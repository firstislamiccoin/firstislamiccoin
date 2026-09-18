#!/usr/bin/env python3
# Copyright (c) 2018-2022 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test the Partially Signed Transaction RPCs.
"""
from decimal import Decimal
from itertools import product

from test_framework.descriptors import descsum_create
from test_framework.fic import get_min_fee_sat
from test_framework.key import H_POINT
from test_framework.messages import (
    COutPoint,
    CTransaction,
    CTxIn,
    CTxOut,
    MAX_BIP125_RBF_SEQUENCE,
    WITNESS_SCALE_FACTOR,
    ser_compact_size,
)
from test_framework.psbt import (
    PSBT,
    PSBTMap,
    PSBT_GLOBAL_UNSIGNED_TX,
    PSBT_IN_RIPEMD160,
    PSBT_IN_SHA256,
    PSBT_IN_HASH160,
    PSBT_IN_HASH256,
    PSBT_IN_NON_WITNESS_UTXO,
    PSBT_IN_WITNESS_UTXO,
    PSBT_OUT_TAP_TREE,
)
from test_framework.script import CScript, OP_TRUE
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import (
    assert_approx,
    assert_equal,
    assert_greater_than,
    assert_greater_than_or_equal,
    assert_raises_rpc_error,
    find_output,
    find_vout_for_address,
    random_bytes,
)
from test_framework.wallet_util import (
    generate_keypair,
    get_generate_key,
)

import json
import os


class PSBTTest(BitcoinTestFramework):
    def add_options(self, parser):
        self.add_wallet_options(parser)

    def set_test_params(self):
        self.num_nodes = 3
        self.extra_args = [
            ["-addresstype=bech32", "-changetype=bech32"], #TODO: Remove address type restrictions once taproot has psbt extensions
            ["-changetype=legacy"],
            []
        ]
        # whitelist peers to speed up tx relay / mempool sync
        for args in self.extra_args:
            args.append("-whitelist=noban@127.0.0.1")
        self.supports_cli = False

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def test_utxo_conversion(self):
        self.log.info("Check that non-witness UTXOs are removed for segwit v1+ inputs")
        mining_node = self.nodes[2]
        offline_node = self.nodes[0]
        online_node = self.nodes[1]

        # Disconnect offline node from others
        # Topology of test network is linear, so this one call is enough
        self.disconnect_nodes(0, 1)

        # Create watchonly on online_node
        online_node.createwallet(wallet_name='wonline', disable_private_keys=True)
        wonline = online_node.get_wallet_rpc('wonline')
        w2 = online_node.get_wallet_rpc(self.default_wallet_name)

        # Mine a transaction that credits the offline address
        offline_addr = offline_node.getnewaddress(address_type="bech32m")
        online_addr = w2.getnewaddress(address_type="bech32m")
        wonline.importaddress(offline_addr, "", False)
        mining_wallet = mining_node.get_wallet_rpc(self.default_wallet_name)
        mining_wallet.sendtoaddress(address=offline_addr, amount=1.0)
        self.generate(mining_node, nblocks=1, sync_fun=lambda: self.sync_all([online_node, mining_node]))

        # Construct an unsigned PSBT on the online node
        # FirstIslamicCoin: leaving only 0.0001 BTC (10000 sat) fee here
        # assumed upstream's ~1 sat/vB relay fee; this fork's consensus floor
        # is a fixed 100 sat/vB (GetMinFee(), src/consensus/tx_verify.cpp),
        # so a single-input/single-output tx needs more like ~12000-15000 sat
        # and 10000 flat gets rejected with bad-txns-fee-not-enough. Bumped
        # to leave a 0.001 BTC (100000 sat) fee, comfortably above the floor.
        utxos = wonline.listunspent(addresses=[offline_addr])
        raw = wonline.createrawtransaction([{"txid":utxos[0]["txid"], "vout":utxos[0]["vout"]}],[{online_addr:0.999}])
        psbt = wonline.walletprocesspsbt(online_node.converttopsbt(raw))["psbt"]
        assert not "not_witness_utxo" in mining_node.decodepsbt(psbt)["inputs"][0]

        # add non-witness UTXO manually
        psbt_new = PSBT.from_base64(psbt)
        prev_tx = wonline.gettransaction(utxos[0]["txid"])["hex"]
        psbt_new.i[0].map[PSBT_IN_NON_WITNESS_UTXO] = bytes.fromhex(prev_tx)
        assert "non_witness_utxo" in mining_node.decodepsbt(psbt_new.to_base64())["inputs"][0]

        # Have the offline node sign the PSBT (which will remove the non-witness UTXO)
        signed_psbt = offline_node.walletprocesspsbt(psbt_new.to_base64())
        assert not "non_witness_utxo" in mining_node.decodepsbt(signed_psbt["psbt"])["inputs"][0]

        # Make sure we can mine the resulting transaction
        txid = mining_node.sendrawtransaction(signed_psbt["hex"])
        self.generate(mining_node, nblocks=1, sync_fun=lambda: self.sync_all([online_node, mining_node]))
        assert_equal(online_node.gettxout(txid,0)["confirmations"], 1)

        wonline.unloadwallet()

        # Reconnect
        self.connect_nodes(1, 0)
        self.connect_nodes(0, 2)

    def test_input_confs_control(self):
        self.nodes[0].createwallet("minconf")
        wallet = self.nodes[0].get_wallet_rpc("minconf")

        # Fund the wallet with different chain heights
        for _ in range(2):
            self.nodes[1].sendmany("", {wallet.getnewaddress():1, wallet.getnewaddress():1})
            self.generate(self.nodes[1], 1)

        unconfirmed_txid = wallet.sendtoaddress(wallet.getnewaddress(), 0.5)

        self.log.info("Crafting PSBT using an unconfirmed input")
        target_address = self.nodes[1].getnewaddress()
        psbtx1 = wallet.walletcreatefundedpsbt([], {target_address: 0.1}, 0, {'fee_rate': 1, 'maxconf': 0})['psbt']

        # Make sure we only had the one input
        tx1_inputs = self.nodes[0].decodepsbt(psbtx1)['tx']['vin']
        assert_equal(len(tx1_inputs), 1)

        utxo1 = tx1_inputs[0]
        assert_equal(unconfirmed_txid, utxo1['txid'])

        signed_tx1 = wallet.walletprocesspsbt(psbtx1)
        txid1 = self.nodes[0].sendrawtransaction(signed_tx1['hex'])

        mempool = self.nodes[0].getrawmempool()
        assert txid1 in mempool

        self.log.info("Fail to craft a new PSBT that sends more funds with add_inputs = False")
        assert_raises_rpc_error(-4, "The preselected coins total amount does not cover the transaction target. Please allow other inputs to be automatically selected or include more coins manually", wallet.walletcreatefundedpsbt, [{'txid': utxo1['txid'], 'vout': utxo1['vout']}], {target_address: 1}, 0, {'add_inputs': False})

        self.log.info("Fail to craft a new PSBT with minconf above highest one")
        assert_raises_rpc_error(-4, "Insufficient funds", wallet.walletcreatefundedpsbt, [{'txid': utxo1['txid'], 'vout': utxo1['vout']}], {target_address: 1}, 0, {'add_inputs': True, 'minconf': 3, 'fee_rate': 10})

        self.log.info("Fail to broadcast a new PSBT with maxconf 0 due to BIP125 rules to verify it actually chose unconfirmed outputs")
        psbt_invalid = wallet.walletcreatefundedpsbt([{'txid': utxo1['txid'], 'vout': utxo1['vout']}], {target_address: 1}, 0, {'add_inputs': True, 'maxconf': 0, 'fee_rate': 10})['psbt']
        signed_invalid = wallet.walletprocesspsbt(psbt_invalid)
        # FirstIslamicCoin: "bad-txns-spends-conflicting-tx" is only reached
        # by upstream's BIP125 replacement-vs-ancestor-conflict check in
        # PreChecks() (src/validation.cpp), which is entirely commented out
        # here under a "// FirstIslamicCoin: Disable replacement feature for
        # now" block (src/validation.cpp, ~line 953) -- replacement is
        # disabled outright, so any mempool conflict is rejected immediately
        # and unconditionally, earlier in the same function, as
        # "txn-mempool-conflict" (src/validation.cpp, ~line 771).
        assert_raises_rpc_error(-26, "txn-mempool-conflict", self.nodes[0].sendrawtransaction, signed_invalid['hex'])

        self.log.info("Craft a replacement adding inputs with highest confs possible")
        psbtx2 = wallet.walletcreatefundedpsbt([{'txid': utxo1['txid'], 'vout': utxo1['vout']}], {target_address: 1}, 0, {'add_inputs': True, 'minconf': 2, 'fee_rate': 10})['psbt']
        tx2_inputs = self.nodes[0].decodepsbt(psbtx2)['tx']['vin']
        assert_greater_than_or_equal(len(tx2_inputs), 2)
        for vin in tx2_inputs:
            if vin['txid'] != unconfirmed_txid:
                assert_greater_than_or_equal(self.nodes[0].gettxout(vin['txid'], vin['vout'])['confirmations'], 2)

        # FirstIslamicCoin: walletcreatefundedpsbt's minconf-driven coin
        # selection above is unaffected by RBF and still genuinely adds
        # higher-confirmation inputs on top of the preselected unconfirmed
        # one, as asserted above. But broadcasting signed_tx2 as an actual
        # *replacement* of txid1 -- upstream's whole point here -- cannot
        # work on this fork: signed_tx2 still spends utxo1, which txid1 (in
        # the mempool since "Fail to craft a new PSBT..." above) also
        # spends, and replacement is disabled outright (see the
        # "txn-mempool-conflict" comment above), so this is the same
        # unconditional early conflict rejection, not a genuine BIP125
        # evaluation. Assert the same rejection instead of a successful
        # replacement, and that txid1 (never replaced) is still the one
        # sitting in the mempool.
        signed_tx2 = wallet.walletprocesspsbt(psbtx2)
        assert_raises_rpc_error(-26, "txn-mempool-conflict", self.nodes[0].sendrawtransaction, signed_tx2['hex'])

        mempool = self.nodes[0].getrawmempool()
        assert txid1 in mempool

        wallet.unloadwallet()

    def assert_change_type(self, psbtx, expected_type):
        """Assert that the given PSBT has a change output with the given type."""

        # The decodepsbt RPC is stateless and independent of any settings, we can always just call it on the first node
        decoded_psbt = self.nodes[0].decodepsbt(psbtx["psbt"])
        changepos = psbtx["changepos"]
        assert_equal(decoded_psbt["tx"]["vout"][changepos]["scriptPubKey"]["type"], expected_type)

    def run_test(self):
        # Create and fund a raw tx for sending 10 BTC
        psbtx1 = self.nodes[0].walletcreatefundedpsbt([], {self.nodes[2].getnewaddress():10})['psbt']

        # If inputs are specified, do not automatically add more:
        utxo1 = self.nodes[0].listunspent()[0]
        # FirstIslamicCoin: a single coinbase UTXO here is a whole
        # POW_SUBSIDY (28,000,000 coins, this fork's flat per-block PoW
        # reward), which trivially covers upstream's 90-coin target -- so
        # the "preselected coins insufficient" error never triggered. Use a
        # target between one and two block subsidies so one UTXO falls
        # short but two (the len(vin)==2 check below) cover it.
        target_amount = 30_000_000
        assert_raises_rpc_error(-4, "The preselected coins total amount does not cover the transaction target. "
                                    "Please allow other inputs to be automatically selected or include more coins manually",
                                self.nodes[0].walletcreatefundedpsbt, [{"txid": utxo1['txid'], "vout": utxo1['vout']}], {self.nodes[2].getnewaddress():target_amount})

        psbtx1 = self.nodes[0].walletcreatefundedpsbt([{"txid": utxo1['txid'], "vout": utxo1['vout']}], {self.nodes[2].getnewaddress():target_amount}, 0, {"add_inputs": True})['psbt']
        assert_equal(len(self.nodes[0].decodepsbt(psbtx1)['tx']['vin']), 2)

        # Inputs argument can be null
        self.nodes[0].walletcreatefundedpsbt(None, {self.nodes[2].getnewaddress():10})

        # Node 1 should not be able to add anything to it but still return the psbtx same as before
        psbtx = self.nodes[1].walletprocesspsbt(psbtx1)['psbt']
        assert_equal(psbtx1, psbtx)

        # Node 0 should not be able to sign the transaction with the wallet is locked
        self.nodes[0].encryptwallet("password")
        assert_raises_rpc_error(-13, "Please enter the wallet passphrase with walletpassphrase first", self.nodes[0].walletprocesspsbt, psbtx)

        # Node 0 should be able to process without signing though
        unsigned_tx = self.nodes[0].walletprocesspsbt(psbtx, False)
        assert_equal(unsigned_tx['complete'], False)

        self.nodes[0].walletpassphrase(passphrase="password", timeout=1000000)

        # Sign the transaction but don't finalize
        processed_psbt = self.nodes[0].walletprocesspsbt(psbt=psbtx, finalize=False)
        assert "hex" not in processed_psbt
        signed_psbt = processed_psbt['psbt']

        # Finalize and send
        finalized_hex = self.nodes[0].finalizepsbt(signed_psbt)['hex']
        self.nodes[0].sendrawtransaction(finalized_hex)

        # Alternative method: sign AND finalize in one command
        processed_finalized_psbt = self.nodes[0].walletprocesspsbt(psbt=psbtx, finalize=True)
        finalized_psbt = processed_finalized_psbt['psbt']
        finalized_psbt_hex = processed_finalized_psbt['hex']
        assert signed_psbt != finalized_psbt
        assert finalized_psbt_hex == finalized_hex

        # Manually selected inputs can be locked:
        assert_equal(len(self.nodes[0].listlockunspent()), 0)
        utxo1 = self.nodes[0].listunspent()[0]
        psbtx1 = self.nodes[0].walletcreatefundedpsbt([{"txid": utxo1['txid'], "vout": utxo1['vout']}], {self.nodes[2].getnewaddress():1}, 0,{"lockUnspents": True})["psbt"]
        assert_equal(len(self.nodes[0].listlockunspent()), 1)

        # Locks are ignored for manually selected inputs
        self.nodes[0].walletcreatefundedpsbt([{"txid": utxo1['txid'], "vout": utxo1['vout']}], {self.nodes[2].getnewaddress():1}, 0)

        # Create p2sh, p2wpkh, and p2wsh addresses
        pubkey0 = self.nodes[0].getaddressinfo(self.nodes[0].getnewaddress())['pubkey']
        pubkey1 = self.nodes[1].getaddressinfo(self.nodes[1].getnewaddress())['pubkey']
        pubkey2 = self.nodes[2].getaddressinfo(self.nodes[2].getnewaddress())['pubkey']

        # Setup watchonly wallets
        self.nodes[2].createwallet(wallet_name='wmulti', disable_private_keys=True)
        wmulti = self.nodes[2].get_wallet_rpc('wmulti')

        # Create all the addresses
        p2sh = wmulti.addmultisigaddress(2, [pubkey0, pubkey1, pubkey2], "", "legacy")['address']
        p2wsh = wmulti.addmultisigaddress(2, [pubkey0, pubkey1, pubkey2], "", "bech32")['address']
        p2sh_p2wsh = wmulti.addmultisigaddress(2, [pubkey0, pubkey1, pubkey2], "", "p2sh-segwit")['address']
        if not self.options.descriptors:
            wmulti.importaddress(p2sh)
            wmulti.importaddress(p2wsh)
            wmulti.importaddress(p2sh_p2wsh)
        p2wpkh = self.nodes[1].getnewaddress("", "bech32")
        p2pkh = self.nodes[1].getnewaddress("", "legacy")
        # FirstIslamicCoin: src/wallet/rpc/addresses.cpp's getnewaddress
        # rejects output_type P2SH_SEGWIT outright ("P2SH_SEGWIT addresses
        # are not welcome") -- a real, pre-existing restriction inherited
        # unmodified from the CodexaCoin import, unrelated to the
        # multisig p2sh_p2wsh address above (addmultisigaddress has no such
        # restriction). p2wpkh/p2pkh below already exercise the mixed
        # witness/non-witness UTXO PSBT paths this section is testing.

        # fund those addresses
        rawtx = self.nodes[0].createrawtransaction([], {p2sh:10, p2wsh:10, p2wpkh:10, p2sh_p2wsh:10, p2pkh:10})
        rawtx = self.nodes[0].fundrawtransaction(rawtx, {"changePosition":3})
        signed_tx = self.nodes[0].signrawtransactionwithwallet(rawtx['hex'])['hex']
        txid = self.nodes[0].sendrawtransaction(signed_tx)
        self.generate(self.nodes[0], 6)

        # Find the output pos
        p2sh_pos = -1
        p2wsh_pos = -1
        p2wpkh_pos = -1
        p2pkh_pos = -1
        p2sh_p2wsh_pos = -1
        decoded = self.nodes[0].decoderawtransaction(signed_tx)
        for out in decoded['vout']:
            if out['scriptPubKey']['address'] == p2sh:
                p2sh_pos = out['n']
            elif out['scriptPubKey']['address'] == p2wsh:
                p2wsh_pos = out['n']
            elif out['scriptPubKey']['address'] == p2wpkh:
                p2wpkh_pos = out['n']
            elif out['scriptPubKey']['address'] == p2sh_p2wsh:
                p2sh_p2wsh_pos = out['n']
            elif out['scriptPubKey']['address'] == p2pkh:
                p2pkh_pos = out['n']

        inputs = [{"txid": txid, "vout": p2wpkh_pos}, {"txid": txid, "vout": p2pkh_pos}]
        # FirstIslamicCoin: 19.99, not upstream's 29.99 -- inputs above is
        # now two 10-BTC addresses, not three, since p2sh_p2wpkh was dropped.
        outputs = [{self.nodes[1].getnewaddress(): 19.99}]

        # spend single key from node 1
        created_psbt = self.nodes[1].walletcreatefundedpsbt(inputs, outputs)
        walletprocesspsbt_out = self.nodes[1].walletprocesspsbt(created_psbt['psbt'])
        # Make sure it has both types of UTXOs
        decoded = self.nodes[1].decodepsbt(walletprocesspsbt_out['psbt'])
        assert 'non_witness_utxo' in decoded['inputs'][0]
        assert 'witness_utxo' in decoded['inputs'][0]
        # Check decodepsbt fee calculation (input values shall only be counted once per UTXO)
        assert_equal(decoded['fee'], created_psbt['fee'])
        assert_equal(walletprocesspsbt_out['complete'], True)
        self.nodes[1].sendrawtransaction(walletprocesspsbt_out['hex'])

        # FirstIslamicCoin: upstream's 0.05290000/0.055 assumed the 3-input
        # (p2wpkh/p2sh_p2wpkh/p2pkh) tx built above; with p2sh_p2wpkh dropped
        # (see the "not welcome" comment above) this is a smaller tx, so the
        # same fee_rate produces a smaller total fee -- confirmed empirically.
        self.log.info("Test walletcreatefundedpsbt fee rate of 10000 sat/vB and 0.1 BTC/kvB produces a total fee at or slightly below -maxtxfee (~0.04410000)")
        res1 = self.nodes[1].walletcreatefundedpsbt(inputs, outputs, 0, {"fee_rate": 10000, "add_inputs": True})
        assert_approx(res1["fee"], 0.0441, 0.0005)
        res2 = self.nodes[1].walletcreatefundedpsbt(inputs, outputs, 0, {"feeRate": "0.1", "add_inputs": True})
        assert_approx(res2["fee"], 0.0441, 0.0005)

        # FirstIslamicCoin: "bypassed" doesn't hold here -- unlike upstream
        # (no fee floor), a fee_rate under 1 sat/vB is silently bumped up to
        # this fork's 100 sat/vB consensus minimum instead of being honoured
        # as requested; confirmed empirically (0.000294 BTC, not upstream's
        # 0.00000381 BTC).
        self.log.info("Test that a fee_rate under 1 sat/vB is bumped up to the fee floor with walletcreatefundedpsbt")
        res3 = self.nodes[1].walletcreatefundedpsbt(inputs, outputs, 0, {"fee_rate": "0.999", "add_inputs": True})
        assert_approx(res3["fee"], 0.000294, 0.00001)
        res4 = self.nodes[1].walletcreatefundedpsbt(inputs, outputs, 0, {"feeRate": 0.00000999, "add_inputs": True})
        assert_approx(res4["fee"], 0.000294, 0.00001)

        # FirstIslamicCoin: a requested zero fee is likewise bumped up to the
        # fee floor here, not honoured as a genuine zero fee -- see the
        # "bumped up to the fee floor" comment above.
        self.log.info("Test that a zero fee_rate is bumped up to the fee floor with walletcreatefundedpsbt")
        for param, zero_value in product(["fee_rate", "feeRate"], [0, 0.000, 0.00000000, "0", "0.000", "0.00000000"]):
            assert_equal(Decimal("0.000294"), self.nodes[1].walletcreatefundedpsbt(inputs, outputs, 0, {param: zero_value, "add_inputs": True})["fee"])

        self.log.info("Test invalid fee rate settings")
        # FirstIslamicCoin: this fork's DEFAULT_TRANSACTION_MAXFEE (-maxtxfee
        # default) is 1 BTC, not upstream's 0.1 BTC -- scaled for this fork's
        # economics. Upstream's 100000 sat/vB (~0.44 BTC total here) stays
        # under that higher cap, so it no longer trips "Fee exceeds maximum";
        # bumped both values well past 1 BTC for this tx's size.
        for param, value in {("fee_rate", 300000), ("feeRate", 3)}:
            assert_raises_rpc_error(-4, "Fee exceeds maximum configured by user (e.g. -maxtxfee, maxfeerate)",
                self.nodes[1].walletcreatefundedpsbt, inputs, outputs, 0, {param: value, "add_inputs": True})
            assert_raises_rpc_error(-3, "Amount out of range",
                self.nodes[1].walletcreatefundedpsbt, inputs, outputs, 0, {param: -1, "add_inputs": True})
            assert_raises_rpc_error(-3, "Amount is not a number or string",
                self.nodes[1].walletcreatefundedpsbt, inputs, outputs, 0, {param: {"foo": "bar"}, "add_inputs": True})
            # Test fee rate values that don't pass fixed-point parsing checks.
            for invalid_value in ["", 0.000000001, 1e-09, 1.111111111, 1111111111111111, "31.999999999999999999999"]:
                assert_raises_rpc_error(-3, "Invalid amount",
                    self.nodes[1].walletcreatefundedpsbt, inputs, outputs, 0, {param: invalid_value, "add_inputs": True})
        # Test fee_rate values that cannot be represented in sat/vB.
        for invalid_value in [0.0001, 0.00000001, 0.00099999, 31.99999999]:
            assert_raises_rpc_error(-3, "Invalid amount",
                self.nodes[1].walletcreatefundedpsbt, inputs, outputs, 0, {"fee_rate": invalid_value, "add_inputs": True})

        self.log.info("- raises RPC error if both feeRate and fee_rate are passed")
        assert_raises_rpc_error(-8, "Cannot specify both fee_rate (sat/vB) and feeRate (FIC/kvB)",
            self.nodes[1].walletcreatefundedpsbt, inputs, outputs, 0, {"fee_rate": 0.1, "feeRate": 0.1, "add_inputs": True})

        # FirstIslamicCoin: estimate_mode/conf_target don't exist as
        # walletcreatefundedpsbt options at all on this fork (no dynamic fee
        # estimation to configure -- see FundTransaction in
        # src/wallet/rpc/spend.cpp), so passing either just raises "Unexpected
        # key", not the "Cannot specify both ..." conflict errors upstream
        # tests here. Dropped, matching the same removal already made for
        # send()'s equivalent conf_target/estimate_mode cases.

        # FirstIslamicCoin: estimate_mode/conf_target validation (both
        # value-type checks and range checks) doesn't apply either -- neither
        # parameter is recognized at all, per the removal noted above.

        self.log.info("Test walletcreatefundedpsbt with too-high fee rate produces total fee well above -maxtxfee and raises RPC error")
        # previously this was silently capped at -maxtxfee
        # FirstIslamicCoin: feeRate is BTC/kvB, so 10 (not upstream's 1)
        # matches fee_rate=1000000 sat/vB below -- needed since this fork's
        # -maxtxfee default is 1 BTC, not upstream's 0.1 BTC (see above).
        for bool_add, outputs_array in {True: outputs, False: [{self.nodes[1].getnewaddress(): 1}]}.items():
            msg = "Fee exceeds maximum configured by user (e.g. -maxtxfee, maxfeerate)"
            assert_raises_rpc_error(-4, msg, self.nodes[1].walletcreatefundedpsbt, inputs, outputs_array, 0, {"fee_rate": 1000000, "add_inputs": bool_add})
            assert_raises_rpc_error(-4, msg, self.nodes[1].walletcreatefundedpsbt, inputs, outputs_array, 0, {"feeRate": 10, "add_inputs": bool_add})

        self.log.info("Test various PSBT operations")
        # partially sign multisig things with node 1
        psbtx = wmulti.walletcreatefundedpsbt(inputs=[{"txid":txid,"vout":p2wsh_pos},{"txid":txid,"vout":p2sh_pos},{"txid":txid,"vout":p2sh_p2wsh_pos}], outputs={self.nodes[1].getnewaddress():29.99}, changeAddress=self.nodes[1].getrawchangeaddress())['psbt']
        walletprocesspsbt_out = self.nodes[1].walletprocesspsbt(psbtx)
        psbtx = walletprocesspsbt_out['psbt']
        assert_equal(walletprocesspsbt_out['complete'], False)

        # Unload wmulti, we don't need it anymore
        wmulti.unloadwallet()

        # partially sign with node 2. This should be complete and sendable
        walletprocesspsbt_out = self.nodes[2].walletprocesspsbt(psbtx)
        assert_equal(walletprocesspsbt_out['complete'], True)
        self.nodes[2].sendrawtransaction(walletprocesspsbt_out['hex'])

        # check that walletprocesspsbt fails to decode a non-psbt
        rawtx = self.nodes[1].createrawtransaction([{"txid":txid,"vout":p2wpkh_pos}], {self.nodes[1].getnewaddress():9.99})
        assert_raises_rpc_error(-22, "TX decode failed", self.nodes[1].walletprocesspsbt, rawtx)

        # Convert a non-psbt to psbt and make sure we can decode it
        rawtx = self.nodes[0].createrawtransaction([], {self.nodes[1].getnewaddress():10})
        rawtx = self.nodes[0].fundrawtransaction(rawtx)
        new_psbt = self.nodes[0].converttopsbt(rawtx['hex'])
        self.nodes[0].decodepsbt(new_psbt)

        # Make sure that a non-psbt with signatures cannot be converted
        signedtx = self.nodes[0].signrawtransactionwithwallet(rawtx['hex'])
        assert_raises_rpc_error(-22, "Inputs must not have scriptSigs and scriptWitnesses",
                                self.nodes[0].converttopsbt, hexstring=signedtx['hex'])  # permitsigdata=False by default
        assert_raises_rpc_error(-22, "Inputs must not have scriptSigs and scriptWitnesses",
                                self.nodes[0].converttopsbt, hexstring=signedtx['hex'], permitsigdata=False)
        assert_raises_rpc_error(-22, "Inputs must not have scriptSigs and scriptWitnesses",
                                self.nodes[0].converttopsbt, hexstring=signedtx['hex'], permitsigdata=False, iswitness=True)
        # Unless we allow it to convert and strip signatures
        self.nodes[0].converttopsbt(hexstring=signedtx['hex'], permitsigdata=True)

        # Create outputs to nodes 1 and 2
        node1_addr = self.nodes[1].getnewaddress()
        node2_addr = self.nodes[2].getnewaddress()
        txid1 = self.nodes[0].sendtoaddress(node1_addr, 13)
        txid2 = self.nodes[0].sendtoaddress(node2_addr, 13)
        blockhash = self.generate(self.nodes[0], 6)[0]
        vout1 = find_output(self.nodes[1], txid1, 13, blockhash=blockhash)
        vout2 = find_output(self.nodes[2], txid2, 13, blockhash=blockhash)

        # Create a psbt spending outputs from nodes 1 and 2
        psbt_orig = self.nodes[0].createpsbt([{"txid":txid1,  "vout":vout1}, {"txid":txid2, "vout":vout2}], {self.nodes[0].getnewaddress():25.999})

        # Update psbts, should only have data for one input and not the other
        psbt1 = self.nodes[1].walletprocesspsbt(psbt_orig, False, "ALL")['psbt']
        psbt1_decoded = self.nodes[0].decodepsbt(psbt1)
        assert psbt1_decoded['inputs'][0] and not psbt1_decoded['inputs'][1]
        # Check that BIP32 path was added
        assert "bip32_derivs" in psbt1_decoded['inputs'][0]
        psbt2 = self.nodes[2].walletprocesspsbt(psbt_orig, False, "ALL", False)['psbt']
        psbt2_decoded = self.nodes[0].decodepsbt(psbt2)
        assert not psbt2_decoded['inputs'][0] and psbt2_decoded['inputs'][1]
        # Check that BIP32 paths were not added
        assert "bip32_derivs" not in psbt2_decoded['inputs'][1]

        # Sign PSBTs (workaround issue #18039)
        psbt1 = self.nodes[1].walletprocesspsbt(psbt_orig)['psbt']
        psbt2 = self.nodes[2].walletprocesspsbt(psbt_orig)['psbt']

        # Combine, finalize, and send the psbts
        combined = self.nodes[0].combinepsbt([psbt1, psbt2])
        finalized = self.nodes[0].finalizepsbt(combined)['hex']
        self.nodes[0].sendrawtransaction(finalized)
        self.generate(self.nodes[0], 6)

        # Test additional args in walletcreatepsbt
        # Make sure both pre-included and funded inputs have the correct
        # sequence numbers.
        # FirstIslamicCoin: RBF is fully disabled on this fork (see
        # PreChecks() in src/validation.cpp), and the "replaceable" option
        # was removed from FundTransaction's options entirely along with it
        # (src/wallet/rpc/spend.cpp) -- passing it at all now raises
        # "Unexpected key". Every created tx's sequence number is always
        # non-replaceable (> MAX_BIP125_RBF_SEQUENCE), confirmed empirically,
        # so upstream's "replaceable explicitly enabled" case (which asserted
        # sequence == MAX_BIP125_RBF_SEQUENCE) no longer has a way to occur
        # and is dropped; the "explicitly disabled" and "no arguments" cases
        # collapse into the same assertion since there's no longer a way to
        # ask for anything else.
        block_height = self.nodes[0].getblockcount()
        unspent = self.nodes[0].listunspent()[0]
        psbtx_info = self.nodes[0].walletcreatefundedpsbt([{"txid":unspent["txid"], "vout":unspent["vout"]}], [{self.nodes[2].getnewaddress():unspent["amount"]+1}], block_height+2, {"add_inputs": True}, False)
        decoded_psbt = self.nodes[0].decodepsbt(psbtx_info["psbt"])
        for tx_in, psbt_in in zip(decoded_psbt["tx"]["vin"], decoded_psbt["inputs"]):
            assert_greater_than(tx_in["sequence"], MAX_BIP125_RBF_SEQUENCE)
            assert "bip32_derivs" not in psbt_in
        assert_equal(decoded_psbt["tx"]["locktime"], block_height+2)

        # Same construction with only locktime set
        psbtx_info = self.nodes[0].walletcreatefundedpsbt([{"txid":unspent["txid"], "vout":unspent["vout"]}], [{self.nodes[2].getnewaddress():unspent["amount"]+1}], block_height, {"add_inputs": True}, True)
        decoded_psbt = self.nodes[0].decodepsbt(psbtx_info["psbt"])
        for tx_in, psbt_in in zip(decoded_psbt["tx"]["vin"], decoded_psbt["inputs"]):
            assert_greater_than(tx_in["sequence"], MAX_BIP125_RBF_SEQUENCE)
            assert "bip32_derivs" in psbt_in
        assert_equal(decoded_psbt["tx"]["locktime"], block_height)

        # Same construction without optional arguments. Not
        # MAX_BIP125_RBF_SEQUENCE as upstream expects (RBF is disabled here
        # regardless of node config -- see the comment above).
        psbtx_info = self.nodes[0].walletcreatefundedpsbt([], [{self.nodes[2].getnewaddress():unspent["amount"]+1}])
        decoded_psbt = self.nodes[0].decodepsbt(psbtx_info["psbt"])
        for tx_in, psbt_in in zip(decoded_psbt["tx"]["vin"], decoded_psbt["inputs"]):
            assert_greater_than(tx_in["sequence"], MAX_BIP125_RBF_SEQUENCE)
            assert "bip32_derivs" in psbt_in
        assert_equal(decoded_psbt["tx"]["locktime"], 0)

        # Same construction without optional arguments, for a node with -walletrbf=0
        unspent1 = self.nodes[1].listunspent()[0]
        psbtx_info = self.nodes[1].walletcreatefundedpsbt([{"txid":unspent1["txid"], "vout":unspent1["vout"]}], [{self.nodes[2].getnewaddress():unspent1["amount"]+1}], block_height, {"add_inputs": True})
        decoded_psbt = self.nodes[1].decodepsbt(psbtx_info["psbt"])
        for tx_in, psbt_in in zip(decoded_psbt["tx"]["vin"], decoded_psbt["inputs"]):
            assert_greater_than(tx_in["sequence"], MAX_BIP125_RBF_SEQUENCE)
            assert "bip32_derivs" in psbt_in

        # Make sure change address wallet does not have P2SH innerscript access to results in success
        # when attempting BnB coin selection
        self.nodes[0].walletcreatefundedpsbt([], [{self.nodes[2].getnewaddress():unspent["amount"]+1}], block_height+2, {"changeAddress":self.nodes[1].getnewaddress()}, False)

        # Make sure the wallet's change type is respected by default
        small_output = {self.nodes[0].getnewaddress():0.1}
        psbtx_native = self.nodes[0].walletcreatefundedpsbt([], [small_output])
        self.assert_change_type(psbtx_native, "witness_v0_keyhash")
        psbtx_legacy = self.nodes[1].walletcreatefundedpsbt([], [small_output])
        self.assert_change_type(psbtx_legacy, "pubkeyhash")

        # Make sure the change type of the wallet can also be overwritten
        psbtx_np2wkh = self.nodes[1].walletcreatefundedpsbt([], [small_output], 0, {"change_type":"p2sh-segwit"})
        self.assert_change_type(psbtx_np2wkh, "scripthash")

        # Make sure the change type cannot be specified if a change address is given
        invalid_options = {"change_type":"legacy","changeAddress":self.nodes[0].getnewaddress()}
        assert_raises_rpc_error(-8, "both change address and address type options", self.nodes[0].walletcreatefundedpsbt, [], [small_output], 0, invalid_options)

        # Regression test for 14473 (mishandling of already-signed witness transaction):
        psbtx_info = self.nodes[0].walletcreatefundedpsbt([{"txid":unspent["txid"], "vout":unspent["vout"]}], [{self.nodes[2].getnewaddress():unspent["amount"]+1}], 0, {"add_inputs": True})
        complete_psbt = self.nodes[0].walletprocesspsbt(psbtx_info["psbt"])
        double_processed_psbt = self.nodes[0].walletprocesspsbt(complete_psbt["psbt"])
        assert_equal(complete_psbt, double_processed_psbt)
        # We don't care about the decode result, but decoding must succeed.
        self.nodes[0].decodepsbt(double_processed_psbt["psbt"])

        # Make sure unsafe inputs are included if specified
        self.nodes[2].createwallet(wallet_name="unsafe")
        wunsafe = self.nodes[2].get_wallet_rpc("unsafe")
        self.nodes[0].sendtoaddress(wunsafe.getnewaddress(), 2)
        self.sync_mempools()
        assert_raises_rpc_error(-4, "Insufficient funds", wunsafe.walletcreatefundedpsbt, [], [{self.nodes[0].getnewaddress(): 1}])
        wunsafe.walletcreatefundedpsbt([], [{self.nodes[0].getnewaddress(): 1}], 0, {"include_unsafe": True})

        # BIP 174 Test Vectors
        # FirstIslamicCoin: data/rpc_psbt.json is upstream's official BIP174
        # fixture (extended with taproot vectors). Most of it is untouched --
        # confirmed empirically that the 39 "invalid" and 2
        # "invalid_with_msg" decode failures, and every "signer"/"combiner"/
        # "finalizer"/"extractor" entry, already pass unmodified on this fork
        # (the invalid ones don't care *why* decodepsbt fails, and the
        # remaining categories' PSBTs happen not to embed a full previous
        # transaction that trips the quirk below).
        #
        # Two things did need regenerating, both because they referenced
        # real Bitcoin mainnet data incompatible with this fork:
        # 1. "valid" indices 0, 2, 6, 7, 10, 11, 12, 13 (of 20) each embed a
        #    real historical Bitcoin transaction (nVersion=1) as their
        #    input's non_witness_utxo. This fork's CTransaction::
        #    UnserializeTransaction (src/primitives/transaction.h, ~line
        #    228) reads an extra 4-byte nTime field whenever nVersion < 2
        #    (a permanent Peercoin-style design difference inherited
        #    unmodified from the CodexaCoin import, not a bug) -- so parsing
        #    those embedded nVersion=1 bytes misreads 4 bytes that were
        #    never there and corrupts everything read afterward, and
        #    decodepsbt fails with "TX decode failed DataStream::read():
        #    end of data". Regenerated by building a genuine, fresh
        #    nVersion=2 "previous transaction" and referencing unsigned tx
        #    on a throwaway FIC regtest node (createrawtransaction), then
        #    substituting only the PSBT_GLOBAL_UNSIGNED_TX and input 0's
        #    NON_WITNESS_UTXO byte blobs -- every other key/value in each
        #    entry (sighash type, global PSBT version, unknown/proprietary
        #    keys, hash preimages) is preserved byte-for-byte, so each entry
        #    still tests exactly the same PSBT feature it did upstream.
        # 2. The single "creator" entry's two output addresses used
        #    Bitcoin's regtest bech32 HRP "bcrt1", which this fork's address
        #    decoder rejects -- this fork's regtest HRP is "rfic1" (see
        #    bech32_hrp in src/kernel/chainparams.cpp; same fix already
        #    applied throughout this test suite, e.g. wallet_dump.py).
        #    Re-encoded both addresses with the same witness program under
        #    "rfic1" instead; the expected unsigned-tx "result" is unchanged
        #    since it depends on the scriptPubKey bytes, not the address's
        #    display HRP (confirmed empirically against a live node).

        # Check that unknown values are just passed through
        unknown_psbt = "cHNidP8BAD8CAAAAAf//////////////////////////////////////////AAAAAAD/////AQAAAAAAAAAAA2oBAAAAAAAACg8BAgMEBQYHCAkPAQIDBAUGBwgJCgsMDQ4PAAA="
        unknown_out = self.nodes[0].walletprocesspsbt(unknown_psbt)['psbt']
        assert_equal(unknown_psbt, unknown_out)

        # Open the data file
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data/rpc_psbt.json'), encoding='utf-8') as f:
            d = json.load(f)
            invalids = d['invalid']
            invalid_with_msgs = d["invalid_with_msg"]
            valids = d['valid']
            creators = d['creator']
            signers = d['signer']
            combiners = d['combiner']
            finalizers = d['finalizer']
            extractors = d['extractor']

        # Invalid PSBTs
        for invalid in invalids:
            assert_raises_rpc_error(-22, "TX decode failed", self.nodes[0].decodepsbt, invalid)
        for invalid in invalid_with_msgs:
            psbt, msg = invalid
            assert_raises_rpc_error(-22, f"TX decode failed {msg}", self.nodes[0].decodepsbt, psbt)

        # Valid PSBTs
        for valid in valids:
            self.nodes[0].decodepsbt(valid)

        # Creator Tests
        # FirstIslamicCoin: createpsbt has no "replaceable" argument at all
        # here (CreateTxDoc() in src/rpc/rawtransaction.cpp only ever
        # declared inputs/outputs/locktime, inherited unmodified from the
        # CodexaCoin import's own RBF removal) -- passing it raises
        # "Unexpected key".
        for creator in creators:
            created_tx = self.nodes[0].createpsbt(inputs=creator['inputs'], outputs=creator['outputs'])
            assert_equal(created_tx, creator['result'])

        # Signer tests
        for i, signer in enumerate(signers):
            self.nodes[2].createwallet(wallet_name="wallet{}".format(i))
            wrpc = self.nodes[2].get_wallet_rpc("wallet{}".format(i))
            for key in signer['privkeys']:
                wrpc.importprivkey(key)
            signed_tx = wrpc.walletprocesspsbt(signer['psbt'], True, "ALL")['psbt']
            assert_equal(signed_tx, signer['result'])

        # Combiner test
        for combiner in combiners:
            combined = self.nodes[2].combinepsbt(combiner['combine'])
            assert_equal(combined, combiner['result'])

        # Empty combiner test
        assert_raises_rpc_error(-8, "Parameter 'txs' cannot be empty", self.nodes[0].combinepsbt, [])

        # Finalizer test
        for finalizer in finalizers:
            finalized = self.nodes[2].finalizepsbt(finalizer['finalize'], False)['psbt']
            assert_equal(finalized, finalizer['result'])

        # Extractor test
        for extractor in extractors:
            extracted = self.nodes[2].finalizepsbt(extractor['extract'], True)['hex']
            assert_equal(extracted, extractor['result'])

        # Unload extra wallets
        for i, signer in enumerate(signers):
            self.nodes[2].unloadwallet("wallet{}".format(i))

        if self.options.descriptors:
            self.test_utxo_conversion()

        self.test_input_confs_control()

        # Test that psbts with p2pkh outputs are created properly
        p2pkh = self.nodes[0].getnewaddress(address_type='legacy')
        psbt = self.nodes[1].walletcreatefundedpsbt([], [{p2pkh : 1}], 0, {"includeWatching" : True}, True)
        self.nodes[0].decodepsbt(psbt['psbt'])

        # Test decoding error: invalid base64
        assert_raises_rpc_error(-22, "TX decode failed invalid base64", self.nodes[0].decodepsbt, ";definitely not base64;")

        # Send to all types of addresses
        addr1 = self.nodes[1].getnewaddress("", "bech32")
        txid1 = self.nodes[0].sendtoaddress(addr1, 11)
        vout1 = find_output(self.nodes[0], txid1, 11)
        addr2 = self.nodes[1].getnewaddress("", "legacy")
        txid2 = self.nodes[0].sendtoaddress(addr2, 11)
        vout2 = find_output(self.nodes[0], txid2, 11)
        # FirstIslamicCoin: getnewaddress rejects "p2sh-segwit" outright (see
        # the "not welcome" comment earlier in this file) -- but that guard
        # is specific to getnewaddress's own RPC handler
        # (src/wallet/rpc/addresses.cpp); the underlying wallet destination
        # logic it calls into (GetNewDestination) has no such restriction,
        # and neither does getrawchangeaddress, which calls
        # GetNewChangeDestination instead. Since this section specifically
        # needs a real, wallet-owned (self-signable) P2SH-P2WPKH address --
        # unlike the getnewaddress removal at the top of run_test(), which
        # had other address types already covering the same PSBT paths --
        # get one via getrawchangeaddress instead; it's otherwise identical
        # to a receiving address for our purposes here.
        addr3 = self.nodes[1].getrawchangeaddress("p2sh-segwit")
        txid3 = self.nodes[0].sendtoaddress(addr3, 11)
        vout3 = find_output(self.nodes[0], txid3, 11)
        self.sync_all()

        def test_psbt_input_keys(psbt_input, keys):
            """Check that the psbt input has only the expected keys."""
            assert_equal(set(keys), set(psbt_input.keys()))

        # Create a PSBT. None of the inputs are filled initially
        psbt = self.nodes[1].createpsbt([{"txid":txid1, "vout":vout1},{"txid":txid2, "vout":vout2},{"txid":txid3, "vout":vout3}], {self.nodes[0].getnewaddress():32.999})
        decoded = self.nodes[1].decodepsbt(psbt)
        test_psbt_input_keys(decoded['inputs'][0], [])
        test_psbt_input_keys(decoded['inputs'][1], [])
        test_psbt_input_keys(decoded['inputs'][2], [])

        # Update a PSBT with UTXOs from the node
        # Bech32 inputs should be filled with witness UTXO. Other inputs should not be filled because they are non-witness
        updated = self.nodes[1].utxoupdatepsbt(psbt)
        decoded = self.nodes[1].decodepsbt(updated)
        test_psbt_input_keys(decoded['inputs'][0], ['witness_utxo', 'non_witness_utxo'])
        test_psbt_input_keys(decoded['inputs'][1], ['non_witness_utxo'])
        test_psbt_input_keys(decoded['inputs'][2], ['non_witness_utxo'])

        # Try again, now while providing descriptors, making P2SH-segwit work, and causing bip32_derivs and redeem_script to be filled in
        descs = [self.nodes[1].getaddressinfo(addr)['desc'] for addr in [addr1,addr2,addr3]]
        updated = self.nodes[1].utxoupdatepsbt(psbt=psbt, descriptors=descs)
        decoded = self.nodes[1].decodepsbt(updated)
        test_psbt_input_keys(decoded['inputs'][0], ['witness_utxo', 'non_witness_utxo', 'bip32_derivs'])
        test_psbt_input_keys(decoded['inputs'][1], ['non_witness_utxo', 'bip32_derivs'])
        test_psbt_input_keys(decoded['inputs'][2], ['non_witness_utxo','witness_utxo', 'bip32_derivs', 'redeem_script'])

        # Two PSBTs with a common input should not be joinable
        psbt1 = self.nodes[1].createpsbt([{"txid":txid1, "vout":vout1}], {self.nodes[0].getnewaddress():Decimal('10.999')})
        assert_raises_rpc_error(-8, "exists in multiple PSBTs", self.nodes[1].joinpsbts, [psbt1, updated])

        # Join two distinct PSBTs
        addr4 = self.nodes[1].getrawchangeaddress("p2sh-segwit")  # FirstIslamicCoin: see the getrawchangeaddress comment above
        txid4 = self.nodes[0].sendtoaddress(addr4, 5)
        vout4 = find_output(self.nodes[0], txid4, 5)
        self.generate(self.nodes[0], 6)
        psbt2 = self.nodes[1].createpsbt([{"txid":txid4, "vout":vout4}], {self.nodes[0].getnewaddress():Decimal('4.999')})
        psbt2 = self.nodes[1].walletprocesspsbt(psbt2)['psbt']
        psbt2_decoded = self.nodes[0].decodepsbt(psbt2)
        assert "final_scriptwitness" in psbt2_decoded['inputs'][0] and "final_scriptSig" in psbt2_decoded['inputs'][0]
        joined = self.nodes[0].joinpsbts([psbt, psbt2])
        joined_decoded = self.nodes[0].decodepsbt(joined)
        assert len(joined_decoded['inputs']) == 4 and len(joined_decoded['outputs']) == 2 and "final_scriptwitness" not in joined_decoded['inputs'][3] and "final_scriptSig" not in joined_decoded['inputs'][3]

        # Check that joining shuffles the inputs and outputs
        # 10 attempts should be enough to get a shuffled join
        shuffled = False
        for _ in range(10):
            shuffled_joined = self.nodes[0].joinpsbts([psbt, psbt2])
            shuffled |= joined != shuffled_joined
            if shuffled:
                break
        assert shuffled

        # Newly created PSBT needs UTXOs and updating
        addr = self.nodes[1].getrawchangeaddress("p2sh-segwit")  # FirstIslamicCoin: see the getrawchangeaddress comment above
        txid = self.nodes[0].sendtoaddress(addr, 7)
        addrinfo = self.nodes[1].getaddressinfo(addr)
        blockhash = self.generate(self.nodes[0], 6)[0]
        vout = find_output(self.nodes[0], txid, 7, blockhash=blockhash)
        psbt = self.nodes[1].createpsbt([{"txid":txid, "vout":vout}], {self.nodes[0].getrawchangeaddress("p2sh-segwit"):Decimal('6.999')})
        analyzed = self.nodes[0].analyzepsbt(psbt)
        assert not analyzed['inputs'][0]['has_utxo'] and not analyzed['inputs'][0]['is_final'] and analyzed['inputs'][0]['next'] == 'updater' and analyzed['next'] == 'updater'

        # After update with wallet, only needs signing
        updated = self.nodes[1].walletprocesspsbt(psbt, False, 'ALL', True)['psbt']
        analyzed = self.nodes[0].analyzepsbt(updated)
        assert analyzed['inputs'][0]['has_utxo'] and not analyzed['inputs'][0]['is_final'] and analyzed['inputs'][0]['next'] == 'signer' and analyzed['next'] == 'signer' and analyzed['inputs'][0]['missing']['signatures'][0] == addrinfo['embedded']['witness_program']

        # Check fee and size things
        assert analyzed['fee'] == Decimal('0.001') and analyzed['estimated_vsize'] == 134 and analyzed['estimated_feerate'] == Decimal('0.00746268')

        # After signing and finalizing, needs extracting
        signed = self.nodes[1].walletprocesspsbt(updated)['psbt']
        analyzed = self.nodes[0].analyzepsbt(signed)
        assert analyzed['inputs'][0]['has_utxo'] and analyzed['inputs'][0]['is_final'] and analyzed['next'] == 'extractor'

        self.log.info("PSBT spending unspendable outputs should have error message and Creator as next")
        analysis = self.nodes[0].analyzepsbt('cHNidP8BAJoCAAAAAljoeiG1ba8MI76OcHBFbDNvfLqlyHV5JPVFiHuyq911AAAAAAD/////g40EJ9DsZQpoqka7CwmK6kQiwHGyyng1Kgd5WdB86h0BAAAAAP////8CcKrwCAAAAAAWAEHYXCtx0AYLCcmIauuBXlCZHdoSTQDh9QUAAAAAFv8/wADXYP/7//////8JxOh0LR2HAI8AAAAAAAEBIADC6wsAAAAAF2oUt/X69ELjeX2nTof+fZ10l+OyAokDAQcJAwEHEAABAACAAAEBIADC6wsAAAAAF2oUt/X69ELjeX2nTof+fZ10l+OyAokDAQcJAwEHENkMak8AAAAA')
        assert_equal(analysis['next'], 'creator')
        assert_equal(analysis['error'], 'PSBT is not valid. Input 0 spends unspendable output')

        self.log.info("PSBT with invalid values should have error message and Creator as next")
        # FirstIslamicCoin: the two hardcoded PSBTs below hit
        # AnalyzePSBT()'s MoneyRange() checks (src/node/psbt.cpp, ~line 39).
        # Upstream made them "invalid" purely by exceeding Bitcoin's 21M-coin
        # MAX_MONEY cap -- this fork's MAX_MONEY is INT64_MAX (no cap; see
        # src/consensus/amount.h), so that same byte pattern is now a
        # perfectly legal value here and no longer trips the check. Patched
        # each one's 8-byte little-endian amount field to a genuinely
        # negative CAmount instead (still invalid under any MAX_MONEY,
        # capped or not) -- specifically -2, not -1, since CTxOut::IsNull()
        # treats nValue == -1 as its "this UTXO is unset" sentinel
        # regardless of scriptPubKey (src/primitives/transaction.h) and
        # PartiallySignedTransaction::GetInputUTXO() (src/psbt.cpp) would
        # then treat the input as having *no* UTXO at all rather than an
        # invalid one, changing which check fires -- this collision is
        # inherent to upstream's own CTxOut/PSBT code, not a fork
        # difference, it just happens to matter now that -1 had to be
        # deliberately chosen instead of reusing the original (now-legal)
        # bytes.
        analysis = self.nodes[0].analyzepsbt('cHNidP8BAHECAAAAAfA00BFgAm6tp86RowwH6BMImQNL5zXUcTT97XoLGz0BAAAAAAD/////AgD5ApUAAAAAFgAUKNw0x8HRctAgmvoevm4u1SbN7XL87QKVAAAAABYAFPck4gF7iL4NL4wtfRAKgQbghiTUAAAAAAABAR/+/////////xYAFJUDtxf2PHo641HEOBOAIvFMNTr2AAAA')
        assert_equal(analysis['next'], 'creator')
        assert_equal(analysis['error'], 'PSBT is not valid. Input 0 has invalid value')

        self.log.info("PSBT with signed, but not finalized, inputs should have Finalizer as next")
        analysis = self.nodes[0].analyzepsbt('cHNidP8BAHECAAAAAZYezcxdnbXoQCmrD79t/LzDgtUo9ERqixk8wgioAobrAAAAAAD9////AlDDAAAAAAAAFgAUy/UxxZuzZswcmFnN/E9DGSiHLUsuGPUFAAAAABYAFLsH5o0R38wXx+X2cCosTMCZnQ4baAAAAAABAR8A4fUFAAAAABYAFOBI2h5thf3+Lflb2LGCsVSZwsltIgIC/i4dtVARCRWtROG0HHoGcaVklzJUcwo5homgGkSNAnJHMEQCIGx7zKcMIGr7cEES9BR4Kdt/pzPTK3fKWcGyCJXb7MVnAiALOBgqlMH4GbC1HDh/HmylmO54fyEy4lKde7/BT/PWxwEBAwQBAAAAIgYC/i4dtVARCRWtROG0HHoGcaVklzJUcwo5homgGkSNAnIYDwVpQ1QAAIABAACAAAAAgAAAAAAAAAAAAAAiAgL+CIiB59NSCssOJRGiMYQK1chahgAaaJpIXE41Cyir+xgPBWlDVAAAgAEAAIAAAACAAQAAAAAAAAAA')
        assert_equal(analysis['next'], 'finalizer')

        analysis = self.nodes[0].analyzepsbt('cHNidP8BAHECAAAAAfA00BFgAm6tp86RowwH6BMImQNL5zXUcTT97XoLGz0BAAAAAAD/////Av//////////FgAUKNw0x8HRctAgmvoevm4u1SbN7XL87QKVAAAAABYAFPck4gF7iL4NL4wtfRAKgQbghiTUAAAAAAABAR8A8gUqAQAAABYAFJUDtxf2PHo641HEOBOAIvFMNTr2AAAA')
        assert_equal(analysis['next'], 'creator')
        assert_equal(analysis['error'], 'PSBT is not valid. Output amount invalid')

        analysis = self.nodes[0].analyzepsbt('cHNidP8BAJoCAAAAAkvEW8NnDtdNtDpsmze+Ht2LH35IJcKv00jKAlUs21RrAwAAAAD/////S8Rbw2cO1020OmybN74e3Ysffkglwq/TSMoCVSzbVGsBAAAAAP7///8CwLYClQAAAAAWABSNJKzjaUb3uOxixsvh1GGE3fW7zQD5ApUAAAAAFgAUKNw0x8HRctAgmvoevm4u1SbN7XIAAAAAAAEAnQIAAAACczMa321tVHuN4GKWKRncycI22aX3uXgwSFUKM2orjRsBAAAAAP7///9zMxrfbW1Ue43gYpYpGdzJwjbZpfe5eDBIVQozaiuNGwAAAAAA/v///wIA+QKVAAAAABl2qRT9zXUVA8Ls5iVqynLHe5/vSe1XyYisQM0ClQAAAAAWABRmWQUcjSjghQ8/uH4Bn/zkakwLtAAAAAAAAQEfQM0ClQAAAAAWABRmWQUcjSjghQ8/uH4Bn/zkakwLtAAAAA==')
        assert_equal(analysis['next'], 'creator')
        assert_equal(analysis['error'], 'PSBT is not valid. Input 0 specifies invalid prevout')

        assert_raises_rpc_error(-25, 'Inputs missing or spent', self.nodes[0].walletprocesspsbt, 'cHNidP8BAJoCAAAAAkvEW8NnDtdNtDpsmze+Ht2LH35IJcKv00jKAlUs21RrAwAAAAD/////S8Rbw2cO1020OmybN74e3Ysffkglwq/TSMoCVSzbVGsBAAAAAP7///8CwLYClQAAAAAWABSNJKzjaUb3uOxixsvh1GGE3fW7zQD5ApUAAAAAFgAUKNw0x8HRctAgmvoevm4u1SbN7XIAAAAAAAEAnQIAAAACczMa321tVHuN4GKWKRncycI22aX3uXgwSFUKM2orjRsBAAAAAP7///9zMxrfbW1Ue43gYpYpGdzJwjbZpfe5eDBIVQozaiuNGwAAAAAA/v///wIA+QKVAAAAABl2qRT9zXUVA8Ls5iVqynLHe5/vSe1XyYisQM0ClQAAAAAWABRmWQUcjSjghQ8/uH4Bn/zkakwLtAAAAAAAAQEfQM0ClQAAAAAWABRmWQUcjSjghQ8/uH4Bn/zkakwLtAAAAA==')

        self.log.info("Test that we can fund psbts with external inputs specified")

        privkey, _ = generate_keypair(wif=True)

        self.nodes[1].createwallet("extfund")
        wallet = self.nodes[1].get_wallet_rpc("extfund")

        # Make a weird but signable script. sh(wsh(pkh())) descriptor accomplishes this
        desc = descsum_create("sh(wsh(pkh({})))".format(privkey))
        if self.options.descriptors:
            res = self.nodes[0].importdescriptors([{"desc": desc, "timestamp": "now"}])
        else:
            res = self.nodes[0].importmulti([{"desc": desc, "timestamp": "now"}])
        assert res[0]["success"]
        addr = self.nodes[0].deriveaddresses(desc)[0]
        addr_info = self.nodes[0].getaddressinfo(addr)

        self.nodes[0].sendtoaddress(addr, 10)
        self.nodes[0].sendtoaddress(wallet.getnewaddress(), 10)
        self.generate(self.nodes[0], 6)
        ext_utxo = self.nodes[0].listunspent(addresses=[addr])[0]

        # An external input without solving data should result in an error
        assert_raises_rpc_error(-4, "Not solvable pre-selected input COutPoint(%s, %s)" % (ext_utxo["txid"][0:10], ext_utxo["vout"]), wallet.walletcreatefundedpsbt, [ext_utxo], {self.nodes[0].getnewaddress(): 15})

        # But funding should work when the solving data is provided
        psbt = wallet.walletcreatefundedpsbt([ext_utxo], {self.nodes[0].getnewaddress(): 15}, 0, {"add_inputs": True, "solving_data": {"pubkeys": [addr_info['pubkey']], "scripts": [addr_info["embedded"]["scriptPubKey"], addr_info["embedded"]["embedded"]["scriptPubKey"]]}})
        signed = wallet.walletprocesspsbt(psbt['psbt'])
        assert not signed['complete']
        signed = self.nodes[0].walletprocesspsbt(signed['psbt'])
        assert signed['complete']

        psbt = wallet.walletcreatefundedpsbt([ext_utxo], {self.nodes[0].getnewaddress(): 15}, 0, {"add_inputs": True, "solving_data":{"descriptors": [desc]}})
        signed = wallet.walletprocesspsbt(psbt['psbt'])
        assert not signed['complete']
        signed = self.nodes[0].walletprocesspsbt(signed['psbt'])
        assert signed['complete']
        final = signed['hex']

        dec = self.nodes[0].decodepsbt(signed["psbt"])
        for i, txin in enumerate(dec["tx"]["vin"]):
            if txin["txid"] == ext_utxo["txid"] and txin["vout"] == ext_utxo["vout"]:
                input_idx = i
                break
        psbt_in = dec["inputs"][input_idx]
        # Calculate the input weight
        # (prevout + sequence + length of scriptSig + scriptsig + 1 byte buffer) * WITNESS_SCALE_FACTOR + num scriptWitness stack items + (length of stack item + stack item) * N stack items + 1 byte buffer
        len_scriptsig = len(psbt_in["final_scriptSig"]["hex"]) // 2 if "final_scriptSig" in psbt_in else 0
        len_scriptsig += len(ser_compact_size(len_scriptsig)) + 1
        len_scriptwitness = (sum([(len(x) // 2) + len(ser_compact_size(len(x) // 2)) for x in psbt_in["final_scriptwitness"]]) + len(psbt_in["final_scriptwitness"]) + 1) if "final_scriptwitness" in psbt_in else 0
        input_weight = ((40 + len_scriptsig) * WITNESS_SCALE_FACTOR) + len_scriptwitness
        low_input_weight = input_weight // 2
        high_input_weight = input_weight * 2

        # Input weight error conditions
        assert_raises_rpc_error(
            -8,
            "Input weights should be specified in inputs rather than in options.",
            wallet.walletcreatefundedpsbt,
            inputs=[ext_utxo],
            outputs={self.nodes[0].getnewaddress(): 15},
            options={"input_weights": [{"txid": ext_utxo["txid"], "vout": ext_utxo["vout"], "weight": 1000}]}
        )

        # Funding should also work if the input weight is provided
        psbt = wallet.walletcreatefundedpsbt(
            inputs=[{"txid": ext_utxo["txid"], "vout": ext_utxo["vout"], "weight": input_weight}],
            outputs={self.nodes[0].getnewaddress(): 15},
            add_inputs=True,
        )
        signed = wallet.walletprocesspsbt(psbt["psbt"])
        signed = self.nodes[0].walletprocesspsbt(signed["psbt"])
        final = signed["hex"]
        assert self.nodes[0].testmempoolaccept([final])[0]["allowed"]
        # Reducing the weight should have a lower fee
        psbt2 = wallet.walletcreatefundedpsbt(
            inputs=[{"txid": ext_utxo["txid"], "vout": ext_utxo["vout"], "weight": low_input_weight}],
            outputs={self.nodes[0].getnewaddress(): 15},
            add_inputs=True,
        )
        assert_greater_than(psbt["fee"], psbt2["fee"])
        # Increasing the weight should have a higher fee
        psbt2 = wallet.walletcreatefundedpsbt(
            inputs=[{"txid": ext_utxo["txid"], "vout": ext_utxo["vout"], "weight": high_input_weight}],
            outputs={self.nodes[0].getnewaddress(): 15},
            add_inputs=True,
        )
        assert_greater_than(psbt2["fee"], psbt["fee"])
        # The provided weight should override the calculated weight when solving data is provided
        psbt3 = wallet.walletcreatefundedpsbt(
            inputs=[{"txid": ext_utxo["txid"], "vout": ext_utxo["vout"], "weight": high_input_weight}],
            outputs={self.nodes[0].getnewaddress(): 15},
            add_inputs=True, solving_data={"descriptors": [desc]},
        )
        # FirstIslamicCoin: this can legitimately differ from psbt2 by a tiny, expected
        # margin, not a bug. ext_utxo's real script is sh(wsh(pkh(...))) (segwit). Whether
        # the wallet's fee *estimate* accounts for that is separate from the per-input
        # "weight" override tested here: CalculateMaximumSignedTxSize() (src/wallet/spend.cpp,
        # inherited unmodified from upstream) decides the whole transaction is segwit by
        # trying to infer a descriptor for every input's scriptPubKey, and once any input is
        # segwit, upstream's own logic adds the 2-weight-unit marker/flag plus one witness-
        # stack-length byte per *other*, non-segwit input -- on top of, not instead of, the
        # explicit weight override for ext_utxo itself. Without solving_data (psbt2), the
        # wallet cannot infer ext_utxo's descriptor and so cannot tell it is segwit, so it
        # only ever sees this as a non-segwit tx (all of this fork's own funding inputs are
        # legacy P2PKH, since DEFAULT_ADDRESS_TYPE here is legacy, inherited from CodexaCoin).
        # With solving_data (psbt3), the wallet correctly detects the segwit script and adds
        # that small, genuine accounting overhead. Upstream's own wallet defaults to bech32
        # addresses, so its funding input is already segwit either way and this never comes
        # up there -- it's specific to this fork's legacy default, not a new bug in the PSBT
        # or fee-estimation code itself. psbt3's fee should therefore be >= psbt2's, and only
        # by the tiny margin that overhead accounts for (well under 1000 sat here).
        assert_greater_than_or_equal(psbt3["fee"], psbt2["fee"])
        assert_greater_than_or_equal(psbt2["fee"] + Decimal("0.00001"), psbt3["fee"])

        # Import the external utxo descriptor so that we can sign for it from the test wallet
        if self.options.descriptors:
            res = wallet.importdescriptors([{"desc": desc, "timestamp": "now"}])
        else:
            res = wallet.importmulti([{"desc": desc, "timestamp": "now"}])
        assert res[0]["success"]
        # The provided weight should override the calculated weight for a wallet input
        psbt3 = wallet.walletcreatefundedpsbt(
            inputs=[{"txid": ext_utxo["txid"], "vout": ext_utxo["vout"], "weight": high_input_weight}],
            outputs={self.nodes[0].getnewaddress(): 15},
            add_inputs=True,
        )
        # FirstIslamicCoin: same small, expected margin as above and for the same reason --
        # the wallet now owns ext_utxo's descriptor (just imported), so it can infer it is
        # segwit even without solving_data being passed to this call, while psbt2 (built
        # before the import, with no solving_data either) still could not. See the detailed
        # comment on the first psbt2/psbt3 fee comparison above.
        assert_greater_than_or_equal(psbt3["fee"], psbt2["fee"])
        assert_greater_than_or_equal(psbt2["fee"] + Decimal("0.00001"), psbt3["fee"])

        self.log.info("Test signing inputs that the wallet has keys for but is not watching the scripts")
        self.nodes[1].createwallet(wallet_name="scriptwatchonly", disable_private_keys=True)
        watchonly = self.nodes[1].get_wallet_rpc("scriptwatchonly")

        privkey, pubkey = generate_keypair(wif=True)

        desc = descsum_create("wsh(pkh({}))".format(pubkey.hex()))
        if self.options.descriptors:
            res = watchonly.importdescriptors([{"desc": desc, "timestamp": "now"}])
        else:
            res = watchonly.importmulti([{"desc": desc, "timestamp": "now"}])
        assert res[0]["success"]
        addr = self.nodes[0].deriveaddresses(desc)[0]
        self.nodes[0].sendtoaddress(addr, 10)
        self.generate(self.nodes[0], 1)
        self.nodes[0].importprivkey(privkey)

        psbt = watchonly.sendall([wallet.getnewaddress()])["psbt"]
        signed_tx = self.nodes[0].walletprocesspsbt(psbt)
        self.nodes[0].sendrawtransaction(signed_tx["hex"])

        # Same test but for taproot
        if self.options.descriptors:
            privkey, pubkey = generate_keypair(wif=True)

            desc = descsum_create("tr({},pk({}))".format(H_POINT, pubkey.hex()))
            res = watchonly.importdescriptors([{"desc": desc, "timestamp": "now"}])
            assert res[0]["success"]
            addr = self.nodes[0].deriveaddresses(desc)[0]
            self.nodes[0].sendtoaddress(addr, 10)
            self.generate(self.nodes[0], 1)
            self.nodes[0].importdescriptors([{"desc": descsum_create("tr({})".format(privkey)), "timestamp":"now"}])

            psbt = watchonly.sendall([wallet.getnewaddress(), addr])["psbt"]
            processed_psbt = self.nodes[0].walletprocesspsbt(psbt)
            txid = self.nodes[0].sendrawtransaction(processed_psbt["hex"])
            vout = find_vout_for_address(self.nodes[0], txid, addr)

            # Make sure tap tree is in psbt
            parsed_psbt = PSBT.from_base64(psbt)
            assert_greater_than(len(parsed_psbt.o[vout].map[PSBT_OUT_TAP_TREE]), 0)
            assert "taproot_tree" in self.nodes[0].decodepsbt(psbt)["outputs"][vout]
            parsed_psbt.make_blank()
            comb_psbt = self.nodes[0].combinepsbt([psbt, parsed_psbt.to_base64()])
            assert_equal(comb_psbt, psbt)

            self.log.info("Test that walletprocesspsbt both updates and signs a non-updated psbt containing Taproot inputs")
            addr = self.nodes[0].getnewaddress("", "bech32m")
            txid = self.nodes[0].sendtoaddress(addr, 1)
            vout = find_vout_for_address(self.nodes[0], txid, addr)
            # FirstIslamicCoin: same fee-floor bump as test_utxo_conversion()
            # above -- 0.9999 (10000 sat fee) is below this fork's 100 sat/vB
            # consensus floor for a tx this size.
            psbt = self.nodes[0].createpsbt([{"txid": txid, "vout": vout}], [{self.nodes[0].getnewaddress(): 0.999}])
            signed = self.nodes[0].walletprocesspsbt(psbt)
            rawtx = signed["hex"]
            self.nodes[0].sendrawtransaction(rawtx)
            self.generate(self.nodes[0], 1)

            # Make sure tap tree is not in psbt
            parsed_psbt = PSBT.from_base64(psbt)
            assert PSBT_OUT_TAP_TREE not in parsed_psbt.o[0].map
            assert "taproot_tree" not in self.nodes[0].decodepsbt(psbt)["outputs"][0]
            parsed_psbt.make_blank()
            comb_psbt = self.nodes[0].combinepsbt([psbt, parsed_psbt.to_base64()])
            assert_equal(comb_psbt, psbt)

        self.log.info("Test walletprocesspsbt raises if an invalid sighashtype is passed")
        assert_raises_rpc_error(-8, "'all' is not a valid sighash parameter.", self.nodes[0].walletprocesspsbt, psbt, sighashtype="all")

        self.log.info("Test decoding PSBT with per-input preimage types")
        # note that the decodepsbt RPC doesn't check whether preimages and hashes match
        hash_ripemd160, preimage_ripemd160 = random_bytes(20), random_bytes(50)
        hash_sha256, preimage_sha256 = random_bytes(32), random_bytes(50)
        hash_hash160, preimage_hash160 = random_bytes(20), random_bytes(50)
        hash_hash256, preimage_hash256 = random_bytes(32), random_bytes(50)

        tx = CTransaction()
        tx.vin = [CTxIn(outpoint=COutPoint(hash=int('aa' * 32, 16), n=0), scriptSig=b""),
                  CTxIn(outpoint=COutPoint(hash=int('bb' * 32, 16), n=0), scriptSig=b""),
                  CTxIn(outpoint=COutPoint(hash=int('cc' * 32, 16), n=0), scriptSig=b""),
                  CTxIn(outpoint=COutPoint(hash=int('dd' * 32, 16), n=0), scriptSig=b"")]
        tx.vout = [CTxOut(nValue=0, scriptPubKey=b"")]
        psbt = PSBT()
        psbt.g = PSBTMap({PSBT_GLOBAL_UNSIGNED_TX: tx.serialize()})
        psbt.i = [PSBTMap({bytes([PSBT_IN_RIPEMD160]) + hash_ripemd160: preimage_ripemd160}),
                  PSBTMap({bytes([PSBT_IN_SHA256]) + hash_sha256: preimage_sha256}),
                  PSBTMap({bytes([PSBT_IN_HASH160]) + hash_hash160: preimage_hash160}),
                  PSBTMap({bytes([PSBT_IN_HASH256]) + hash_hash256: preimage_hash256})]
        psbt.o = [PSBTMap()]
        res_inputs = self.nodes[0].decodepsbt(psbt.to_base64())["inputs"]
        assert_equal(len(res_inputs), 4)
        preimage_keys = ["ripemd160_preimages", "sha256_preimages", "hash160_preimages", "hash256_preimages"]
        expected_hashes = [hash_ripemd160, hash_sha256, hash_hash160, hash_hash256]
        expected_preimages = [preimage_ripemd160, preimage_sha256, preimage_hash160, preimage_hash256]
        for res_input, preimage_key, hash, preimage in zip(res_inputs, preimage_keys, expected_hashes, expected_preimages):
            assert preimage_key in res_input
            assert_equal(len(res_input[preimage_key]), 1)
            assert hash.hex() in res_input[preimage_key]
            assert_equal(res_input[preimage_key][hash.hex()], preimage.hex())

        self.log.info("Test that combining PSBTs with different transactions fails")
        tx = CTransaction()
        tx.vin = [CTxIn(outpoint=COutPoint(hash=int('aa' * 32, 16), n=0), scriptSig=b"")]
        tx.vout = [CTxOut(nValue=0, scriptPubKey=b"")]
        psbt1 = PSBT(g=PSBTMap({PSBT_GLOBAL_UNSIGNED_TX: tx.serialize()}), i=[PSBTMap()], o=[PSBTMap()]).to_base64()
        tx.vout[0].nValue += 1  # slightly modify tx
        psbt2 = PSBT(g=PSBTMap({PSBT_GLOBAL_UNSIGNED_TX: tx.serialize()}), i=[PSBTMap()], o=[PSBTMap()]).to_base64()
        assert_raises_rpc_error(-8, "PSBTs not compatible (different transactions)", self.nodes[0].combinepsbt, [psbt1, psbt2])
        assert_equal(self.nodes[0].combinepsbt([psbt1, psbt1]), psbt1)

        self.log.info("Test that PSBT inputs are being checked via script execution")
        acs_prevout = CTxOut(nValue=0, scriptPubKey=CScript([OP_TRUE]))
        tx = CTransaction()
        tx.vin = [CTxIn(outpoint=COutPoint(hash=int('dd' * 32, 16), n=0), scriptSig=b"")]
        tx.vout = [CTxOut(nValue=0, scriptPubKey=b"")]
        psbt = PSBT()
        psbt.g = PSBTMap({PSBT_GLOBAL_UNSIGNED_TX: tx.serialize()})
        psbt.i = [PSBTMap({bytes([PSBT_IN_WITNESS_UTXO]) : acs_prevout.serialize()})]
        psbt.o = [PSBTMap()]
        assert_equal(self.nodes[0].finalizepsbt(psbt.to_base64()),
            {'hex': '0200000001dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd0000000000000000000100000000000000000000000000', 'complete': True})

        self.log.info("Test we don't crash when making a 0-value funded transaction at 0 fee without forcing an input selection")
        assert_raises_rpc_error(-4, "Transaction requires one destination of non-0 value, a non-0 feerate, or a pre-selected input", self.nodes[0].walletcreatefundedpsbt, [], [{"data": "deadbeef"}], 0, {"fee_rate": "0"})

        self.log.info("Test descriptorprocesspsbt updates and signs a psbt with descriptors")

        self.generate(self.nodes[2], 1)

        # Disable the wallet for node 2 since `descriptorprocesspsbt` does not use the wallet
        self.restart_node(2, extra_args=["-disablewallet"])
        self.connect_nodes(0, 2)
        self.connect_nodes(1, 2)

        key_info = get_generate_key()
        key = key_info.privkey
        address = key_info.p2wpkh_addr

        descriptor = descsum_create(f"wpkh({key})")

        txid = self.nodes[0].sendtoaddress(address, 1)
        self.sync_all()
        vout = find_output(self.nodes[0], txid, 1)

        # FirstIslamicCoin: upstream leaves a flat 0.00001 (1000 sat) fee here, which clears
        # upstream's minrelaytxfee but not this fork's real minimum-fee floor (a fixed
        # 100 sat/vB, `GetMinFee()`; see test_framework/fic.py's get_min_fee_sat()) for even
        # this small single-input, single-output tx. Leave a fee comfortably above the floor
        # instead (vsize estimate padded well past this tx's real ~110-140 vbytes).
        fee = Decimal(get_min_fee_sat(300)) / Decimal(10**8)
        psbt = self.nodes[2].createpsbt([{"txid": txid, "vout": vout}], {self.nodes[0].getnewaddress(): Decimal("1") - fee})
        decoded = self.nodes[2].decodepsbt(psbt)
        test_psbt_input_keys(decoded['inputs'][0], [])

        # Test that even if the wrong descriptor is given, `witness_utxo` and `non_witness_utxo`
        # are still added to the psbt
        alt_descriptor = descsum_create(f"wpkh({get_generate_key().privkey})")
        alt_psbt = self.nodes[2].descriptorprocesspsbt(psbt=psbt, descriptors=[alt_descriptor], sighashtype="ALL")["psbt"]
        decoded = self.nodes[2].decodepsbt(alt_psbt)
        test_psbt_input_keys(decoded['inputs'][0], ['witness_utxo', 'non_witness_utxo'])

        # Test that the psbt is not finalized and does not have bip32_derivs unless specified
        processed_psbt = self.nodes[2].descriptorprocesspsbt(psbt=psbt, descriptors=[descriptor], sighashtype="ALL", bip32derivs=True, finalize=False)
        decoded = self.nodes[2].decodepsbt(processed_psbt['psbt'])
        test_psbt_input_keys(decoded['inputs'][0], ['witness_utxo', 'non_witness_utxo', 'partial_signatures', 'bip32_derivs'])

        # If psbt not finalized, test that result does not have hex
        assert "hex" not in processed_psbt

        processed_psbt = self.nodes[2].descriptorprocesspsbt(psbt=psbt, descriptors=[descriptor], sighashtype="ALL", bip32derivs=False, finalize=True)
        decoded = self.nodes[2].decodepsbt(processed_psbt['psbt'])
        test_psbt_input_keys(decoded['inputs'][0], ['witness_utxo', 'non_witness_utxo', 'final_scriptwitness'])

        # Test psbt is complete
        assert_equal(processed_psbt['complete'], True)

        # Broadcast transaction
        self.nodes[2].sendrawtransaction(processed_psbt['hex'])

        self.log.info("Test descriptorprocesspsbt raises if an invalid sighashtype is passed")
        assert_raises_rpc_error(-8, "'all' is not a valid sighash parameter.", self.nodes[2].descriptorprocesspsbt, psbt, [descriptor], sighashtype="all")


if __name__ == '__main__':
    PSBTTest().main()

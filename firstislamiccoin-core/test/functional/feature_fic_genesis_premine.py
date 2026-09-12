#!/usr/bin/env python3
# Copyright (c) 2026 The FirstIslamicCoin developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""The genesis premine, and a chain that is proof-of-stake from block 1.

Runs regtest with -lastpowblock=0, reproducing mainnet's rules:

- the genesis coinbase carries the whole 14,000,000,000 premine as 1,000
  equal outputs, and they are in the UTXO set;
- the genesis transaction can be looked up, and its outputs spent at once;
- no proof-of-work block is accepted, ever;
- the chain is started, and kept going, by staking genesis outputs -- there
  is no stall while the first coinstake outputs mature;
- supply is exactly premine + 10 per block.
"""

from test_framework.fic import (
    GENESIS_OUTPUT_VALUE,
    GENESIS_OUTPUTS,
    POS_FROM_GENESIS_ARGS,
    PREMINE,
    REGTEST_GENESIS_ADDRESS,
    STAKE_REWARD,
    block_fees,
    coinstake_mint,
    import_genesis_key,
)
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import (
    assert_equal,
    assert_raises_rpc_error,
)

MATURITY = 10  # regtest nCoinbaseMaturity


class GenesisPremineTest(BitcoinTestFramework):
    def add_options(self, parser):
        self.add_wallet_options(parser)

    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 1
        self.extra_args = [POS_FROM_GENESIS_ARGS + ["-staking=0"]]

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def run_test(self):
        node = self.nodes[0]
        assert_equal(node.getblockcount(), 0)

        self.log.info("Genesis coinbase carries the premine as spendable outputs")
        genesis = node.getblock(node.getblockhash(0), 2)
        coinbase = genesis["tx"][0]
        assert_equal(len(coinbase["vout"]), GENESIS_OUTPUTS)
        for vout in coinbase["vout"]:
            assert_equal(vout["value"], GENESIS_OUTPUT_VALUE)
            assert_equal(vout["scriptPubKey"]["address"], REGTEST_GENESIS_ADDRESS)
        utxos = node.gettxoutsetinfo()
        assert_equal(utxos["total_amount"], PREMINE)
        assert_equal(utxos["txouts"], GENESIS_OUTPUTS)

        self.log.info("The genesis transaction is indexed and retrievable")
        self.wait_until(lambda: node.getindexinfo("txindex")["txindex"]["synced"])
        assert_equal(node.getrawtransaction(coinbase["txid"], True)["blockhash"], genesis["hash"])

        self.log.info("Proof-of-work is rejected from block 1")
        assert_raises_rpc_error(-1, "reject-pow", node.generatetoaddress, 1, node.getnewaddress(), invalid_call=False)
        assert_equal(node.getblockcount(), 0)

        self.log.info("The premine key's wallet sees it as mature, spendable balance")
        import_genesis_key(node, self.options.descriptors)
        balances = node.getbalances()["mine"]
        assert_equal(balances["trusted"], PREMINE)
        assert_equal(balances["immature"], 0)

        self.log.info("A genesis output can be spent before any block is staked")
        spend_txid = node.sendtoaddress(node.getnewaddress(), 1000)
        assert spend_txid in node.getrawmempool()

        self.log.info(f"Staking produces the chain from genesis outputs, past the {MATURITY}-block maturity window")
        self.restart_node(0, extra_args=POS_FROM_GENESIS_ARGS + ["-staking=1"])
        target = MATURITY + 2
        self.wait_until(lambda: node.getblockcount() >= target, timeout=900)
        height = node.getblockcount()

        spend_confirmed = False
        for h in range(1, height + 1):
            block = node.getblock(node.getblockhash(h), 3)
            assert_equal(block["flags"], "proof-of-stake")
            coinstake = block["tx"][1]
            kernel = coinstake["vin"][0]
            if h <= MATURITY:
                # Nothing but a genesis output can be mature yet.
                assert_equal(kernel["txid"], coinbase["txid"])
            assert_equal(coinstake_mint(block), STAKE_REWARD + block_fees(block))
            spend_confirmed |= any(tx["txid"] == spend_txid for tx in block["tx"])
        assert spend_confirmed, "the genesis spend should have been included in a staked block"

        self.log.info("Supply is exactly the premine plus the fixed reward per block")
        assert_equal(node.gettxoutsetinfo()["total_amount"], PREMINE + STAKE_REWARD * height)


if __name__ == "__main__":
    GenesisPremineTest().main()

#!/usr/bin/env python3
# Copyright (c) 2015-2022 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test BIP65 (CHECKLOCKTIMEVERIFY).

Test that the CHECKLOCKTIMEVERIFY soft-fork activates.
"""

from test_framework.blocktools import (
    TIME_GENESIS_BLOCK,
    create_block,
    create_coinbase,
)
from test_framework.messages import (
    CTransaction,
    SEQUENCE_FINAL,
    msg_block,
)
from test_framework.p2p import P2PInterface
from test_framework.script import (
    CScript,
    CScriptNum,
    OP_1NEGATE,
    OP_CHECKLOCKTIMEVERIFY,
    OP_DROP,
)
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import assert_equal
from test_framework.wallet import (
    MiniWallet,
    MiniWalletMode,
)


# Helper function to modify a transaction by
# 1) prepending a given script to the scriptSig of vin 0 and
# 2) (optionally) modify the nSequence of vin 0 and the tx's nLockTime
def cltv_modify_tx(tx, prepend_scriptsig, nsequence=None, nlocktime=None):
    assert_equal(len(tx.vin), 1)
    if nsequence is not None:
        tx.vin[0].nSequence = nsequence
        tx.nLockTime = nlocktime

    tx.vin[0].scriptSig = CScript(prepend_scriptsig + list(CScript(tx.vin[0].scriptSig)))
    tx.rehash()


def cltv_invalidate(tx, failure_reason):
    # Modify the signature in vin 0 and nSequence/nLockTime of the tx to fail CLTV
    #
    # According to BIP65, OP_CHECKLOCKTIMEVERIFY can fail due the following reasons:
    # 1) the stack is empty
    # 2) the top item on the stack is less than 0
    # 3) the lock-time type (height vs. timestamp) of the top stack item and the
    #    nLockTime field are not the same
    # 4) the top stack item is greater than the transaction's nLockTime field
    # 5) the nSequence field of the txin is 0xffffffff (SEQUENCE_FINAL)
    assert failure_reason in range(5)
    scheme = [
        # | Script to prepend to scriptSig                  | nSequence  | nLockTime    |
        # +-------------------------------------------------+------------+--------------+
        [[OP_CHECKLOCKTIMEVERIFY],                            None,       None],
        [[OP_1NEGATE, OP_CHECKLOCKTIMEVERIFY, OP_DROP],       None,       None],
        [[CScriptNum(100), OP_CHECKLOCKTIMEVERIFY, OP_DROP],  0,          TIME_GENESIS_BLOCK],
        [[CScriptNum(100), OP_CHECKLOCKTIMEVERIFY, OP_DROP],  0,          50],
        [[CScriptNum(50),  OP_CHECKLOCKTIMEVERIFY, OP_DROP],  SEQUENCE_FINAL, 50],
    ][failure_reason]

    cltv_modify_tx(tx, prepend_scriptsig=scheme[0], nsequence=scheme[1], nlocktime=scheme[2])


def cltv_validate(tx, height):
    # Modify the signature in vin 0 and nSequence/nLockTime of the tx to pass CLTV
    scheme = [[CScriptNum(height), OP_CHECKLOCKTIMEVERIFY, OP_DROP], 0, height]

    cltv_modify_tx(tx, prepend_scriptsig=scheme[0], nsequence=scheme[1], nlocktime=scheme[2])


CLTV_HEIGHT = 111
# FirstIslamicCoin: CheckBlockHeader rejects blocks with nVersion < 7 (bad-version, src/validation.cpp)
MIN_BLOCK_VERSION = 7


class BIP65Test(BitcoinTestFramework):
    def set_test_params(self):
        self.num_nodes = 1
        self.extra_args = [[
            '-whitelist=noban@127.0.0.1',
            '-par=1',  # Use only one script thread to get the exact reject reason for testing
            '-acceptnonstdtxn=1',  # cltv_invalidate is nonstandard
        ]]
        self.setup_clean_chain = True
        self.rpc_timeout = 480

    def test_cltv_info(self, *, is_active):
        # FirstIslamicCoin: assume that CLTV is always active
        pass

    def run_test(self):
        peer = self.nodes[0].add_p2p_connection(P2PInterface())
        wallet = MiniWallet(self.nodes[0], mode=MiniWalletMode.RAW_OP_TRUE)

        self.test_cltv_info(is_active=False)

        self.log.info("Mining %d blocks", CLTV_HEIGHT - 2)
        self.generate(wallet, 10)
        self.generate(self.nodes[0], CLTV_HEIGHT - 2 - 10)
        assert_equal(self.nodes[0].getblockcount(), CLTV_HEIGHT - 2)

        # FirstIslamicCoin: CHECKLOCKTIMEVERIFY is enforced for every block timestamped after nProtocolV3Time
        # (2015, see GetBlockScriptFlags in src/validation.cpp), so unlike Bitcoin there is no pre-activation
        # window: invalid-according-to-CLTV transactions are rejected below CLTV_HEIGHT as well.
        self.log.info("Test that invalid-according-to-CLTV transactions cannot appear in a block below CLTV_HEIGHT")

        # create one invalid tx per CLTV failure reason (5 in total) and collect them
        invalid_cltv_txs = []
        for i in range(5):
            spendtx = wallet.create_self_transfer()['tx']
            cltv_invalidate(spendtx, i)
            invalid_cltv_txs.append(spendtx)

        tip = self.nodes[0].getbestblockhash()
        block_time = self.nodes[0].getblockheader(tip)['mediantime'] + 1
        block = create_block(int(tip, 16), create_coinbase(CLTV_HEIGHT - 1), block_time, version=MIN_BLOCK_VERSION, txlist=invalid_cltv_txs)
        block.solve()

        self.test_cltv_info(is_active=True)
        with self.nodes[0].assert_debug_log(expected_msgs=[f'CheckInputScripts on {invalid_cltv_txs[0].hash} failed with mandatory-script-verify-flag-failed']):
            peer.send_and_ping(msg_block(block))
        assert_equal(self.nodes[0].getbestblockhash(), tip)

        # Mine a regular block to reach CLTV_HEIGHT - 1
        self.generate(self.nodes[0], 1)
        assert_equal(self.nodes[0].getblockcount(), CLTV_HEIGHT - 1)

        self.log.info("Test that blocks must be at least version %d", MIN_BLOCK_VERSION)
        tip_hash = self.nodes[0].getbestblockhash()
        tip = int(tip_hash, 16)
        block_time = self.nodes[0].getblockheader(tip_hash)['time'] + 1
        block = create_block(tip, create_coinbase(CLTV_HEIGHT), block_time, version=MIN_BLOCK_VERSION - 1)
        block.solve()

        # FirstIslamicCoin: for nVersion <= 6 the node identifies the block by its scrypt hash
        # (CBlockHeader::GetHash in src/primitives/block.cpp), so match on the reject reason only.
        with self.nodes[0].assert_debug_log(expected_msgs=['bad-version, bad block version']):
            peer.send_and_ping(msg_block(block))
            assert_equal(int(self.nodes[0].getbestblockhash(), 16), tip)
            peer.sync_with_ping()

        self.log.info("Test that invalid-according-to-CLTV transactions cannot appear in a block")
        block.nVersion = MIN_BLOCK_VERSION
        block.vtx.append(CTransaction()) # dummy tx after coinbase that will be replaced later

        # create and test one invalid tx per CLTV failure reason (5 in total)
        for i in range(5):
            spendtx = wallet.create_self_transfer()['tx']
            cltv_invalidate(spendtx, i)

            expected_cltv_reject_reason = [
                "mandatory-script-verify-flag-failed (Operation not valid with the current stack size)",
                "mandatory-script-verify-flag-failed (Negative locktime)",
                "mandatory-script-verify-flag-failed (Locktime requirement not satisfied)",
                "mandatory-script-verify-flag-failed (Locktime requirement not satisfied)",
                "mandatory-script-verify-flag-failed (Locktime requirement not satisfied)",
            ][i]
            # First we show that this tx is valid except for CLTV by getting it
            # rejected from the mempool for exactly that reason.
            assert_equal(
                [{
                    'txid': spendtx.hash,
                    'wtxid': spendtx.getwtxid(),
                    'allowed': False,
                    'reject-reason': expected_cltv_reject_reason,
                }],
                self.nodes[0].testmempoolaccept(rawtxs=[spendtx.serialize().hex()], maxfeerate=0),
            )

            # Now we verify that a block with this transaction is also invalid.
            block.vtx[1] = spendtx
            block.hashMerkleRoot = block.calc_merkle_root()
            block.solve()

            with self.nodes[0].assert_debug_log(expected_msgs=[f'CheckInputScripts on {block.vtx[-1].hash} failed with {expected_cltv_reject_reason}']):
                peer.send_and_ping(msg_block(block))
                assert_equal(int(self.nodes[0].getbestblockhash(), 16), tip)
                peer.sync_with_ping()

        self.log.info("Test that a version %d block with a valid-according-to-CLTV transaction is accepted", MIN_BLOCK_VERSION)
        cltv_validate(spendtx, CLTV_HEIGHT - 1)

        block.vtx.pop(1)
        block.vtx.append(spendtx)
        block.hashMerkleRoot = block.calc_merkle_root()
        block.solve()

        self.test_cltv_info(is_active=True)  # Not active as of current tip, but next block must obey rules
        peer.send_and_ping(msg_block(block))
        self.test_cltv_info(is_active=True)  # Active as of current tip
        assert_equal(int(self.nodes[0].getbestblockhash(), 16), block.sha256)


if __name__ == '__main__':
    BIP65Test().main()

#!/usr/bin/env python3
# Copyright (c) 2020-2022 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test orphaned block rewards in the wallet."""

from test_framework.blocktools import COINBASE_MATURITY
from test_framework.fic import POW_BLOCK_REWARD
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import assert_equal

class OrphanedBlockRewardTest(BitcoinTestFramework):
    def add_options(self, parser):
        self.add_wallet_options(parser)

    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 2

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def run_test(self):
        # Generate some blocks and obtain some coins on node 0.  We send
        # some balance to node 1, which will hold it as a single coin.
        self.generate(self.nodes[0], 150)
        self.nodes[0].sendtoaddress(self.nodes[1].getnewaddress(), 10)
        self.generate(self.nodes[0], 1)

        # Get a block reward with node 1 and remember the block so we can orphan
        # it later.
        self.sync_blocks()
        blk = self.generate(self.nodes[1], 1)[0]

        # Let the block reward mature and send coins including both
        # the existing balance and the block reward.
        # FirstIslamicCoin: regtest nMaxReorganizationDepth is 50
        # (kernel/chainparams.cpp; validation.cpp "older-than-maxreorg-depth"),
        # so only mine until the reward is mature to keep the reorgs shallow.
        self.generate(self.nodes[0], COINBASE_MATURITY + 1)
        assert_equal(self.nodes[1].getbalance(), 10 + POW_BLOCK_REWARD)
        pre_reorg_conf_bals = self.nodes[1].getbalances()
        # Send more than the block reward alone so that, as upstream intends,
        # both the existing coin and the reward are spent.
        txid = self.nodes[1].sendtoaddress(self.nodes[0].getnewaddress(), POW_BLOCK_REWARD + 5)
        orig_chain_tip = self.nodes[0].getbestblockhash()
        self.sync_mempools()

        # Orphan the block reward and make sure that the original coins
        # from the wallet can still be spent.
        # FirstIslamicCoin: peers reject fork headers timestamped before their
        # sync checkpoint (tip - nCoinbaseMaturity; validation.cpp
        # "older-than-checkpoint", BLOCK_HEADER_SYNC). These regtest blocks
        # were mined faster than their 1-second spacing, so their timestamps
        # run ahead of the clock; move time past the tip before forking.
        fork_time = self.nodes[0].getblockheader(orig_chain_tip)["time"] + 60
        for node in self.nodes:
            node.setmocktime(fork_time)
        self.nodes[0].invalidateblock(blk)
        blocks = self.generate(self.nodes[0], COINBASE_MATURITY + 3)  # one longer than the original chain
        conflict_block = blocks[0]
        # We expect the descendants of orphaned rewards to no longer be considered
        assert_equal(self.nodes[1].getbalances()["mine"], {
          "trusted": 10,
          "untrusted_pending": 0,
          "immature": 0,
        })
        # And the unconfirmed tx to be abandoned
        assert_equal(self.nodes[1].gettransaction(txid)["details"][0]["abandoned"], True)

        # The abandoning should persist through reloading
        self.nodes[1].unloadwallet(self.default_wallet_name)
        self.nodes[1].loadwallet(self.default_wallet_name)
        assert_equal(self.nodes[1].gettransaction(txid)["details"][0]["abandoned"], True)

        # If the orphaned reward is reorged back into the main chain, any unconfirmed
        # descendant txs at the time of the original reorg remain abandoned.
        fork_time = self.nodes[0].getblockheader(self.nodes[0].getbestblockhash())["time"] + 60
        for node in self.nodes:
            node.setmocktime(fork_time)  # see "older-than-checkpoint" above
        self.nodes[0].invalidateblock(conflict_block)
        self.nodes[0].reconsiderblock(blk)
        assert_equal(self.nodes[0].getbestblockhash(), orig_chain_tip)
        self.generate(self.nodes[0], 3)

        balances = self.nodes[1].getbalances()
        del balances["lastprocessedblock"]
        del pre_reorg_conf_bals["lastprocessedblock"]
        assert_equal(balances, pre_reorg_conf_bals)
        assert_equal(self.nodes[1].gettransaction(txid)["details"][0]["abandoned"], True)


if __name__ == '__main__':
    OrphanedBlockRewardTest().main()

#!/usr/bin/env python3
# Copyright (c) 2020-2022 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test orphaned block rewards in the wallet."""

from test_framework.fic import POW_BLOCK_REWARD
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import assert_equal

# FirstIslamicCoin: keep the reorg well inside the 10-block sync-checkpoint
# window explained below. 4 blocks (the reward block itself plus 3 mined on
# top of it) leaves more than half the window as margin.
BLOCKS_MINED_ON_TOP_OF_REWARD = 3

class OrphanedBlockRewardTest(BitcoinTestFramework):
    def add_options(self, parser):
        self.add_wallet_options(parser)

    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 2

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def run_test(self):
        # FirstIslamicCoin: this fork adds a Qtum/PPCoin-style "synchronized
        # checkpoint" anti-DoS rule that upstream Bitcoin doesn't have. In
        # ContextualCheckBlockHeader() (src/validation.cpp), every competing
        # header is checked against blockman.CheckSyncCheckpoint(), which
        # rejects it outright -- regardless of how much proof of work the
        # competing chain has -- if its height is at or below the receiving
        # peer's "sync checkpoint". That checkpoint is computed by
        # AutoSelectSyncCheckpoint() (src/node/blockstorage.cpp) as simply
        # (peer's own current tip height - nCoinbaseMaturity); on regtest
        # nCoinbaseMaturity is 10 (kernel/chainparams.cpp), so once a block is
        # 10+ blocks deep from a peer's tip, that peer can never accept a reorg
        # replacing it. There's a second, time-based sibling of this same
        # checkpoint (also keyed off nCoinbaseMaturity) at validation.cpp's
        # "older-than-checkpoint"/BLOCK_HEADER_SYNC check, which rejects a fork
        # block whose timestamp precedes the checkpoint block's -- regtest
        # blocks are typically mined faster than their 1-second spacing, so we
        # still need to push mocktime past the tip before forking (see
        # fork_time below) or that check trips first.
        #
        # nCoinbaseMaturity is *also* the number of confirmations a coinbase
        # output needs before it can be spent. Both checks use the exact same
        # constant, so a block reward becomes spendable at precisely the
        # moment its block becomes permanently un-reorgable -- there is no
        # window in which a reward can be both spent and later orphaned via
        # p2p sync between two nodes, so we cannot reproduce upstream's
        # original scenario (mature the reward, spend it combined with other
        # coins, then orphan the spend). Instead we keep the reorg shallow and
        # never let the reward mature, which also means it can never gain a
        # spendable descendant transaction (the wallet's coin selection
        # excludes immature coinbase outputs, and the network would reject any
        # attempt to spend one early regardless of the checkpoint). We instead
        # exercise, directly on the reward's own coinbase transaction:
        #   (a) the getbalances() immature/trusted/untrusted_pending breakdown
        #       correctly reacting to the reward's block being orphaned and
        #       later restored, and
        #   (b) CWallet::AddToWallet's "mark inactive coinbase and coinstake
        #       transactions ... as abandoned" logic (src/wallet/wallet.cpp),
        #       which automatically flags a coinbase transaction abandoned as
        #       soon as its block is disconnected. That flag is persisted to
        #       the wallet DB, which we check survives a wallet reload; we
        #       then restore the original chain and check the coinbase
        #       transaction correctly un-abandons once it is genuinely
        #       reconfirmed, so the checkpoint-driven reorg-and-back cycle
        #       leaves no stuck/residual bad wallet state.
        #
        # (Note: unlike a spending descendant, the reward's own coinbase
        # transaction *is* directly touched -- and its state reset to
        # Confirmed -- when its block is reconnected, so this last check
        # intentionally differs from upstream's "an abandoned descendant tx
        # stays abandoned even after the reorg is undone" assertion, which
        # relies on a wallet-known descendant transaction that is never itself
        # reconfirmed. There is no way to construct such a descendant here
        # without spending the still-immature reward.)
        self.generate(self.nodes[0], 150)
        self.nodes[0].sendtoaddress(self.nodes[1].getnewaddress(), 10)
        self.generate(self.nodes[0], 1)

        # Get a block reward with node 1 and remember the block (and its
        # coinbase txid) so we can orphan it later.
        self.sync_blocks()
        blk = self.generate(self.nodes[1], 1)[0]
        reward_txid = self.nodes[1].getblock(blk)["tx"][0]

        # Mine a few more blocks (still on the one shared chain, no fork yet)
        # so the eventual reorg has some real depth to it rather than being a
        # trivial "orphan the current tip" case.
        self.generate(self.nodes[0], BLOCKS_MINED_ON_TOP_OF_REWARD)

        pre_reorg_bals = self.nodes[1].getbalances()
        assert_equal(pre_reorg_bals["mine"]["trusted"], 10)
        assert_equal(pre_reorg_bals["mine"]["immature"], POW_BLOCK_REWARD)
        assert_equal(pre_reorg_bals["mine"]["untrusted_pending"], 0)
        assert_equal(self.nodes[1].gettransaction(reward_txid)["details"][0]["abandoned"], False)

        orig_chain_tip = self.nodes[0].getbestblockhash()

        # Orphan the block reward and make sure that the original coins
        # from the wallet can still be spent.
        # FirstIslamicCoin: peers reject fork headers timestamped before their
        # sync checkpoint (see the big comment above). These regtest blocks
        # were mined faster than their 1-second spacing, so their timestamps
        # run ahead of the clock; move time past the tip before forking.
        fork_time = self.nodes[0].getblockheader(orig_chain_tip)["time"] + 60
        for node in self.nodes:
            node.setmocktime(fork_time)
        self.nodes[0].invalidateblock(blk)
        # We invalidated (blk + BLOCKS_MINED_ON_TOP_OF_REWARD) blocks; mine a
        # couple more than that so the new chain is longer than the original.
        blocks = self.generate(self.nodes[0], BLOCKS_MINED_ON_TOP_OF_REWARD + 1 + 2)
        conflict_block = blocks[0]

        # The orphaned reward should no longer count as immature balance...
        assert_equal(self.nodes[1].getbalances()["mine"], {
          "trusted": 10,
          "untrusted_pending": 0,
          "immature": 0,
          "stake": 0,
        })
        # ...and its coinbase transaction should be marked abandoned.
        assert_equal(self.nodes[1].gettransaction(reward_txid)["details"][0]["abandoned"], True)

        # The abandoning should persist through reloading.
        self.nodes[1].unloadwallet(self.default_wallet_name)
        self.nodes[1].loadwallet(self.default_wallet_name)
        assert_equal(self.nodes[1].gettransaction(reward_txid)["details"][0]["abandoned"], True)

        # Restore the original chain (undoing the orphaning) and check that
        # doing so doesn't leave the wallet in a stuck or inconsistent state:
        # the reward's balance and abandoned status should both correctly
        # revert once it is genuinely reconfirmed.
        fork_time = self.nodes[0].getblockheader(self.nodes[0].getbestblockhash())["time"] + 60
        for node in self.nodes:
            node.setmocktime(fork_time)  # see "older-than-checkpoint" above
        self.nodes[0].invalidateblock(conflict_block)
        self.nodes[0].reconsiderblock(blk)
        assert_equal(self.nodes[0].getbestblockhash(), orig_chain_tip)
        self.generate(self.nodes[0], 3)

        balances = self.nodes[1].getbalances()
        del balances["lastprocessedblock"]
        del pre_reorg_bals["lastprocessedblock"]
        assert_equal(balances, pre_reorg_bals)
        assert_equal(self.nodes[1].gettransaction(reward_txid)["details"][0]["abandoned"], False)


if __name__ == '__main__':
    OrphanedBlockRewardTest().main()

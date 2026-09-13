#!/usr/bin/env python3
# Copyright (c) 2026 The FirstIslamicCoin developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test reorg handling across regtest's PoW window / PoS boundary.

Disconnects two nodes, lets each independently stake its own fork, then
reconnects them, to make sure DisconnectBlock/ConnectBlock cycles leave the
fixed-reward supply accounting exact on both sides.

Both nodes need their own spendable, matured balance to stake with -- node0
mines regtest's PoW window to its own wallet, then sends node1 a chunk of
funds and mines enough confirmations for it to mature (min stake age in
this codebase is a confirmation-depth check, nCoinbaseMaturity deep,
applied uniformly to any wallet UTXO -- see
wallet/staking.cpp::SelectCoinsForStaking) before disconnecting. Which
side's fork ends up "winning" after reconnect isn't asserted -- only that
both nodes converge to a single consistent tip and consistent supply.
"""

from decimal import Decimal

from test_framework.fic import PREMINE, STAKE_REWARD
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import assert_equal

PREMINE_WINDOW = 500
# The genesis premine (owned by neither node here) plus regtest's PoW window,
# 500 blocks x 28,000,000 -- a test-harness convenience that mainnet lacks.
SUPPLY_AFTER_POW_WINDOW = PREMINE + PREMINE_WINDOW * Decimal("28000000")
# Per-attempt kernel-hit probability scales with the input's amount (see
# pos.cpp::CheckStakeKernelHash -- kernel weight is amount-only, target is
# fixed on regtest since fPoSNoRetargeting=true). An earlier version of
# this test funded node1 with only 500M (~1/28th of node0's ~13.7B
# remaining balance) and node1 needed vastly more search-interval attempts
# than node0 to win a kernel -- confirmed via debug.log (88 attempts, ~23
# minutes, still nothing) before this was raised. Funding node1 with an
# amount on the same order of magnitude as node0's remaining balance keeps
# both nodes' staking latency comparable and the test's wall-clock time
# bounded.
NODE1_FUNDING = 7_000_000_000
CONFIRMATIONS_TO_MATURE = 15  # regtest nCoinbaseMaturity is 10; a little headroom


class PosReorgTest(BitcoinTestFramework):
    def add_options(self, parser):
        self.add_wallet_options(parser)

    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 2
        # Both nodes stake their own forks; the framework disables staking by
        # default (see util.write_config), so opt back in here.
        self.extra_args = [["-staking=1"]] * self.num_nodes

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def total_supply(self, node):
        return Decimal(str(node.gettxoutsetinfo()["total_amount"]))

    def run_test(self):
        node0, node1 = self.nodes

        # generatetoaddress always mines PoW, and PoW is only ever valid
        # for blocks 1..PREMINE_WINDOW (ContextualCheckBlockHeader rejects
        # it past that unconditionally -- confirmed by feature_premine.py).
        # So node1's funding transaction has to be sent and confirmed
        # *within* the premine window, not by mining extra blocks after
        # it: mine most of the window, send the funding tx, then mine the
        # rest of the window (which both completes the premine and gives
        # the funding tx its confirmations) in one continuous PoW mine.
        self.log.info(f"Mining the first {PREMINE_WINDOW - CONFIRMATIONS_TO_MATURE} premine blocks on node0")
        addr0 = node0.getnewaddress()
        self.generatetoaddress(node0, PREMINE_WINDOW - CONFIRMATIONS_TO_MATURE, addr0)

        self.log.info(f"Funding node1 with {NODE1_FUNDING} FIC so it has something of its own to stake")
        addr1 = node1.getnewaddress()
        node0.sendtoaddress(addr1, NODE1_FUNDING)

        self.log.info(f"Mining the remaining {CONFIRMATIONS_TO_MATURE} premine blocks (also confirms the funding tx)")
        self.generatetoaddress(node0, CONFIRMATIONS_TO_MATURE, addr0)
        assert_equal(node0.getblockcount(), PREMINE_WINDOW)

        self.sync_all()
        assert_equal(node0.getbestblockhash(), node1.getbestblockhash())
        assert_equal(self.total_supply(node0), SUPPLY_AFTER_POW_WINDOW)
        assert node1.getbalance() >= NODE1_FUNDING, "node1's funding tx should be confirmed and spendable by now"

        self.log.info("Disconnecting node0 and node1")
        self.disconnect_nodes(0, 1)

        pre_disconnect_height = node0.getblockcount()
        assert_equal(pre_disconnect_height, node1.getblockcount())

        # See feature_coinage_reward.py for why this needs a long timeout:
        # rapidly mining leaves the chain's median-time-past several
        # minutes ahead of real wall-clock time, and PoS blocks are
        # correctly withheld until real time catches up (consensus
        # safety, not a hang).
        self.log.info("Letting node0 and node1 independently stake their own forks")
        self.wait_until(lambda: node0.getblockcount() > pre_disconnect_height, timeout=900)
        self.wait_until(lambda: node1.getblockcount() > pre_disconnect_height, timeout=900)

        self.log.info(f"node0 forked to height {node0.getblockcount()}, node1 forked to height {node1.getblockcount()}")

        self.log.info("Reconnecting nodes; they should converge onto a single chain")
        self.connect_nodes(0, 1)
        self.sync_all()

        assert_equal(node0.getbestblockhash(), node1.getbestblockhash())
        assert_equal(node0.getblockcount(), node1.getblockcount())

        self.log.info("Checking supply is exactly the PoW-window supply + 10 per staked block, on both nodes")
        supply0 = self.total_supply(node0)
        supply1 = self.total_supply(node1)
        assert_equal(supply0, supply1)
        staked_blocks = node0.getblockcount() - PREMINE_WINDOW
        assert staked_blocks > 0
        assert_equal(supply0, SUPPLY_AFTER_POW_WINDOW + STAKE_REWARD * staked_blocks)

        self.log.info(f"Post-reorg supply consistent on both nodes: {supply0} FIC")


if __name__ == "__main__":
    PosReorgTest().main()

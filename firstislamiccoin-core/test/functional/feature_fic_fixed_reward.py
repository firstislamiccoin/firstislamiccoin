#!/usr/bin/env python3
# Copyright (c) 2026 The FirstIslamicCoin developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Every proof-of-stake block mints exactly the fixed reward plus its fees.

Two nodes stake on a chain that is proof-of-stake from block 1. node0 holds the
premine; node1 is funded with stakes differing by orders of magnitude. While
they stake, both keep sending fee-paying transactions. For every block, the
coinstake must mint exactly 10 FIC + that block's fees, however large the
staked kernel was and however long it had sat unspent.

(The consensus rule itself, including rejection of over- and under-claiming
coinstakes, is covered by fic_reward_tests in the unit test suite.)
"""

from decimal import Decimal

from test_framework.fic import (
    POS_FROM_GENESIS_ARGS,
    PREMINE,
    STAKE_REWARD,
    block_fees,
    coinstake_mint,
    import_genesis_key,
)
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import assert_equal

# Stakes for node1, from a handful of coins to hundreds of millions.
NODE1_STAKES = [Decimal("50"), Decimal("20000"), Decimal("3000000"), Decimal("600000000")]
MATURITY = 10  # regtest nCoinbaseMaturity
TARGET_HEIGHT = 30


class FixedRewardTest(BitcoinTestFramework):
    def add_options(self, parser):
        self.add_wallet_options(parser)

    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 2
        self.extra_args = [POS_FROM_GENESIS_ARGS + ["-staking=0"]] * 2

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def run_test(self):
        node0, node1 = self.nodes

        self.log.info("Funding node1 with stakes of very different sizes, straight from the premine")
        import_genesis_key(node0, self.options.descriptors)
        node0.sendmany("", {node1.getnewaddress(): amount for amount in NODE1_STAKES})
        self.sync_mempools()

        self.log.info("Both nodes stake")
        for i in range(self.num_nodes):
            self.restart_node(i, extra_args=POS_FROM_GENESIS_ARGS + ["-staking=1"])
        self.connect_nodes(0, 1)

        def keep_transacting():
            # Fee-paying traffic in both directions, so blocks carry fees.
            if node0.getmempoolinfo()["size"] < 2:
                node0.sendtoaddress(node1.getnewaddress(), Decimal("1.5"))
            if node1.getbalance() > 10 and node1.getmempoolinfo()["size"] < 3:
                node1.sendtoaddress(node0.getnewaddress(), Decimal("0.25"))
            return node0.getblockcount() >= TARGET_HEIGHT

        self.wait_until(keep_transacting, timeout=1800)
        self.sync_blocks()
        height = node0.getblockcount()

        self.log.info(f"Checking the reward of all {height} blocks")
        kernel_values, kernel_ages, fee_blocks = set(), set(), 0
        for h in range(1, height + 1):
            block = node0.getblock(node0.getblockhash(h), 3)
            assert_equal(block["flags"], "proof-of-stake")
            fees = block_fees(block)
            fee_blocks += fees > 0

            mint = coinstake_mint(block)
            assert_equal(mint, STAKE_REWARD + fees)

            kernel = block["tx"][1]["vin"][0]["prevout"]
            age = block["height"] - kernel["height"]
            kernel_values.add(kernel["value"])
            kernel_ages.add(age)
            self.log.debug(f"  block {h}: kernel of {kernel['value']} aged {age} blocks -> minted {mint} ({fees} fees)")

        self.log.info(f"  {len(kernel_values)} distinct kernel values, {len(kernel_ages)} distinct kernel ages, "
                      f"{fee_blocks} blocks with fees -- one reward: {STAKE_REWARD} + fees")
        assert len(kernel_values) >= 2, "expected blocks staked with differently sized kernels"
        assert len(kernel_ages) >= 2, "expected blocks staked with kernels of different ages"
        assert fee_blocks >= 1, "expected at least one block carrying fees"

        self.log.info("Supply is exactly the premine plus the fixed reward per block")
        assert_equal(node0.gettxoutsetinfo()["total_amount"], PREMINE + STAKE_REWARD * height)
        assert_equal(node1.gettxoutsetinfo()["total_amount"], PREMINE + STAKE_REWARD * height)


if __name__ == "__main__":
    FixedRewardTest().main()

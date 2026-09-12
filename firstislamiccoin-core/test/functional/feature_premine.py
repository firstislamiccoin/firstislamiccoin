#!/usr/bin/env python3
# Copyright (c) 2026 The CodexaCoin developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test CodexaCoin's founder premine window and PoS-only enforcement.

Covers PARAMETERS.md section 5: a fixed nLastPOWBlock-block PoW window
mints exactly nPremineTotal (14,000,000,000 CAC on regtest, split evenly
per block), after which PoW is permanently disallowed and only PoS blocks
are accepted.
"""

from decimal import Decimal

from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import (
    assert_equal,
    assert_raises_rpc_error,
)

COIN = Decimal("100000000")
PREMINE_WINDOW = 500
EXPECTED_TOTAL_PREMINE = Decimal("14000000000")
EXPECTED_PER_BLOCK = EXPECTED_TOTAL_PREMINE / PREMINE_WINDOW  # 28,000,000 CAC


class PremineTest(BitcoinTestFramework):
    def add_options(self, parser):
        self.add_wallet_options(parser)

    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 1

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def run_test(self):
        node = self.nodes[0]
        addr = node.getnewaddress()

        self.log.info(f"Mining the full {PREMINE_WINDOW}-block premine window")
        self.generatetoaddress(node, PREMINE_WINDOW, addr)
        assert_equal(node.getblockcount(), PREMINE_WINDOW)

        self.log.info("Checking every premine block pays exactly the expected flat per-block reward")
        total = Decimal(0)
        for height in range(1, PREMINE_WINDOW + 1):
            block_hash = node.getblockhash(height)
            block = node.getblock(block_hash, 2)
            coinbase_out = sum(Decimal(str(vout["value"])) for vout in block["tx"][0]["vout"])
            assert_equal(coinbase_out, EXPECTED_PER_BLOCK)
            total += coinbase_out

        self.log.info(f"Checking total premine == {EXPECTED_TOTAL_PREMINE} CAC exactly")
        assert_equal(total, EXPECTED_TOTAL_PREMINE)

        self.log.info("Checking PoW is rejected immediately past the premine window (block 501)")
        assert_raises_rpc_error(-1, "reject-pow", node.generatetoaddress, 1, addr, invalid_call=False)

        self.log.info("Checking the chain tip did not advance from the rejected PoW attempt")
        assert_equal(node.getblockcount(), PREMINE_WINDOW)


if __name__ == "__main__":
    PremineTest().main()

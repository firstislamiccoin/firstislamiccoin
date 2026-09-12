#!/usr/bin/env python3
# Copyright (c) 2026 The FirstIslamicCoin developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""FirstIslamicCoin regtest constants and helpers shared by functional tests."""

from decimal import Decimal

from .descriptors import descsum_create

# The regtest genesis premine key. Deliberately public -- it is
# sha256("FirstIslamicCoin regtest genesis premine key") -- so tests can spend
# and stake the premine. Mainnet and testnet genesis blocks pay other scripts.
REGTEST_GENESIS_WIF = "cMup77fpH26t5EnVk7HtkNzhcBAbMaXCGFZxoUo6extVBqSSLhQM"
REGTEST_GENESIS_ADDRESS = "mqotRenA4D6QimV51jkNMjQuLdZthPCJwh"

PREMINE = Decimal("14000000000")
GENESIS_OUTPUTS = 1000
GENESIS_OUTPUT_VALUE = PREMINE / GENESIS_OUTPUTS
STAKE_REWARD = Decimal("10")

# Regtest normally keeps a proof-of-work window so the upstream harness can
# mine on demand. These arguments restore mainnet's rules instead: no PoW
# after genesis, so every block must be staked.
POS_FROM_GENESIS_ARGS = ["-lastpowblock=0", "-txindex=1"]


def import_genesis_key(node, descriptors):
    """Give node's wallet the regtest premine and rescan from genesis."""
    if descriptors:
        result = node.importdescriptors([{"desc": descsum_create(f"combo({REGTEST_GENESIS_WIF})"), "timestamp": 0}])
        assert result[0]["success"], result
    else:
        node.importprivkey(REGTEST_GENESIS_WIF, "genesis", True)


def coinstake_mint(block):
    """What a getblock(verbosity=3) proof-of-stake block's coinstake paid out
    beyond what it spent: the fixed reward plus the block's fees."""
    coinstake = block["tx"][1]
    value_in = sum((vin["prevout"]["value"] for vin in coinstake["vin"]), Decimal(0))
    value_out = sum((vout["value"] for vout in coinstake["vout"]), Decimal(0))
    return value_out - value_in


def block_fees(block):
    """Fees of the ordinary transactions in a getblock(verbosity>=2) PoS block."""
    return sum((tx["fee"] for tx in block["tx"][2:]), Decimal(0))

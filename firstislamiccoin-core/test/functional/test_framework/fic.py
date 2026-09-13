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
# Regtest proof-of-work subsidy per block (consensus.nPowSubsidy), paid up to
# nLastPOWBlock. Constant (no halving). POW_BLOCK_REWARD is an alias used by
# some tests; both names refer to the same value.
POW_SUBSIDY = Decimal("28000000")
POW_BLOCK_REWARD = POW_SUBSIDY

# Regtest normally keeps a proof-of-work window so the upstream harness can
# mine on demand. These arguments restore mainnet's rules instead: no PoW
# after genesis, so every block must be staked.
#
# -maxtipage: the regtest genesis block is dated 2026-09-12 00:00 UTC. Once it
# is more than a day old (the default -maxtipage), a node whose tip is still
# genesis stays in initial block download: it neither relays transactions nor
# stakes, so a chain that must be staked from genesis could not start. Ten
# years keeps these tests independent of the wall clock.
POS_FROM_GENESIS_ARGS = ["-lastpowblock=0", "-txindex=1", "-maxtipage=315360000"]


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


def matured_coinbase_value(node, old_height, new_height):
    """Value of node's wallet coinbase outputs that became spendable while the
    tip moved from old_height to new_height. A coinbase at height h matures at
    tip h + COINBASE_MATURITY (wallet.cpp GetTxBlocksToMaturity uses
    nCoinbaseMaturity + 1 confirmations)."""
    from .blocktools import COINBASE_MATURITY
    total = Decimal(0)
    for tip in range(old_height + 1, new_height + 1):
        height = tip - COINBASE_MATURITY
        if height < 1:
            continue
        coinbase = node.getblock(node.getblockhash(height), 2)["tx"][0]
        for out in coinbase["vout"]:
            address = out["scriptPubKey"].get("address")
            if address and node.getaddressinfo(address)["ismine"]:
                total += out["value"]
    return total


# Minimum transaction fee, enforced for every mempool and block transaction
# (GetMinFee in src/consensus/tx_verify.cpp; MIN_TX_FEE and TX_FEE_PER_KB in
# src/validation.h): a flat 10000 sat up to 100 vbytes, 100 sat/vbyte above.
# Peers' feefilter (BIP133) is fixed at this same rate and never rounds above
# it, so a transaction paying exactly get_min_fee_sat() is always relayed.
MIN_TX_FEE_SAT = 10000
TX_FEE_PER_KB_SAT = 100000


def get_min_fee_sat(vsize):
    """The minimum fee in satoshis for a transaction of vsize vbytes. This also
    meets every peer's feefilter, which is fixed at the same rate."""
    return MIN_TX_FEE_SAT if vsize <= 100 else TX_FEE_PER_KB_SAT * vsize // 1000

#!/usr/bin/env python3
"""FirstIslamicCoin block explorer backend.

Public, read-only, no authentication and no wallet keys -- a deliberately
separate, lower-trust service from any future staking-service backend,
same reasoning as CodexaCoin's explorer/app.py (see README.md).

Backend: direct firstislamiccoind RPC. txindex=1 is on by default on this
fork (staking itself depends on it -- see wallet/staking.cpp), so arbitrary
block/transaction lookups by hash/txid work natively with no extra
indexing infrastructure.

Address lookups use `scantxoutset`, a stateless full-UTXO-set scan for a
descriptor, rather than importing the address into a wallet -- appropriate
here specifically because the explorer must be able to look up *any*
address a visitor types in without accumulating permanent wallet state for
each one. Known limitation, same as CodexaCoin's: scantxoutset only sees
the *current* UTXO set, so this gives accurate current balance/UTXOs but
NOT historical (already-spent) transactions for an address -- that needs a
real index (firstislamiccoin-electrumx, Phase 4, not built yet).
Documented here and in the API response itself, not silently overclaimed.

FirstIslamicCoin's supply is exact and constant-formula at every height,
unlike CodexaCoin's: no proof-of-work premine window, and the post-genesis
reward is a fixed 10 FIC + fees rather than coin-age-proportional (see
docs/tokenomics.md). Supply at height N = 14,000,000,000 + 10 x N FIC,
always, which is why /api/supply here can give an exact figure CAC's
explorer.py explicitly couldn't.

Configuration is via environment variables (see rpc.py):
    FIC_RPC_HOST, FIC_RPC_PORT, FIC_RPC_COOKIEFILE
    FIC_RPC_USER, FIC_RPC_PASSWORD          (alternative to the cookie file)
    EXPLORER_CORS_ORIGINS  (default: *)
    EXPLORER_RICHLIST_MAX_BLOCKS  (default: 5000)
"""
import os
import re

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import rpc
from rpc import RpcError

COIN = 100_000_000  # 1 FIC = 100,000,000 fils
PREMINE_TOTAL_FILS = 14_000_000_000 * COIN
FIXED_REWARD_FILS = 10 * COIN
TARGET_SPACING_SECONDS = 64  # docs/tokenomics.md; regtest/testnet may differ, see /api/stats "chain"
BLOCKS_PER_YEAR = 31_536_000 // TARGET_SPACING_SECONDS  # 492,750, matches docs/tokenomics.md exactly
ANNUAL_EMISSION_FILS = BLOCKS_PER_YEAR * FIXED_REWARD_FILS

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": os.environ.get("EXPLORER_CORS_ORIGINS", "*")}})
# Fully public, unauthenticated, no per-user identity to key off of --
# rate-limit by IP as the only real abuse control available here.
limiter = Limiter(get_remote_address, app=app, default_limits=["120 per minute"], storage_uri="memory://")


def error(message, status=400):
    return jsonify({"error": message}), status


def total_supply_fils(height):
    """Exact at every height: the genesis premine plus the fixed reward for
    every block since -- see docs/tokenomics.md "Supply, in one line". Fees
    move existing coins between people and mint none, so they don't appear
    here."""
    return PREMINE_TOTAL_FILS + FIXED_REWARD_FILS * height


def is_coinstake_tx(tx):
    return (
        len(tx["vin"]) > 0
        and "coinbase" not in tx["vin"][0]
        and len(tx["vout"]) >= 2
        and float(tx["vout"][0]["value"]) == 0
        and tx["vout"][0]["scriptPubKey"].get("hex", "") == ""
    )


def summarize_tx(tx, block_time=None):
    is_coinbase = "coinbase" in tx["vin"][0] if tx["vin"] else False
    is_coinstake = is_coinstake_tx(tx)
    out_total_fils = sum(round(o["value"] * COIN) for o in tx["vout"])
    return {
        "txid": tx["txid"],
        "is_coinbase": is_coinbase,
        "is_coinstake": is_coinstake,
        "vin_count": len(tx["vin"]),
        "vout_count": len(tx["vout"]),
        "output_total_fils": str(out_total_fils),
        "time": tx.get("time", block_time),
    }


@app.route("/api/stats")
def stats():
    info = rpc.call("getblockchaininfo")
    height = info["blocks"]
    return jsonify({
        "height": height,
        "best_block_hash": info["bestblockhash"],
        "difficulty": info["difficulty"],
        "chain": info["chain"],
        "premine_total_fils": str(PREMINE_TOTAL_FILS),
        "fixed_reward_fils": str(FIXED_REWARD_FILS),
        "total_supply_fils": str(total_supply_fils(height)),
        "annual_emission_fils": str(ANNUAL_EMISSION_FILS),
    })


@app.route("/api/supply")
def supply():
    # Plain-number endpoint for listing forms (CoinMarketCap/CoinGecko-style),
    # matching the prompt's Phase 8 requirement. See /api/circulating for why
    # this and circulating are the same number for FIC today.
    height = rpc.call("getblockchaininfo")["blocks"]
    total_fic = total_supply_fils(height) / COIN
    return jsonify({"height": height, "total_supply": total_fic, "unit": "FIC"})


@app.route("/api/circulating")
def circulating():
    # FirstIslamicCoin has no vesting/lockup schedule distinguishing
    # "circulating" from "total": the genesis premine is fully spendable
    # from block 1 (see docs/tokenomics.md, "genesis outputs are exempt from
    # coinbase maturity"). Circulating supply is total supply. On mainnet,
    # until the genesis key ceremony (docs/CHANGELOG-FIC.md TODO-HUMAN 1)
    # replaces the placeholder key, the premine cannot actually move -- that
    # nuance is surfaced in "premine_spendable" rather than silently assumed.
    height = rpc.call("getblockchaininfo")["blocks"]
    chain = rpc.call("getblockchaininfo")["chain"]
    total_fic = total_supply_fils(height) / COIN
    return jsonify({
        "height": height,
        "circulating_supply": total_fic,
        "unit": "FIC",
        "premine_spendable": chain != "main",
        "note": "Circulating equals total supply on this chain: the genesis "
                "premine has no lockup. premine_spendable is false only on "
                "mainnet before the genesis key ceremony replaces its "
                "placeholder recipient.",
    })


@app.route("/api/blockreward")
def blockreward():
    return jsonify({
        "reward_fic": FIXED_REWARD_FILS / COIN,
        "fixed": True,
        "depends_on_stake_amount": False,
        "depends_on_stake_age": False,
        "note": "Every proof-of-stake block mints exactly this amount plus "
                "that block's transaction fees; enforced as an exact match "
                "by consensus, not a policy. See docs/tokenomics.md.",
    })


@app.route("/api/staking-stats")
def staking_stats():
    # "Active stake weight estimate" (prompt Phase 8 item 2) would need
    # getstakinginfo's netstakeweight, a wallet RPC -- this backend
    # deliberately holds no wallet (see module docstring), so that figure
    # isn't shown here rather than approximated from a formula this service
    # can't verify against a real wallet. Blocks/day is computed directly
    # from real block timestamps, no wallet needed.
    info = rpc.call("getblockchaininfo")
    height = info["blocks"]
    window = min(500, height)
    blocks_per_day = None
    if window >= 2:
        newest = rpc.call("getblock", [info["bestblockhash"], 1])
        oldest_hash = rpc.call("getblockhash", [height - window])
        oldest = rpc.call("getblock", [oldest_hash, 1])
        elapsed = newest["time"] - oldest["time"]
        if elapsed > 0:
            blocks_per_day = round(window * 86400 / elapsed, 1)
    return jsonify({
        "height": height,
        "blocks_per_day": blocks_per_day,
        "measured_over_blocks": window if blocks_per_day is not None else 0,
        "target_blocks_per_day": round(86400 / TARGET_SPACING_SECONDS, 1),
        "current_block_reward_fic": FIXED_REWARD_FILS / COIN,
        "annual_emission_fic": ANNUAL_EMISSION_FILS / COIN,
        "active_stake_weight": None,
        "delegated_staking_p2cs": None,
        "note": "active_stake_weight needs a staking wallet's getstakinginfo; "
                "this read-only backend holds no wallet, so it's omitted "
                "rather than estimated from an unverified formula. "
                "delegated_staking_p2cs (P2CS/cold-staking statistics) is "
                "null because the feature doesn't exist in this codebase yet "
                "-- see TODO-HUMAN 2 in docs/CHANGELOG-FIC.md.",
    })


@app.route("/api/block/<ident>")
def block_detail(ident):
    try:
        if re.fullmatch(r"[0-9]+", ident):
            block_hash = rpc.call("getblockhash", [int(ident)])
        else:
            block_hash = ident
        block = rpc.call("getblock", [block_hash, 2])
    except RpcError:
        return error("No such block", 404)

    txs = [summarize_tx(tx, block["time"]) for tx in block["tx"]]
    is_genesis = block["height"] == 0
    is_pos = block.get("flags") == "proof-of-stake" or (len(txs) > 0 and txs[0]["is_coinstake"])
    return jsonify({
        "hash": block["hash"],
        "height": block["height"],
        "time": block["time"],
        "difficulty": block["difficulty"],
        "bits": block["bits"],
        "version": block["version"],
        "merkleroot": block["merkleroot"],
        "previousblockhash": block.get("previousblockhash"),
        "nextblockhash": block.get("nextblockhash"),
        "is_genesis": is_genesis,
        "is_proof_of_stake": is_pos,
        "tx_count": len(txs),
        "transactions": txs,
    })


@app.route("/api/tx/<txid>")
def tx_detail(txid):
    try:
        tx = rpc.call("getrawtransaction", [txid, True])
    except RpcError:
        return error("No such transaction", 404)

    is_coinstake = is_coinstake_tx(tx)
    is_coinbase = "coinbase" in tx["vin"][0] if tx["vin"] else False
    reward_fils = None
    if is_coinstake:
        out_total = sum(round(o["value"] * COIN) for o in tx["vout"])
        in_total = 0
        for vin in tx["vin"]:
            prevtx = rpc.call("getrawtransaction", [vin["txid"], True])
            in_total += round(prevtx["vout"][vin["vout"]]["value"] * COIN)
        reward_fils = out_total - in_total

    height = None
    if "blockhash" in tx:
        block = rpc.call("getblock", [tx["blockhash"], 1])
        height = block["height"]

    return jsonify({
        "txid": txid,
        "height": height,
        "blockhash": tx.get("blockhash"),
        "confirmations": tx.get("confirmations", 0),
        "time": tx.get("time"),
        "is_coinbase": is_coinbase,
        "is_coinstake": is_coinstake,
        "reward_fils": str(reward_fils) if reward_fils is not None else None,
        "reward_fees_fils": str(reward_fils - FIXED_REWARD_FILS) if reward_fils is not None else None,
        "vin": tx["vin"],
        "vout": tx["vout"],
    })


@app.route("/api/address/<address>")
@limiter.limit("10 per minute")  # scantxoutset is a full UTXO-set scan -- expensive, limit harder
def address_detail(address):
    try:
        result = rpc.call("scantxoutset", ["start", [f"addr({address})"]])
    except RpcError as e:
        return error(f"Lookup failed: {e.message}", 400)
    if not result.get("success"):
        return error("Scan did not complete, try again", 503)

    utxos = [
        {"txid": u["txid"], "vout": u["vout"], "value_fils": str(round(u["amount"] * COIN)),
         "height": u.get("height"), "is_coinbase_or_coinstake": u.get("coinbase", False)}
        for u in result["unspents"]
    ]
    balance_fils = sum(int(u["value_fils"]) for u in utxos)
    return jsonify({
        "address": address,
        "balance_fils": str(balance_fils),
        "utxo_count": len(utxos),
        "utxos": utxos,
        "scanned_at_height": result["height"],
        "note": "Current balance/UTXOs only -- this explorer has no full "
                "transaction-history index (see app.py's module docstring); "
                "spent/historical transactions for this address aren't shown here.",
    })


@app.route("/api/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return error("Provide ?q=<height|block hash|txid|address>")

    if re.fullmatch(r"[0-9]+", q):
        return jsonify({"type": "block", "id": q})
    if re.fullmatch(r"[0-9a-fA-F]{64}", q):
        # Disambiguate block hash vs txid by trying getblock first (cheap,
        # since we already have txindex for the tx fallback).
        try:
            rpc.call("getblock", [q, 1])
            return jsonify({"type": "block", "id": q})
        except RpcError:
            pass
        try:
            rpc.call("getrawtransaction", [q, True])
            return jsonify({"type": "tx", "id": q})
        except RpcError:
            return error("No block or transaction found with that hash", 404)
    # Anything else is treated as an address -- validated server-side by the
    # scan itself; the search endpoint just routes, it doesn't pre-validate.
    return jsonify({"type": "address", "id": q})


RICHLIST_MAX_BLOCKS = int(os.environ.get("EXPLORER_RICHLIST_MAX_BLOCKS", "5000"))


@app.route("/api/richlist")
@limiter.limit("6 per minute")  # this is a real block-scanning computation, not a cheap lookup -- see its own comment
def richlist():
    # No general address index exists (see module docstring), so this
    # builds one on the fly by walking every block's transactions: credit
    # each output's address, debit each non-coinbase input's previous
    # output's address (resolved via txindex). Correct for the whole chain,
    # but genuinely O(blocks x transactions) -- bounded by
    # EXPLORER_RICHLIST_MAX_BLOCKS (walks the *last* N blocks only once the
    # chain exceeds that, silently becoming an approximation over only
    # recent history rather than a wrong full-chain answer). A real address
    # index (firstislamiccoin-electrumx, Phase 4) is the right fix before
    # this matters on a mature chain -- this isn't a replacement for that,
    # just what's honestly buildable without one right now.
    try:
        limit = min(int(request.args.get("limit", "20")), 100)
    except ValueError:
        return error("limit must be an integer")

    height = rpc.call("getblockchaininfo")["blocks"]
    start_height = max(0, height - RICHLIST_MAX_BLOCKS + 1)
    truncated = start_height > 0

    balances = {}
    for h in range(start_height, height + 1):
        block_hash = rpc.call("getblockhash", [h])
        block = rpc.call("getblock", [block_hash, 2])
        for tx in block["tx"]:
            for vout in tx["vout"]:
                addr = vout["scriptPubKey"].get("address")
                if not addr:
                    continue
                balances[addr] = balances.get(addr, 0) + round(vout["value"] * COIN)
            if "coinbase" in tx["vin"][0]:
                continue
            for vin in tx["vin"]:
                try:
                    prevtx = rpc.call("getrawtransaction", [vin["txid"], True])
                except RpcError:
                    continue
                prevout = prevtx["vout"][vin["vout"]]
                addr = prevout["scriptPubKey"].get("address")
                if not addr:
                    continue
                balances[addr] = balances.get(addr, 0) - round(prevout["value"] * COIN)

    ranked = sorted(balances.items(), key=lambda kv: kv[1], reverse=True)
    ranked = [(a, b) for a, b in ranked if b > 0][:limit]
    return jsonify({
        "addresses": [{"address": a, "balance_fils": str(b)} for a, b in ranked],
        "scanned_from_height": start_height,
        "scanned_to_height": height,
        "truncated": truncated,
    })


@app.route("/api/supply-series")
def supply_series():
    # Exact at every point, unlike CodexaCoin's (whose PoW premine window
    # gave a fixed formula only up to height 500, then nothing computable
    # once coin-age PoS rewards started): FIC's fixed reward makes
    # total_supply_fils(h) exact for any h at all.
    height = rpc.call("getblockchaininfo")["blocks"]
    buckets = min(50, max(1, height))
    step = max(1, height // buckets)
    points = [{"height": h, "total_supply_fils": str(total_supply_fils(h))}
              for h in range(0, height + 1, step)]
    if points[-1]["height"] != height:
        points.append({"height": height, "total_supply_fils": str(total_supply_fils(height))})
    return jsonify({"points": points})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081, debug=False)

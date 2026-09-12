#!/usr/bin/env python3
"""Sum every coinbase output from block 1 through the end of the founder
premine window (consensus.nLastPOWBlock) via RPC, and assert the total
equals exactly the chain's configured premine (14,000,000,000 CAC on
mainnet/testnet). See PARAMETERS.md section 5.

Usage:
    audit_premine_supply.py [-rpcconnect=HOST] [-rpcport=PORT]
                             [-rpcuser=USER] [-rpcpassword=PASS]
                             [-rpccookiefile=PATH] [--last-pow-block=N]
                             [--expected-total=SATOSHIS]

With no arguments, connects to a local regtest node using cookie auth from
the default regtest datadir.
"""
import argparse
import http.client
import json
import os
import sys
from base64 import b64encode

COIN = 100_000_000


def rpc_call(conn, host, auth_header, method, params=None):
    payload = json.dumps({"jsonrpc": "1.0", "id": "audit", "method": method, "params": params or []})
    headers = {"Content-Type": "application/json", "Authorization": auth_header}
    conn.request("POST", "/", payload, headers)
    resp = conn.getresponse()
    body = json.loads(resp.read())
    if body.get("error"):
        raise RuntimeError(f"RPC error calling {method}: {body['error']}")
    return body["result"]


def load_cookie_auth(cookie_path):
    with open(cookie_path, "r") as f:
        userpass = f.read().strip()
    return "Basic " + b64encode(userpass.encode()).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rpcconnect", default="127.0.0.1")
    ap.add_argument("--rpcport", type=int, default=36211)  # CAC regtest RPC port
    ap.add_argument("--rpcuser")
    ap.add_argument("--rpcpassword")
    ap.add_argument("--rpccookiefile")
    ap.add_argument("--last-pow-block", type=int, default=500)
    ap.add_argument("--expected-total", type=int, default=14_000_000_000 * COIN,
                     help="Expected total premine in satoshis (default: 14,000,000,000 CAC)")
    args = ap.parse_args()

    if args.rpcuser and args.rpcpassword:
        auth_header = "Basic " + b64encode(f"{args.rpcuser}:{args.rpcpassword}".encode()).decode()
    else:
        cookie_path = args.rpccookiefile or os.path.expanduser("~/.codexacoin/regtest/.cookie")
        auth_header = load_cookie_auth(cookie_path)

    conn = http.client.HTTPConnection(args.rpcconnect, args.rpcport, timeout=30)

    height = rpc_call(conn, args.rpcconnect, auth_header, "getblockcount")
    scan_to = min(args.last_pow_block, height)
    if height < args.last_pow_block:
        print(f"WARNING: chain height ({height}) is below the premine window "
              f"({args.last_pow_block}); auditing only blocks 1..{scan_to} so far mined.")

    total_satoshis = 0
    per_block = []
    for h in range(1, scan_to + 1):
        block_hash = rpc_call(conn, args.rpcconnect, auth_header, "getblockhash", [h])
        block = rpc_call(conn, args.rpcconnect, auth_header, "getblock", [block_hash, 2])
        coinbase_tx = block["tx"][0]
        block_reward_sat = round(sum(vout["value"] for vout in coinbase_tx["vout"]) * COIN)
        per_block.append(block_reward_sat)
        total_satoshis += block_reward_sat

    print(f"Scanned blocks 1..{scan_to} (premine window: 1..{args.last_pow_block})")
    if per_block:
        print(f"Per-block reward: {per_block[0] / COIN:,.8f} CAC "
              f"(constant across window: {len(set(per_block)) == 1})")
    print(f"Total minted so far:  {total_satoshis / COIN:,.8f} CAC")
    print(f"Expected full premine: {args.expected_total / COIN:,.8f} CAC")

    if scan_to < args.last_pow_block:
        print("Premine window not fully mined yet; partial total only, skipping equality assertion.")
        return 0

    if total_satoshis != args.expected_total:
        print(f"FAIL: premine total mismatch (actual={total_satoshis} sat, "
              f"expected={args.expected_total} sat, diff={total_satoshis - args.expected_total} sat)")
        return 1

    print("PASS: premine total matches exactly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

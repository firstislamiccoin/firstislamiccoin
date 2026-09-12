#!/usr/bin/env python3
# Copyright (c) 2026 The FirstIslamicCoin developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Audit a FirstIslamicCoin node's supply against the consensus rules, over RPC.

From genesis to the current tip, checks that:
  1. the genesis coinbase carries exactly the premine, all of it spendable;
  2. every proof-of-stake block mints exactly the fixed reward -- its coinstake
     pays the reward plus the block's fees, nothing more or less;
  3. no proof-of-work block exists above --last-pow-block (0 on mainnet and
     testnet; regtest keeps a PoW window for its test harness);
  4. the UTXO set totals premine + everything minted - everything burned.

Needs unpruned block and undo data (getblock verbosity 3).

Usage:
    audit_premine_supply.py [--rpcconnect HOST] [--rpcport PORT]
                            [--rpcuser USER --rpcpassword PASS | --rpccookiefile PATH]
                            [--premine COINS] [--reward COINS] [--last-pow-block N]

With no arguments, connects to a local regtest node using cookie auth.
"""
import argparse
import http.client
import json
import os
import sys
from base64 import b64encode
from decimal import Decimal


class RPC:
    def __init__(self, host, port, auth_header):
        self.conn = http.client.HTTPConnection(host, port, timeout=120)
        self.auth = auth_header

    def __call__(self, method, *params):
        payload = json.dumps({"jsonrpc": "1.0", "id": "audit", "method": method, "params": list(params)})
        self.conn.request("POST", "/", payload, {"Content-Type": "application/json", "Authorization": self.auth})
        body = json.loads(self.conn.getresponse().read(), parse_float=Decimal)
        if body.get("error"):
            raise RuntimeError(f"RPC error calling {method}: {body['error']}")
        return body["result"]


def burned(tx):
    """Value sent to provably unspendable (OP_RETURN) outputs."""
    return sum((o["value"] for o in tx["vout"] if o["scriptPubKey"]["type"] == "nulldata"), Decimal(0))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rpcconnect", default="127.0.0.1")
    ap.add_argument("--rpcport", type=int, default=39771, help="default: regtest")
    ap.add_argument("--rpcuser")
    ap.add_argument("--rpcpassword")
    ap.add_argument("--rpccookiefile", default=os.path.expanduser("~/.firstislamiccoin/regtest/.cookie"))
    ap.add_argument("--premine", type=Decimal, default=Decimal("14000000000"))
    ap.add_argument("--reward", type=Decimal, default=Decimal("10"), help="fixed proof-of-stake reward")
    ap.add_argument("--last-pow-block", type=int, default=0)
    args = ap.parse_args()

    if args.rpcuser and args.rpcpassword:
        userpass = f"{args.rpcuser}:{args.rpcpassword}"
    else:
        with open(args.rpccookiefile) as f:
            userpass = f.read().strip()
    rpc = RPC(args.rpcconnect, args.rpcport, "Basic " + b64encode(userpass.encode()).decode())

    failures = []
    tip = rpc("getblockcount")

    genesis = rpc("getblock", rpc("getblockhash", 0), 3)
    premine_outputs = genesis["tx"][0]["vout"]
    genesis_total = sum((o["value"] for o in premine_outputs), Decimal(0))
    if genesis_total != args.premine:
        failures.append(f"genesis coinbase carries {genesis_total}, expected {args.premine}")
    if any(o["scriptPubKey"]["type"] == "nulldata" for o in premine_outputs):
        failures.append("genesis coinbase has an unspendable output")
    print(f"Genesis: {len(premine_outputs)} outputs totalling {genesis_total:,}")

    minted = Decimal(0)
    burnt = sum((burned(tx) for tx in genesis["tx"]), Decimal(0))
    pos_blocks = pow_blocks = 0
    for height in range(1, tip + 1):
        block = rpc("getblock", rpc("getblockhash", height), 3)
        txs = block["tx"]
        burnt += sum((burned(tx) for tx in txs), Decimal(0))
        if block.get("flags") == "proof-of-stake":
            pos_blocks += 1
            coinstake = txs[1]
            fees = sum((tx["fee"] for tx in txs[2:]), Decimal(0))
            value_in = sum((vin["prevout"]["value"] for vin in coinstake["vin"]), Decimal(0))
            value_out = sum((o["value"] for o in coinstake["vout"]), Decimal(0))
            if value_out - value_in != args.reward + fees:
                failures.append(f"block {height}: coinstake mints {value_out - value_in}, expected {args.reward} + {fees} fees")
            minted += value_out - value_in - fees
        else:
            pow_blocks += 1
            if height > args.last_pow_block:
                failures.append(f"block {height}: proof-of-work above --last-pow-block {args.last_pow_block}")
            fees = sum((tx["fee"] for tx in txs[1:]), Decimal(0))
            minted += sum((o["value"] for o in txs[0]["vout"]), Decimal(0)) - fees

    utxo_total = rpc("gettxoutsetinfo")["total_amount"]
    expected = args.premine + minted - burnt
    print(f"Blocks 1..{tip}: {pos_blocks} proof-of-stake, {pow_blocks} proof-of-work")
    print(f"Minted since genesis: {minted:,}   burned: {burnt:,}")
    print(f"UTXO set total:       {utxo_total:,}")
    print(f"Expected:             {expected:,}")
    if utxo_total != expected:
        failures.append(f"UTXO total {utxo_total} != premine + minted - burned {expected}")

    if failures:
        print(f"\nFAIL ({len(failures)}):")
        for f in failures[:50]:
            print(f"  - {f}")
        return 1
    print("\nPASS: supply matches the premine and the fixed reward exactly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Build the Phase 2 testnet report from the chain and the run's records.

Reads every block from node0 (verbosity 3, so every input carries its prevout)
and checks, at every height:
  - the block is proof of stake;
  - the block mints exactly the fixed reward: all outputs minus all inputs = 10;
  - the coinstake gains exactly reward + the block's fees.
Then block spacing, forks and reorganisations (monitor.jsonl), the stress
results (stress.jsonl), the bootstrap distribution, per-wallet staked-block
counts, and the supply audit.

Writes /out/testnet-report.md and /out/testnet-metrics.json.
Usage: report.py [--min-blocks 2000]
"""
import glob
import json
import statistics
import subprocess
import sys
import time
from decimal import Decimal

from ficrpc import RPCError, log, nodes

REWARD = Decimal("10")
TARGET_SPACING = 64
OUT_MD = "/out/testnet-report.md"
OUT_JSON = "/out/testnet-metrics.json"

rpc = nodes()


def load_jsonl(path):
    try:
        return [json.loads(l) for l in open(path) if l.strip()]
    except FileNotFoundError:
        return []


def blocks_check(node, tip):
    violations, times, fees_total, tx_total, stakers = [], {}, Decimal(0), 0, {}
    for h in range(1, tip + 1):
        b = node.getblock(node.getblockhash(h), 3)
        times[h] = b["time"]
        txs = b["tx"]
        tx_total += len(txs)
        pos = "proof-of-stake" in b.get("flags", "")
        total_out = sum(Decimal(o["value"]) for tx in txs for o in tx["vout"])
        total_in = Decimal(0)
        fees = Decimal(0)
        cs_gain = None
        for i, tx in enumerate(txs):
            if i == 0:
                continue  # coinbase: no real inputs
            tin = sum(Decimal(v["prevout"]["value"]) for v in tx["vin"])
            tout = sum(Decimal(o["value"]) for o in tx["vout"])
            total_in += tin
            if i == 1 and pos:
                cs_gain = tout - tin
                kernel = tx["vin"][0]["prevout"]["scriptPubKey"]
                stakers.setdefault(kernel.get("address") or kernel["desc"], 0)
                stakers[kernel.get("address") or kernel["desc"]] += 1
            else:
                fees += tin - tout
        fees_total += fees
        minted = total_out - total_in
        problems = []
        if not pos:
            problems.append("not proof-of-stake")
        if minted != REWARD:
            problems.append(f"minted {minted}")
        if cs_gain is not None and cs_gain != REWARD + fees:
            problems.append(f"coinstake gained {cs_gain}, expected {REWARD + fees}")
        if problems:
            violations.append({"height": h, "hash": b["hash"], "problems": problems})
        if h % 250 == 0:
            log(f"checked {h}/{tip}")
    return violations, times, fees_total, tx_total, stakers


def spacing_stats(times, lo, hi):
    deltas = [times[h] - times[h - 1] for h in range(max(lo, 2), hi + 1)]
    if not deltas:
        return None
    mean = (times[hi] - times[max(lo, 2) - 1]) / len(deltas)
    return {"from": max(lo, 2) - 1, "to": hi, "intervals": len(deltas), "mean": round(mean, 2),
            "median": statistics.median(deltas), "stdev": round(statistics.pstdev(deltas), 2),
            "min": min(deltas), "max": max(deltas),
            "deviation_pct": round(100 * (mean - TARGET_SPACING) / TARGET_SPACING, 2),
            "within_10pct": abs(mean - TARGET_SPACING) <= 0.10 * TARGET_SPACING}


def wallet_of(stakers):
    """Map kernel addresses/descriptors to the wallet that owns them."""
    owners = {}
    wallets = [(n, w) for n in rpc for w in rpc[n].listwallets()]
    for key, count in stakers.items():
        addr = key
        if key.startswith("pk("):
            pub = key[3:key.index(")")]
            desc = f"pkh({pub})"
            addr = rpc["node0"].deriveaddresses(f"{desc}#{rpc['node0'].getdescriptorinfo(desc)['checksum']}")[0]
        owner = "unknown"
        for n, w in wallets:
            try:
                if rpc[n].w(w).getaddressinfo(addr).get("ismine"):
                    owner = w
                    break
            except RPCError:
                pass
        owners[owner] = owners.get(owner, 0) + count
    return owners


def fork_stats(monitor, excluded_windows):
    def excluded(t):
        return any(a <= t <= b + 120 for a, b in excluded_windows)

    max_branch, reorgs, divergent, samples = {}, [], 0, {}
    for rec in monitor:
        t = rec.get("t", 0)
        if rec.get("event") == "reorg":
            if not excluded(t):
                reorgs.append(rec)
            continue
        if "height" not in rec:
            continue
        samples.setdefault(round(t), {})[rec["node"]] = (rec["height"], rec["best"])
        if excluded(t):
            continue
        for f in rec.get("forks", []):
            if f["status"] in ("valid-fork", "valid-headers", "headers-only"):
                max_branch[rec["node"]] = max(max_branch.get(rec["node"], 0), f["branchlen"])
    return {"max_fork_branchlen": max_branch, "longest_fork": max(max_branch.values(), default=0),
            "reorgs": len(reorgs), "max_reorg_depth": max((r["depth"] for r in reorgs), default=0),
            "reorg_depths": sorted(r["depth"] for r in reorgs)}


def supply_audit():
    cookie = glob.glob("/data/node0/*/.cookie")[0]
    proc = subprocess.run([sys.executable, "/opt/fic/audit_premine_supply.py", "--rpcconnect", "node0",
                           "--rpcport", "29771", "--rpccookiefile", cookie, "--last-pow-block", "0"],
                          capture_output=True, text=True, timeout=3600)
    return {"exit": proc.returncode, "output": (proc.stdout + proc.stderr).strip()}


def main():
    min_blocks = int(sys.argv[sys.argv.index("--min-blocks") + 1]) if "--min-blocks" in sys.argv else 2000
    node0 = rpc["node0"]
    tip = node0.getblockcount()
    if tip < min_blocks:
        log(f"only {tip} blocks; report needs {min_blocks} (pass --min-blocks to override)")
    log(f"checking blocks 1..{tip}")
    violations, times, fees_total, tx_total, stakers = blocks_check(node0, tip)

    stress = load_jsonl("/out/stress.jsonl")
    windows = [tuple(s["window"]) for s in stress if s.get("step") == "reorg" and "window" in s]
    # node restarts during stress steps also produce transient tips; excluded windows are reported
    monitor = load_jsonl("/out/monitor.jsonl")
    forks = fork_stats(monitor, windows)
    bootstrap = json.load(open("/out/bootstrap-state.json")) if glob.glob("/out/bootstrap-state.json") else {}

    tips_now = {n: [t for t in rpc[n].getchaintips() if t["status"] != "active"] for n in rpc}
    heights_now = {n: rpc[n].getblockcount() for n in rpc}
    info = node0.getblockchaininfo()
    network = node0.getnetworkinfo()
    staker_blocks = wallet_of(stakers)
    audit = supply_audit()

    spacing_all = spacing_stats(times, 2, tip)
    spacing_last = spacing_stats(times, max(2, tip - 1999), tip)
    windows_100 = [spacing_stats(times, lo, min(lo + 99, tip)) for lo in range(2, tip + 1, 100)]
    window_means = [w["mean"] for w in windows_100 if w and w["intervals"] >= 50]
    first_time, last_time = times.get(1), times.get(tip)

    metrics = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "subversion": network["subversion"], "chain": info["chain"], "tip": tip, "heights_now": heights_now,
        "run_hours": round((last_time - first_time) / 3600, 2) if first_time else None,
        "transactions": tx_total, "fees_total": fees_total,
        "reward_violations": violations, "blocks_checked": tip,
        "spacing_all": spacing_all, "spacing_last_2000": spacing_last,
        "spacing_100_block_window_means": {"min": min(window_means, default=None), "max": max(window_means, default=None)},
        "forks": forks, "tips_now": tips_now, "staked_blocks_by_wallet": staker_blocks,
        "supply_audit": audit, "stress": stress, "bootstrap": {k: v for k, v in bootstrap.items() if "height" in k},
    }
    with open(OUT_JSON, "w") as f:
        json.dump(metrics, f, indent=1, default=str)

    def yes(b):
        return "**PASS**" if b else "**FAIL**"

    s = {x["step"]: x for x in stress}
    lines = [
        "# FirstIslamicCoin testnet report (Phase 2)",
        "",
        f"Generated {metrics['generated']} by `firstislamiccoin-infra/testnet/report.py` from the live chain. "
        f"Node `{network['subversion']}`, chain `{info['chain']}`.",
        "",
        "## Summary",
        "",
        "| Check | Requirement | Result | |",
        "|---|---|---|---|",
        f"| Blocks | ≥ 2,000 | {tip:,} blocks over {metrics['run_hours']} h | {yes(tip >= 2000)} |",
        f"| Reward | exactly 10 tFIC + fees at every height | {tip - len(violations):,} of {tip:,} blocks exact | {yes(not violations)} |",
        f"| Spacing | mean within ±10% of 64 s | {spacing_all['mean']} s over all blocks ({spacing_all['deviation_pct']:+}%); "
        f"{spacing_last['mean']} s over the last 2,000 ({spacing_last['deviation_pct']:+}%) | {yes(spacing_last['within_10pct'])} |",
        f"| Forks | none longer than 2 blocks | longest fork {forks['longest_fork']} block(s); {forks['reorgs']} reorgs, deepest {forks['max_reorg_depth']} | {yes(forks['longest_fork'] <= 2 and forks['max_reorg_depth'] <= 2)} |",
        f"| Reorg handling | invalidateblock / reconsiderblock | " + (
            f"node1 stayed off the invalidated chain: {s['reorg']['stayed_off_invalid_chain']}; rejoined in {s['reorg']['rejoin_seconds']} s"
            if "reorg" in s else "not run") + f" | {yes('reorg' in s and s['reorg']['stayed_off_invalid_chain'] and s['reorg']['invalid_tips_after_reconsider'] == 0)} |",
        f"| Stress | 10,000 transactions via sendmany batches | " + (
            f"{s['spray']['transactions']:,} sent in {s['spray']['seconds_to_submit']} s, cleared in {s['spray']['seconds_to_clear']} s"
            if "spray" in s else "not run") + f" | {yes('spray' in s and s['spray']['transactions'] >= 10000)} |",
        f"| Mempool eviction | node1 at -maxmempool=5 | " + (
            f"node1 peak usage {s['spray']['mempool_peak'].get('node1', {}).get('usage')} bytes, peak min fee {s['spray']['mempool_peak'].get('node1', {}).get('minfee')}"
            if "spray" in s else "not run") + " | see below |",
        f"| Restart with reindex | same chain and UTXO set | " + (
            f"hash {s['reindex-after']['hash_matches']}, MuHash {s['reindex-after']['muhash_matches']}" if "reindex-after" in s else "not run")
        + f" | {yes('reindex-after' in s and s['reindex-after']['ok'])} |",
        f"| -txindex=1 | historical lookups | " + (
            f"{s['txindex']['ok']} of {s['txindex']['lookups']} on node3, genesis tx included" if "txindex" in s else "not run")
        + f" | {yes('txindex' in s and s['txindex']['ok'] == s['txindex']['lookups'])} |",
        f"| -prune=2000 | pruned node | not supported by this chain — see below | **N/A** |",
        f"| Supply | premine + 10 per block, exact | exit {audit['exit']} | {yes(audit['exit'] == 0)} |",
        "",
        "## Network",
        "",
        "Four nodes from `firstislamiccoin-infra/docker-compose.testnet.yml`. node0–node2 share bridge network "
        "`fic-a`; node3 is alone on `fic-b`, a separate network namespace and subnet, and reaches the chain only "
        "through node2, which is attached to both. Five staking wallets: staker1 (node0), staker2 and staker5 "
        "(node1), staker3 (node2), staker4 (node3).",
        "",
        f"Heights at report time: {heights_now}.",
        "",
        "## Premine distribution",
        "",
        "The testnet genesis key was imported into wallet `genesis` on node0, which staked the first blocks from "
        "genesis outputs. Tranche 1 (100 genesis outputs to each staker) confirmed at height "
        f"{bootstrap.get('tranche1_height')}; tranche 2 (the rest of the spendable premine, 100 outputs per staker) "
        f"at {bootstrap.get('tranche2_height')}, after which genesis staking was switched off; the final sweep of "
        f"matured leftovers at {bootstrap.get('sweep_height')}.",
        "",
        "Staked blocks by wallet (kernel owner): " + ", ".join(f"{k} {v}" for k, v in sorted(staker_blocks.items())) + ".",
        "",
        "## Reward",
        "",
        f"All {tip:,} blocks after genesis were read with their inputs' prevouts. Each block's outputs minus inputs "
        f"must equal 10 tFIC, and its coinstake must gain 10 tFIC plus the fees of the block's other transactions. "
        f"Violations: {len(violations)}. Fees collected over the run: {fees_total} tFIC across {tx_total:,} transactions.",
        "",
        "## Block spacing",
        "",
        "| Range | Intervals | Mean | Median | Std dev | Min | Max | Deviation |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for label, st in (("all blocks", spacing_all), ("last 2,000", spacing_last)):
        lines.append(f"| {label} ({st['from']}–{st['to']}) | {st['intervals']:,} | {st['mean']} s | {st['median']} s | "
                     f"{st['stdev']} s | {st['min']} s | {st['max']} s | {st['deviation_pct']:+}% |")
    lines += [
        "",
        f"100-block window means ranged from {metrics['spacing_100_block_window_means']['min']} s to "
        f"{metrics['spacing_100_block_window_means']['max']} s. Block 1 is excluded from spacing: its predecessor is "
        "the genesis block, dated 2026-09-12 00:00 UTC, before the network started.",
        "",
        "## Forks and reorganisations",
        "",
        f"The monitor sampled every node's chain tips every 5 s ({len(monitor):,} records). Longest competing branch "
        f"seen per node: {forks['max_fork_branchlen']}. Reorganisations observed on any node: {forks['reorgs']} "
        f"(depths {forks['reorg_depths'][:40]}{'…' if len(forks['reorg_depths']) > 40 else ''}). "
        "Periods of the deliberate invalidateblock test are excluded and reported below.",
        "",
        f"Non-active chain tips at report time: {tips_now}.",
        "",
        "## Stress and operations",
        "",
        "```json",
        json.dumps(stress, indent=1, default=str)[:12000],
        "```",
        "",
        "## Supply audit",
        "",
        "```",
        audit["output"][-3000:],
        "```",
    ]
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines) + "\n")
    log(f"wrote {OUT_MD} and {OUT_JSON}")


if __name__ == "__main__":
    main()

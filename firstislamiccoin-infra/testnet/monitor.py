#!/usr/bin/env python3
"""Continuously sample the testnet into /out/monitor.jsonl.

Every SAMPLE_SECONDS, for each node: height, best hash, peer count, mempool
size/bytes/min fee, and every chain tip that is not the active one (forks,
with their branch length). Separately tracks the last REORG_WINDOW block
hashes each node reported and logs a `reorg` event, with its depth, whenever a
hash at a height it had already seen changes.

The report derives fork statistics from this file; per-block reward and
spacing checks are made against the chain itself by report.py.
"""
import json
import time

from ficrpc import log, nodes

SAMPLE_SECONDS = 5
REORG_WINDOW = 50
OUT = "/out/monitor.jsonl"
STATUS = "/out/monitor-status.json"


def main():
    rpc = nodes()
    seen = {name: {} for name in rpc}          # node -> {height: hash}
    max_fork = {name: 0 for name in rpc}
    reorgs = []
    log("monitor started")
    with open(OUT, "a") as out:
        while True:
            now = time.time()
            status = {"t": now, "nodes": {}, "max_fork_branchlen": max_fork, "reorgs": len(reorgs)}
            for name, node in rpc.items():
                rec = {"t": round(now, 3), "node": name}
                try:
                    info = node.call("getblockchaininfo", retry_for=0, timeout=20)
                    tips = node.call("getchaintips", retry_for=0, timeout=20)
                    mempool = node.call("getmempoolinfo", retry_for=0, timeout=20)
                    rec.update(
                        height=info["blocks"],
                        best=info["bestblockhash"],
                        ibd=info["initialblockdownload"],
                        peers=node.call("getconnectioncount", retry_for=0, timeout=20),
                        mempool={"size": mempool["size"], "bytes": mempool["bytes"],
                                 "usage": mempool["usage"], "minfee": str(mempool["mempoolminfee"])},
                        forks=[{"height": t["height"], "branchlen": t["branchlen"], "status": t["status"], "hash": t["hash"]}
                               for t in tips if t["status"] != "active"],
                    )
                    for t in rec["forks"]:
                        if t["status"] in ("valid-fork", "valid-headers", "headers-only", "invalid"):
                            max_fork[name] = max(max_fork[name], t["branchlen"])

                    # Reorg detection over the recent window.
                    h = info["blocks"]
                    lo = max(0, h - REORG_WINDOW)
                    known = seen[name]
                    for height in range(max(lo, h - 12), h + 1):
                        blockhash = info["bestblockhash"] if height == h else node.call("getblockhash", height, retry_for=0, timeout=20)
                        old = known.get(height)
                        if old is not None and old != blockhash:
                            old_tip = max(known)
                            event = {"t": round(now, 3), "node": name, "event": "reorg",
                                     "fork_height": height - 1, "old_tip": old_tip,
                                     "depth": old_tip - (height - 1), "new_tip": h}
                            reorgs.append(event)
                            out.write(json.dumps(event) + "\n")
                            log(f"reorg on {name}: depth {event['depth']} at height {height}")
                            for k in [k for k in known if k >= height]:
                                del known[k]
                        known[height] = blockhash
                    for k in [k for k in known if k < lo]:
                        del known[k]
                except Exception as e:  # a node restarting is expected during stress steps
                    rec["error"] = str(e)[:200]
                out.write(json.dumps(rec) + "\n")
                status["nodes"][name] = {k: rec.get(k) for k in ("height", "peers", "ibd", "error")}
            out.flush()
            with open(STATUS, "w") as f:
                json.dump(status, f, indent=1)
            time.sleep(max(0.0, SAMPLE_SECONDS - (time.time() - now)))


if __name__ == "__main__":
    main()

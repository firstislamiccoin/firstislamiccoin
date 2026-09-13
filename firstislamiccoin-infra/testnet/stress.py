#!/usr/bin/env python3
"""Phase 2 stress steps, run one at a time by run-stress.sh (which does the
node restarts these steps need). Results append to /out/stress.jsonl.

  fund            three `stress` wallets (node0, node1, node3) get 3,400
                  confirmed 1,000-tFIC outputs each, via sendmany batches
  spray           10,000 transactions, each a sendmany to 2-5 addresses in the
                  other stress wallets; node1 runs with -maxmempool=5 meanwhile
  reindex-before  node2: record block hash and coinstatsindex UTXO-set MuHash
                  at a fixed height before it restarts with -reindex
  reindex-after   node2: wait for the reindex and both indexes, compare
  txindex         node3: look up random historical transactions, and the
                  genesis transaction, through the transaction index alone
  reorg           node1: invalidateblock two blocks deep, confirm it stays off
                  the chain while the others extend it, reconsiderblock, confirm
                  it rejoins the best chain
  record <json>   append a result produced on the host (the -prune check)
"""
import json
import random
import sys
import threading
import time
from decimal import Decimal

from ficrpc import RPCError, log, nodes, wait_for

OUT = "/out/stress.jsonl"
STRESS = [("stress0", "node0", "staker1"), ("stress1", "node1", "staker2"), ("stress3", "node3", "staker4")]
UTXOS_PER_WALLET = 3400
FUND_BATCH = 200
FUND_AMOUNT = Decimal("1000")
SPRAY_TOTAL = 10000

rpc = nodes()


def record(step, **data):
    data = {"step": step, "t": time.time(), **data}
    with open(OUT, "a") as f:
        f.write(json.dumps(data, default=str) + "\n")
    log(f"{step}: " + json.dumps(data, default=str)[:600])


def ensure_wallet(node_name, wallet):
    node = rpc[node_name]
    if wallet in node.listwallets():
        return
    if wallet in [w["name"] for w in node.listwalletdir()["wallets"]]:
        node.loadwallet(wallet, True)
    else:
        node.createwallet(wallet, False, False, "", False, True, True)


def wait_all_confirmed(node_wallet, txids, what, timeout=4 * 3600):
    pending = set(txids)

    def done():
        for txid in list(pending):
            if node_wallet.gettransaction(txid)["confirmations"] >= 1:
                pending.discard(txid)
        return not pending

    wait_for(done, what, timeout=timeout, interval=20)


def step_fund():
    started = time.time()
    for wallet, node_name, source in STRESS:
        ensure_wallet(node_name, wallet)
        dest = rpc[node_name].w(wallet)
        src = rpc[node_name].w(source)
        have = len([u for u in dest.listunspent(1) if u["amount"] == FUND_AMOUNT])
        txids = []
        while have < UTXOS_PER_WALLET:
            n = min(FUND_BATCH, UTXOS_PER_WALLET - have)
            amounts = {dest.getnewaddress("fund", "bech32"): FUND_AMOUNT for _ in range(n)}
            txids.append(src.sendmany("", amounts, 1, "fund"))
            have += n
        wait_all_confirmed(src, txids, f"funding {wallet}")
        log(f"{wallet}: {len(dest.listunspent(1))} confirmed outputs")
    record("fund", wallets=[w for w, _, _ in STRESS], utxos_per_wallet=UTXOS_PER_WALLET,
           amount=FUND_AMOUNT, seconds=round(time.time() - started))


def step_spray():
    for wallet, node_name, _ in STRESS:
        ensure_wallet(node_name, wallet)
    pools = {w: [rpc[n].w(w).getnewaddress("spray", "bech32") for _ in range(100)] for w, n, _ in STRESS}
    per_wallet = -(-SPRAY_TOTAL // len(STRESS))
    results = {}
    lock = threading.Lock()
    counter = {"sent": 0}
    started = time.time()
    start_height = rpc["node0"].getblockcount()

    def worker(wallet, node_name):
        me = rpc[node_name].w(wallet)
        others = [a for w, addrs in pools.items() if w != wallet for a in addrs]
        ok, errors, txids = 0, {}, []
        while True:
            with lock:
                if counter["sent"] >= SPRAY_TOTAL or ok >= per_wallet:
                    break
            k = random.randint(2, 5)
            amounts = {a: Decimal(random.randint(10, 500)) / 100 for a in random.sample(others, k)}
            try:
                txids.append(me.sendmany("", amounts, 1, "spray", retry_for=60))
                ok += 1
                with lock:
                    counter["sent"] += 1
                    if counter["sent"] % 1000 == 0:
                        log(f"spray: {counter['sent']} transactions sent")
            except RPCError as e:
                key = e.message[:80]
                errors[key] = errors.get(key, 0) + 1
                time.sleep(2)  # out of confirmed coins until the next block, or node1's mempool is full
        results[wallet] = {"node": node_name, "sent": ok, "errors": errors, "txids": txids}

    threads = [threading.Thread(target=worker, args=(w, n)) for w, n, _ in STRESS]
    for t in threads:
        t.start()
    peak = {}
    while any(t.is_alive() for t in threads):
        for name, node in rpc.items():
            try:
                info = node.getmempoolinfo(retry_for=0, timeout=10)
                p = peak.setdefault(name, {"size": 0, "usage": 0, "minfee": "0"})
                p["size"] = max(p["size"], info["size"])
                p["usage"] = max(p["usage"], info["usage"])
                p["minfee"] = str(max(Decimal(p["minfee"]), info["mempoolminfee"]))
            except Exception:
                pass
        time.sleep(5)
    for t in threads:
        t.join()
    submitted = time.time()
    total = sum(r["sent"] for r in results.values())
    log(f"spray: {total} transactions in {round(submitted - started)} s; waiting for confirmations")

    # Everything relayed must confirm. node1's own transactions that its capped
    # mempool refused stay in its wallet unbroadcast; count them separately.
    def unconfirmed():
        count = 0
        for wallet, r in results.items():
            node = rpc[r["node"]].w(wallet)
            r["txids"] = [t for t in r["txids"] if node.gettransaction(t)["confirmations"] < 1]
            count += len(r["txids"])
        return count

    deadline = time.time() + 3 * 3600
    remaining = unconfirmed()
    while remaining and time.time() < deadline:
        if all(rpc[n].getmempoolinfo()["size"] == 0 for n in ("node0", "node2", "node3")):
            break
        time.sleep(30)
        remaining = unconfirmed()
    end_height = rpc["node0"].getblockcount()
    record("spray", transactions=total, seconds_to_submit=round(submitted - started),
           seconds_to_clear=round(time.time() - submitted), blocks=f"{start_height + 1}..{end_height}",
           per_wallet={w: {"node": r["node"], "sent": r["sent"], "errors": r["errors"], "unconfirmed": len(r["txids"])}
                       for w, r in results.items()},
           mempool_peak=peak, node1_maxmempool_mb=5)


def step_reindex_before():
    node2 = rpc["node2"]
    h = node2.getblockcount() - 6
    stats = node2.gettxoutsetinfo("muhash", h, True)
    record("reindex-before", height=h, hash=node2.getblockhash(h), muhash=stats["muhash"],
           total_amount=stats["total_amount"], txouts=stats["txouts"], tip=node2.getblockcount())


def step_reindex_after():
    before = [json.loads(l) for l in open(OUT) if '"reindex-before"' in l][-1]
    node2, node0 = rpc["node2"], rpc["node0"]
    started = time.time()
    wait_for(lambda: node2.getblockcount(retry_for=600) >= node0.getblockcount() - 1
             and all(i["synced"] for i in node2.getindexinfo().values()),
             "node2 reindex and indexes", timeout=6 * 3600, interval=10)
    h = before["height"]
    stats = node2.gettxoutsetinfo("muhash", h, True)
    ok = (node2.getblockhash(h) == before["hash"] and stats["muhash"] == before["muhash"]
          and str(stats["total_amount"]) == str(before["total_amount"]))
    record("reindex-after", ok=ok, height=h, hash_matches=node2.getblockhash(h) == before["hash"],
           muhash_matches=stats["muhash"] == before["muhash"], total_amount=stats["total_amount"],
           indexes=node2.getindexinfo(), tip=node2.getblockcount(), node0_tip=node0.getblockcount(),
           wait_seconds=round(time.time() - started))


def step_txindex():
    node3 = rpc["node3"]
    tip = node3.getblockcount()
    genesis_tx = node3.getblock(node3.getblockhash(0))["tx"][0]
    samples = [(0, genesis_tx)]
    for h in random.sample(range(1, tip + 1), min(300, tip)):
        block = node3.getblock(node3.getblockhash(h))
        samples.append((h, random.choice(block["tx"])))
    ok, bad, started = 0, [], time.time()
    for h, txid in samples:
        tx = node3.getrawtransaction(txid, True)  # no blockhash: the index must find it
        if tx.get("blockhash") == node3.getblockhash(h):
            ok += 1
        else:
            bad.append(txid)
    record("txindex", node="node3", lookups=len(samples), ok=ok, failures=bad, includes_genesis_tx=True,
           ms_per_lookup=round(1000 * (time.time() - started) / len(samples), 1), indexes=node3.getindexinfo())


def set_staking(node, enabled):
    for wallet in node.listwallets():
        node.w(wallet).staking(enabled)


def step_reorg():
    node0, node1 = rpc["node0"], rpc["node1"]
    started = time.time()
    set_staking(node1, False)  # node1 must not build its own branch while it rejects the chain
    wait_for(lambda: node1.getbestblockhash() == node0.getbestblockhash(), "node1 in sync", timeout=600, interval=2)
    h = node1.getblockcount()
    target = node1.getblockhash(h - 1)
    node1.invalidateblock(target)
    after_invalidate = node1.getblockcount()
    invalid_tips = [t for t in node1.getchaintips() if t["status"] == "invalid"]
    wait_height = h + 2
    wait_for(lambda: node0.getblockcount() >= wait_height, f"network height {wait_height}", timeout=1800, interval=5)
    stayed_off = node1.getblockcount() == after_invalidate
    node1.reconsiderblock(target)
    t_reconsider = time.time()
    wait_for(lambda: node1.getbestblockhash() == node0.getbestblockhash(), "node1 rejoins", timeout=900, interval=1)
    rejoin_seconds = round(time.time() - t_reconsider, 1)
    leftover_invalid = [t for t in node1.getchaintips() if t["status"] == "invalid"]
    set_staking(node1, True)
    record("reorg", node="node1", invalidated_height=h - 1, tip_before=h, tip_after_invalidate=after_invalidate,
           invalid_tip_reported=bool(invalid_tips), network_extended_to=node0.getblockcount(),
           stayed_off_invalid_chain=stayed_off, rejoined=True, rejoin_seconds=rejoin_seconds,
           invalid_tips_after_reconsider=len(leftover_invalid),
           window=[started, time.time()])


STEPS = {"fund": step_fund, "spray": step_spray, "reindex-before": step_reindex_before,
         "reindex-after": step_reindex_after, "txindex": step_txindex, "reorg": step_reorg}

if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "record":
        record(**json.loads(sys.argv[2]))
    elif len(sys.argv) == 2 and sys.argv[1] in STEPS:
        STEPS[sys.argv[1]]()
    else:
        sys.exit(__doc__)

#!/usr/bin/env python3
"""Bootstrap the Phase 2 testnet: distribute the genesis premine across five
staking wallets on four nodes, without ever stalling the chain.

Maturity is a confirmation depth (50 blocks on testnet) and genesis outputs are
the only coins exempt from it, so moving every genesis output at once would
leave nothing able to stake and the chain could never advance. The premine
therefore moves in tranches:

  1. node0 imports the testnet genesis key into wallet `genesis`; it stakes
     block 1 from the 1,000 genesis outputs.
  2. Tranche 1: 100 genesis outputs (14,000,000 tFIC each) to each of the five
     staker wallets -- half the premine. The other half keeps staking.
  3. After tranche 1 matures (50 blocks + margin), tranche 2: everything the
     genesis wallet can spend, in 100 equal outputs per staker. Staking on the
     genesis wallet is then switched off, so it stops earning rewards.
  4. After that matures, sweep whatever the genesis wallet still holds (split
     coinstake outputs and rewards that have since matured) to the stakers.

Many outputs per staker, not one: a coin that stakes must wait out maturity
again, so a wallet with one large output could stake once every 50 blocks.

Idempotent: progress is kept in /out/bootstrap-state.json and a rerun resumes.
The WIF is read from the mounted secret and never printed or stored.
"""
import json
import os
import sys
from decimal import ROUND_DOWN, Decimal

from ficrpc import RPCError, log, nodes, wait_for

STATE_PATH = "/out/bootstrap-state.json"
KEY_PATH = "/run/secrets/testnet-genesis-key.txt"
PREMINE = Decimal("14000000000")
GENESIS_OUTPUT_VALUE = Decimal("14000000")
MATURITY = 50
MARGIN = 5
OUTPUTS_PER_STAKER = 100
STAKERS = [("staker1", "node0"), ("staker2", "node1"), ("staker3", "node2"), ("staker4", "node3"), ("staker5", "node1")]
SATS = Decimal("0.00000001")

rpc = nodes()


def load_state():
    if os.path.exists(STATE_PATH):
        return json.load(open(STATE_PATH))
    return {}


def save_state(state):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=1)
    os.replace(tmp, STATE_PATH)


def read_wif():
    for line in open(KEY_PATH):
        key, _, value = line.strip().partition("=")
        if key == "wif" and value:
            return value
    sys.exit(f"no wif= line in {KEY_PATH}")


def height():
    return rpc["node0"].getblockcount()


def ensure_wallet(node_name, wallet):
    node = rpc[node_name]
    if wallet in node.listwallets():
        return
    if wallet in [w["name"] for w in node.listwalletdir()["wallets"]]:
        node.loadwallet(wallet, True)
    else:
        # name, disable_private_keys, blank, passphrase, avoid_reuse, descriptors, load_on_startup
        node.createwallet(wallet, False, False, "", False, True, True)
    log(f"wallet {wallet} ready on {node_name}")


def wait_confirmed(wallet_node, txids, what):
    def confirmed():
        heights = []
        for txid in txids:
            tx = wallet_node.gettransaction(txid)
            if tx["confirmations"] < 1:
                return None
            heights.append(tx["blockheight"])
        return max(heights)

    h = wait_for(confirmed, what, timeout=3 * 3600, interval=15)
    log(f"{what} confirmed by height {h}")
    return h


def wait_height(target, what):
    log(f"waiting for height {target} ({what}); now {height()}")
    wait_for(lambda: height() >= target, f"height {target}", timeout=6 * 3600, interval=30)


def distribute(state, key, per_output):
    """One sendmany per staker, OUTPUTS_PER_STAKER outputs each."""
    genesis = rpc["node0"].w("genesis")
    txids = state.setdefault(key, {})
    for staker, node_name in STAKERS:
        if staker in txids:
            continue
        wallet = rpc[node_name].w(staker)
        addrs = [wallet.getnewaddress(key, "legacy") for _ in range(OUTPUTS_PER_STAKER)]
        amounts = {a: per_output for a in addrs}
        # dummy, amounts, minconf, comment, subtractfeefrom
        txid = genesis.sendmany("", amounts, 1, key, [addrs[0]])
        txids[staker] = txid
        save_state(state)
        log(f"{key}: {OUTPUTS_PER_STAKER} x {per_output} tFIC to {staker} on {node_name}: {txid}")
    return list(txids.values())


def main():
    state = load_state()
    node0 = rpc["node0"]

    log("waiting for the network to connect")
    wait_for(lambda: node0.getconnectioncount() >= 2 and rpc["node2"].getconnectioncount() >= 3
             and rpc["node3"].getconnectioncount() >= 1, "peers", timeout=900, interval=5)

    # 1. Genesis key
    ensure_wallet("node0", "genesis")
    genesis = node0.w("genesis")
    if not state.get("imported"):
        wif = read_wif()
        desc = f"combo({wif})"
        checksum = node0.getdescriptorinfo(desc)["checksum"]
        result = genesis.importdescriptors([{"desc": f"{desc}#{checksum}", "timestamp": 0}])
        del wif, desc
        if not result[0]["success"]:
            sys.exit(f"genesis key import failed: {result[0].get('error')}")
        state["imported"] = True
        save_state(state)
    balances = genesis.getbalances()["mine"]
    log(f"genesis wallet balances: {balances}")
    total = sum(Decimal(v) for v in balances.values())
    if height() == 0 and total != PREMINE:
        sys.exit(f"genesis wallet holds {total}, expected the {PREMINE} premine")

    log("waiting for the genesis wallet to stake block 1")
    wait_height(1, "first staked block")

    # 2. Staker wallets and tranche 1
    for staker, node_name in STAKERS:
        ensure_wallet(node_name, staker)
    if "tranche1_height" not in state:
        txids = distribute(state, "tranche1", GENESIS_OUTPUT_VALUE)
        state["tranche1_height"] = wait_confirmed(genesis, txids, "tranche 1")
        save_state(state)

    # 3. Tranche 2 once tranche 1 can stake
    wait_height(state["tranche1_height"] + MATURITY + MARGIN, "tranche 1 maturity")
    for staker, node_name in STAKERS:
        info = rpc[node_name].w(staker).getstakinginfo()
        log(f"{staker}: staking={info['staking']} weight={info['weight']}")
    if "tranche2_height" not in state:
        if "tranche2" not in state:
            spendable = Decimal(genesis.getbalances()["mine"]["trusted"])
            per_output = ((spendable - Decimal(10)) / (len(STAKERS) * OUTPUTS_PER_STAKER)).quantize(SATS, rounding=ROUND_DOWN)
            state["tranche2_per_output"] = str(per_output)
            save_state(state)
        per_output = Decimal(state["tranche2_per_output"])
        txids = distribute(state, "tranche2", per_output)
        state["tranche2_height"] = wait_confirmed(genesis, txids, "tranche 2")
        save_state(state)
    try:
        genesis.staking(False)
        log("staking disabled on the genesis wallet")
    except RPCError as e:
        log(f"could not disable genesis staking: {e}")

    # 4. Sweep what matured since
    wait_height(state["tranche2_height"] + MATURITY + MARGIN, "tranche 2 maturity")
    if "sweep_height" not in state:
        if "sweep" not in state:
            spendable = Decimal(genesis.getbalances()["mine"]["trusted"])
            if spendable > 1:
                amounts = {}
                share = (spendable / len(STAKERS)).quantize(SATS, rounding=ROUND_DOWN)
                for staker, node_name in STAKERS:
                    amounts[rpc[node_name].w(staker).getnewaddress("sweep", "legacy")] = share
                state["sweep"] = genesis.sendmany("", amounts, 1, "sweep", list(amounts))
                save_state(state)
                log(f"sweep: {share} tFIC to each staker: {state['sweep']}")
        if "sweep" in state:
            state["sweep_height"] = wait_confirmed(genesis, [state["sweep"]], "sweep")
        else:
            state["sweep_height"] = height()
        save_state(state)

    summary = {"height": height(), "genesis": genesis.getbalances()["mine"], "stakers": {}}
    for staker, node_name in STAKERS:
        wallet = rpc[node_name].w(staker)
        summary["stakers"][staker] = {"node": node_name, "balances": wallet.getbalances()["mine"],
                                      "utxos": len(wallet.listunspent(0))}
    state["done"] = True
    save_state(state)
    with open("/out/bootstrap-summary.json", "w") as f:
        json.dump(summary, f, indent=1, default=str)
    log("bootstrap complete: " + json.dumps(summary, default=str))


if __name__ == "__main__":
    main()

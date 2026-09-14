"""6A custodial staking pool logic.

Design: each deposit gets its own dedicated on-chain address/UTXO,
funded once and left alone (never consolidated with other users'
deposits). This means the *chain's own* already-verified PoS reward
logic computes each depositor's reward correctly -- the pool's job is
just to notice when a deposit's UTXO gets staked (produces a coinstake
transaction) and credit that depositor's ledger with the reward minus
the pool fee, never to reimplement the reward formula itself.

Reward model differs from CAC, mechanics don't. CAC's coinstake reward
is coin-age-proportional: hold more, longer, earn more per block, at a
rate the pool could usefully quote as an annualized percentage
(STAKE_REWARD_ANNUAL_BP in CAC's version of this file). FIC's reward is
a fixed 10 FIC plus that block's fees, paid whole to whichever staker's
kernel wins the block (see ../docs/CHANGELOG-FIC.md's Phase 1 section and
docs/genesis.md) -- deposit size affects only the *probability* of a
given deposit's kernel winning a block (stake weight is amount-only, see
CHANGELOG's "Kernel stake weight is already amount-only" note), not the
*size* of the reward when it does. There is no annual/monthly rate this
pool can honestly quote a depositor, so status_for_user() below reports
0 for effective_monthly_rate_bp rather than porting CAC's env-var-driven
constant -- see ../firstislamiccoin-mobile/docs/mobile-api.md section 5's
matching note. What doesn't change at all: _attribute_rewards() below
reads the reward directly off the real coinstake transaction's own
outputs-minus-inputs, exactly like CAC's version, and that computation
is correct regardless of which reward model produced the number -- it
never assumes coin-age or fixed-amount, it just reads what actually
happened on-chain.

Known simplification (see README.md): withdraw() closes out all of a
user's active deposits rather than supporting partial withdrawal from a
specific deposit -- fine for this phase's verification scope, a real
production pool would need per-deposit partial-withdrawal accounting.
"""
import os

import db
import push
import referral
import rpc
from rpc import RpcError


def _notify_user(user_id, title, body):
    """Best-effort: sends to every subscription this user has registered
    (e.g. more than one browser/device). Never raises -- see push.py's
    own note on why a dead subscription shouldn't fail a watcher pass
    that's also crediting real money."""
    with db.db() as conn:
        subs = conn.execute(
            "SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE user_id = ?", (user_id,)
        ).fetchall()
    for s in subs:
        push.send_notification(
            {"endpoint": s["endpoint"], "keys": {"p256dh": s["p256dh"], "auth": s["auth"]}},
            title, body,
        )

POOL_WALLET = os.environ.get("GATEWAY_POOL_WALLET", "stakingpool")
POOL_FEE_BP = int(os.environ.get("GATEWAY_POOL_FEE_BP", "500"))
COIN = 100_000_000


class StakingError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def ensure_pool_wallet_loaded():
    loaded = rpc.call("listwallets", wallet="")
    if POOL_WALLET in loaded:
        return
    try:
        rpc.call("loadwallet", [POOL_WALLET], wallet="")
        return
    except RpcError as e:
        on_disk = {w["name"] for w in rpc.call("listwalletdir", wallet="")["wallets"]}
        if POOL_WALLET in on_disk:
            # Exists on disk but couldn't load -- e.g. another
            # firstislamiccoind process already has it open (confirmed to
            # happen locally with CAC's own gateway: killing it with
            # SIGKILL mid-RPC-call can leave the *node's* wallet manager
            # holding a stale handle on a wallet this process itself
            # asked it to load). Don't fall through to createwallet,
            # which would just fail confusingly with "already exists" --
            # surface the real problem instead.
            raise RpcError(
                e.code, f"Wallet '{POOL_WALLET}' exists on disk but failed to load: {e.message}"
            )
    rpc.call("createwallet", [POOL_WALLET], wallet="")


def create_deposit(user_id):
    ensure_pool_wallet_loaded()
    address = rpc.call("getnewaddress", [f"deposit:pending", "legacy"], wallet=POOL_WALLET)
    with db.db() as conn:
        cur = conn.execute(
            "INSERT INTO stake_deposits (user_id, deposit_address, status, created_at) VALUES (?, ?, 'awaiting_funds', ?)",
            (user_id, address, db.now()),
        )
        deposit_id = cur.lastrowid
        conn.commit()
    # Re-label with the real deposit id now that we have one, so the
    # watcher can filter listtransactions by it later.
    rpc.call("setlabel", [address, f"deposit:{deposit_id}"], wallet=POOL_WALLET)
    return address


def _mark_funded_deposits():
    """Scans the pool wallet for deposits that now have funds and marks
    them active. Idempotent -- safe to call repeatedly."""
    ensure_pool_wallet_loaded()
    with db.db() as conn:
        pending = conn.execute(
            "SELECT id, user_id, deposit_address FROM stake_deposits WHERE status = 'awaiting_funds'"
        ).fetchall()
    for dep in pending:
        utxos = rpc.call("listunspent", [1, 9999999, [dep["deposit_address"]]], wallet=POOL_WALLET)
        if not utxos:
            continue
        u = utxos[0]
        amount_sat = round(u["amount"] * COIN)
        with db.db() as conn:
            conn.execute(
                "UPDATE stake_deposits SET status='active', funding_txid=?, funding_vout=?, amount_satoshis=? WHERE id=?",
                (u["txid"], u["vout"], amount_sat, dep["id"]),
            )
            conn.commit()
        _notify_user(
            dep["user_id"], "Deposit received",
            f"Your deposit of {amount_sat / COIN:.8f} FIC is confirmed and will begin staking.",
        )
        referral.credit_referral_if_eligible(dep["user_id"], dep["id"], amount_sat)


def _is_coinstake(tx):
    return (
        len(tx["vin"]) > 0
        and "coinbase" not in tx["vin"][0]
        and len(tx["vout"]) >= 2
        and float(tx["vout"][0]["value"]) == 0
        and tx["vout"][0]["scriptPubKey"].get("hex", "") == ""
    )


def _attribute_rewards():
    """Watcher pass: for every active deposit whose funding UTXO has been
    spent, finds the spending transaction, confirms it's a coinstake
    (per CTransaction::IsCoinStake's exact definition, unchanged from
    CAC -- see transaction.h), and credits the depositor's reward ledger.
    Dedupes on coinstake_txid so this is safe to call on a timer without
    double-crediting."""
    ensure_pool_wallet_loaded()
    with db.db() as conn:
        active = conn.execute(
            "SELECT id, user_id, funding_txid, funding_vout FROM stake_deposits WHERE status = 'active'"
        ).fetchall()
    for dep in active:
        try:
            still_unspent = rpc.call("gettxout", [dep["funding_txid"], dep["funding_vout"], True])
        except RpcError:
            continue
        if still_unspent is not None:
            continue  # not staked yet
        history = rpc.call("listtransactions", [f"deposit:{dep['id']}", 50, 0, True], wallet=POOL_WALLET)
        for t in history:
            txid = t["txid"]
            with db.db() as conn:
                already = conn.execute(
                    "SELECT 1 FROM stake_rewards WHERE coinstake_txid = ?", (txid,)
                ).fetchone()
            if already:
                continue
            try:
                tx = rpc.call("getrawtransaction", [txid, True])
            except RpcError:
                continue
            if not _is_coinstake(tx):
                continue
            spends_our_utxo = any(
                vin.get("txid") == dep["funding_txid"] and vin.get("vout") == dep["funding_vout"]
                for vin in tx["vin"]
            )
            if not spends_our_utxo:
                continue
            out_total = sum(round(o["value"] * COIN) for o in tx["vout"])
            in_total = 0
            for vin in tx["vin"]:
                prevtx2 = rpc.call("getrawtransaction", [vin["txid"], True])
                in_total += round(prevtx2["vout"][vin["vout"]]["value"] * COIN)
            gross = out_total - in_total
            pool_fee = gross * POOL_FEE_BP // 10000
            net = gross - pool_fee
            with db.db() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO stake_rewards "
                    "(deposit_id, coinstake_txid, gross_reward_satoshis, pool_fee_satoshis, net_reward_satoshis, credited_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (dep["id"], txid, gross, pool_fee, net, db.now()),
                )
                conn.commit()
            _notify_user(
                dep["user_id"], "Staking reward earned",
                f"You earned {net / COIN:.8f} FIC from staking (after pool fee).",
            )


def run_watcher_pass():
    """Call periodically (see README.md's systemd timer) to keep deposit
    status and reward attribution up to date."""
    _mark_funded_deposits()
    _attribute_rewards()


def status_for_user(user_id):
    with db.db() as conn:
        deposits = conn.execute(
            "SELECT id, amount_satoshis, status FROM stake_deposits WHERE user_id = ?", (user_id,)
        ).fetchall()
        rewards_total = 0
        active_deposit_ids = [d["id"] for d in deposits if d["status"] == "active"]
        if active_deposit_ids:
            # Only rewards belonging to still-active deposits count as
            # "accrued" -- withdraw() pays out a deposit's principal and
            # every reward credited to it together in one transaction
            # (see withdraw()'s docstring), so a withdrawn deposit's
            # rewards are already gone, not still outstanding.
            placeholders = ",".join("?" * len(active_deposit_ids))
            row = conn.execute(
                f"SELECT COALESCE(SUM(net_reward_satoshis), 0) AS total FROM stake_rewards "
                f"WHERE deposit_id IN ({placeholders})",
                active_deposit_ids,
            ).fetchone()
            rewards_total = row["total"]
    delegated = sum(d["amount_satoshis"] or 0 for d in deposits if d["status"] == "active")
    return {
        "mode": "custodial",
        "delegated_amount": str(delegated),
        "accrued_rewards": str(rewards_total),
        # No honest rate to quote -- see this module's docstring. Kept as
        # a field (not dropped) for wire-shape stability with CAC's
        # original contract; 0 here, not a fabricated number.
        "effective_monthly_rate_bp": 0,
        "pool_fee_bp": POOL_FEE_BP,
        "can_withdraw": delegated > 0 or rewards_total > 0,
    }


def withdraw(user_id, amount_satoshis, to_address):
    status = status_for_user(user_id)
    available = int(status["delegated_amount"]) + int(status["accrued_rewards"])
    if amount_satoshis > available:
        raise StakingError(
            "invalid-address", f"Requested {amount_satoshis} exceeds available balance {available}"
        )
    ensure_pool_wallet_loaded()
    amount_fic = amount_satoshis / COIN
    try:
        txid = rpc.call("sendtoaddress", [to_address, amount_fic], wallet=POOL_WALLET)
    except RpcError as e:
        # A ledger balance can be "available" per our accounting before the
        # underlying coinstake output (principal + reward, recombined into
        # one output by the chain itself) has matured on-chain -- same
        # maturity rule as everywhere else in this project, just surfaced
        # here as a clean, expected error instead of a raw RPC failure.
        if e.code == -6:
            raise StakingError(
                "not-found",
                "Funds are still maturing on-chain and aren't spendable yet -- try again shortly.",
            )
        raise StakingError("invalid-address", f"Withdrawal failed: {e.message}")
    with db.db() as conn:
        conn.execute(
            "UPDATE stake_deposits SET status='withdrawn', withdrawn_at=? WHERE user_id=? AND status='active'",
            (db.now(), user_id),
        )
        conn.commit()
    return txid

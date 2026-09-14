"""Referral reward: a referrer gets REFERRAL_REWARD_BP (10%, matching the
project's existing basis-point convention -- see POOL_FEE_BP in
staking.py) of a referred user's first funded deposit.

Funding source, deliberately not the pool: paid from a dedicated
ADMIN_WALLET, funded by the project owner's own action, not the pool
wallet that holds other users' custodial deposits. FIC's coin supply is
otherwise fixed by design -- premine plus staking rewards only, no dev
fund (see ../docs/tokenomics.md: "no developer fund"), same as CAC -- so
this reward can't come from newly-minted FIC either; it has to be real
FIC someone deliberately set aside.

Crediting (this module, called from staking.py's watcher pass) only ever
writes a ledger row -- no funds move until the referrer explicitly
withdraws via /v1/referral/withdraw, which is the only place this module
calls sendtoaddress. Mirrors staking.py's withdraw() pattern exactly.
"""
import os
import secrets

import db
import rpc
from rpc import RpcError

ADMIN_WALLET = os.environ.get("GATEWAY_ADMIN_WALLET", "adminwallet")
REFERRAL_REWARD_BP = int(os.environ.get("GATEWAY_REFERRAL_REWARD_BP", "1000"))  # 10%
COIN = 100_000_000


class ReferralError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def ensure_admin_wallet_loaded():
    loaded = rpc.call("listwallets", wallet="")
    if ADMIN_WALLET in loaded:
        return
    try:
        rpc.call("loadwallet", [ADMIN_WALLET], wallet="")
        return
    except RpcError as e:
        on_disk = {w["name"] for w in rpc.call("listwalletdir", wallet="")["wallets"]}
        if ADMIN_WALLET in on_disk:
            raise RpcError(
                e.code, f"Wallet '{ADMIN_WALLET}' exists on disk but failed to load: {e.message}"
            )
    rpc.call("createwallet", [ADMIN_WALLET], wallet="")


def generate_referral_code():
    # 8 chars of base32-ish alphabet, short enough to type/share, long
    # enough that guessing a real one is impractical.
    return secrets.token_urlsafe(6).replace("_", "").replace("-", "")[:8].upper()


def credit_referral_if_eligible(user_id, deposit_id, amount_satoshis):
    """Called right after a deposit is marked 'active' in staking.py.
    Credits the referrer once per referred user, only for that user's
    very first funded deposit -- checked by seeing whether this is the
    only 'active'-or-later deposit this user has ever had."""
    with db.db() as conn:
        user = conn.execute("SELECT referred_by FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user or not user["referred_by"]:
            return
        already_credited = conn.execute(
            "SELECT 1 FROM referral_credits WHERE referred_user_id = ?", (user_id,)
        ).fetchone()
        if already_credited:
            return
        prior_deposits = conn.execute(
            "SELECT COUNT(*) AS n FROM stake_deposits WHERE user_id = ? AND status != 'awaiting_funds' AND id != ?",
            (user_id, deposit_id),
        ).fetchone()["n"]
        if prior_deposits > 0:
            return  # not their first funded deposit
        reward_satoshis = amount_satoshis * REFERRAL_REWARD_BP // 10_000
        if reward_satoshis <= 0:
            return
        conn.execute(
            """INSERT INTO referral_credits
               (referrer_user_id, referred_user_id, source_deposit_id, amount_satoshis, credited_at)
               VALUES (?, ?, ?, ?, ?)""",
            (user["referred_by"], user_id, deposit_id, reward_satoshis, db.now()),
        )
        conn.commit()


def _mask_email(email):
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    visible = local[:1] or "*"
    return f"{visible}{'*' * max(len(local) - 1, 3)}@{domain}"


def history_for_user(user_id):
    """Every user this account referred, whether or not they've funded a
    deposit yet -- not just the ones that generated a credit -- so a
    referrer can see who signed up with their code, not only who's paid
    out. Referred users' emails are masked; this is the referrer's own
    dashboard, not an admin tool, so full contact details of someone
    else's account shouldn't be exposed here."""
    with db.db() as conn:
        rows = conn.execute(
            """SELECT u.email, u.created_at AS joined_at,
                      rc.amount_satoshis, rc.credited_at, rc.withdrawn_at
               FROM users u
               LEFT JOIN referral_credits rc
                 ON rc.referred_user_id = u.id AND rc.referrer_user_id = ?
               WHERE u.referred_by = ?
               ORDER BY u.created_at DESC""",
            (user_id, user_id),
        ).fetchall()
    return [
        {
            "referred_email_masked": _mask_email(row["email"]),
            "joined_at": row["joined_at"],
            "amount_satoshis": row["amount_satoshis"],
            "credited_at": row["credited_at"],
            "withdrawn": row["withdrawn_at"] is not None,
        }
        for row in rows
    ]


def status_for_user(user_id):
    with db.db() as conn:
        row = conn.execute("SELECT referral_code FROM users WHERE id = ?", (user_id,)).fetchone()
        referred_count = conn.execute(
            "SELECT COUNT(*) AS n FROM users WHERE referred_by = ?", (user_id,)
        ).fetchone()["n"]
        available = conn.execute(
            "SELECT COALESCE(SUM(amount_satoshis), 0) AS s FROM referral_credits WHERE referrer_user_id = ? AND withdrawn_at IS NULL",
            (user_id,),
        ).fetchone()["s"]
        lifetime = conn.execute(
            "SELECT COALESCE(SUM(amount_satoshis), 0) AS s FROM referral_credits WHERE referrer_user_id = ?",
            (user_id,),
        ).fetchone()["s"]
    return {
        "referral_code": row["referral_code"],
        "referred_count": referred_count,
        "available_satoshis": available,
        "lifetime_satoshis": lifetime,
    }


def withdraw(user_id, to_address):
    status = status_for_user(user_id)
    amount_satoshis = status["available_satoshis"]
    if amount_satoshis <= 0:
        raise ReferralError("invalid-address", "No referral credit available to withdraw")
    ensure_admin_wallet_loaded()
    amount_fic = amount_satoshis / COIN
    try:
        txid = rpc.call("sendtoaddress", [to_address, amount_fic], wallet=ADMIN_WALLET)
    except RpcError as e:
        if e.code == -6:
            raise ReferralError(
                "not-found",
                "The admin wallet doesn't have enough confirmed funds right now -- try again shortly, or contact the project.",
            )
        raise ReferralError("invalid-address", f"Withdrawal failed: {e.message}")
    with db.db() as conn:
        conn.execute(
            "UPDATE referral_credits SET withdrawn_at=?, withdrawal_txid=? WHERE referrer_user_id=? AND withdrawn_at IS NULL",
            (db.now(), txid, user_id),
        )
        conn.commit()
    return txid

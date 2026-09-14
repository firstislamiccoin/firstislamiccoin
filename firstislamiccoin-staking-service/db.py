"""SQLite storage for the gateway: user accounts, the staking pool's
per-user ledger, and the set of addresses the gateway node has imported
watch-only (see README.md for why watch-only import is this phase's
chosen backend instead of Electrum -- PARAMETERS.md section 13.1 has the
full reasoning)."""
import os
import sqlite3
import time
from contextlib import contextmanager

DB_PATH = os.environ.get("GATEWAY_DB_PATH", os.path.join(os.path.dirname(__file__), "gateway.db"))


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at REAL NOT NULL,
                full_name TEXT,
                date_of_birth TEXT,
                id_type TEXT,
                id_number_encrypted TEXT,
                referral_code TEXT UNIQUE,
                referred_by INTEGER REFERENCES users(id)
            )
            """
        )
        # Signup originally had no KYC/referral fields (see PARAMETERS.md
        # section 13.6) -- ALTER TABLE ADD COLUMN for anyone whose users
        # table already exists from before these columns were added.
        # SQLite has no "ADD COLUMN IF NOT EXISTS", so check first.
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        for col in ("full_name", "date_of_birth", "id_type", "id_number_encrypted", "referral_code", "referred_by"):
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watched_addresses (
                address TEXT PRIMARY KEY,
                imported_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stake_deposits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                deposit_address TEXT NOT NULL UNIQUE,
                funding_txid TEXT,
                funding_vout INTEGER,
                amount_satoshis INTEGER,
                status TEXT NOT NULL DEFAULT 'awaiting_funds',
                created_at REAL NOT NULL,
                withdrawn_at REAL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_deposits_user ON stake_deposits(user_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stake_rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deposit_id INTEGER NOT NULL REFERENCES stake_deposits(id),
                coinstake_txid TEXT NOT NULL UNIQUE,
                gross_reward_satoshis INTEGER NOT NULL,
                pool_fee_satoshis INTEGER NOT NULL,
                net_reward_satoshis INTEGER NOT NULL,
                credited_at REAL NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rewards_deposit ON stake_rewards(deposit_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                endpoint TEXT NOT NULL UNIQUE,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_push_user ON push_subscriptions(user_id)")
        # Native mobile push (FCM), keyed by address rather than a user
        # account -- unlike push_subscriptions (Web Push, tied to a
        # staking-service login), the mobile app doesn't require signing
        # in just to watch an address for incoming payments, so this
        # follows the same no-auth-required, address-keyed convention as
        # /v1/address/<address>/balance and friends. last_notified_balance
        # is how mobile_notify.py detects a *new* increase rather than
        # re-notifying the same balance on every watcher pass.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mobile_push_registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                platform TEXT NOT NULL,
                token TEXT NOT NULL,
                last_notified_balance INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                UNIQUE(address, token)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mobile_push_address ON mobile_push_registrations(address)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS referral_credits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_user_id INTEGER NOT NULL REFERENCES users(id),
                referred_user_id INTEGER NOT NULL REFERENCES users(id),
                source_deposit_id INTEGER NOT NULL REFERENCES stake_deposits(id),
                amount_satoshis INTEGER NOT NULL,
                credited_at REAL NOT NULL,
                withdrawn_at REAL,
                withdrawal_txid TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_referral_credits_referrer ON referral_credits(referrer_user_id)")
        # ALTER TABLE ADD COLUMN can't express UNIQUE, so enforce it via a
        # separate index instead -- covers both a fresh CREATE TABLE (whose
        # inline UNIQUE already exists) and an existing install that just
        # got the column added above.
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code)")
        # One-shot FIC/USD price-threshold alerts (see price_alerts.py).
        # channel='web' rows are user_id-keyed (delivered via the same
        # push_subscriptions a logged-in user already has from the
        # staking screen's "Enable notifications"); channel='mobile' rows
        # are address+token-keyed, following mobile_push_registrations'
        # no-login convention. Exactly one of (user_id) / (address, token)
        # is populated depending on channel.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS price_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL,
                user_id INTEGER REFERENCES users(id),
                address TEXT,
                token TEXT,
                direction TEXT NOT NULL,
                threshold_usd REAL NOT NULL,
                created_at REAL NOT NULL,
                triggered_at REAL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_price_alerts_web ON price_alerts(channel, user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_price_alerts_mobile ON price_alerts(channel, address, token)")
        conn.commit()


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def now():
    return time.time()

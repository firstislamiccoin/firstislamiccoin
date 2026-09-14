#!/usr/bin/env python3
"""FirstIslamicCoin mobile/web gateway -- implements
../firstislamiccoin-mobile/docs/mobile-api.md.

Backend choice: this implementation queries firstislamiccoind directly
via RPC, using a dedicated watch-only wallet ("gateway" by default) that
imports any address it's asked about on first use, rather than talking
to firstislamiccoin-electrumx as mobile-api.md's architecture section
describes. mobile-api.md's own design explicitly treats the gateway's
backend as an internal detail -- the client-facing REST contract below
is unchanged either way.

This is the same substitution CAC's own vps-gateway made, for a related
but distinct reason: CAC's electrumx-cac existed but was blocked locally
by a macOS packaging issue; FIC's firstislamiccoin-electrumx (Phase 4)
does not exist at all yet (see ../docs/repo-map.md's "Two mapping
caveats"). Either way, this substitution is what makes it possible to
have something actually runnable and verifiable end-to-end right now
rather than waiting on Phase 4. See README.md's "Known limitation"
section before deploying this to a chain with real transaction history.

Configuration is via environment variables (see README.md):
    FIC_RPC_HOST, FIC_RPC_PORT, FIC_RPC_COOKIEFILE, or FIC_RPC_USER/FIC_RPC_PASSWORD
    FIC_NETWORK              (default: mainnet -- cosmetic only, see rpc.py)
    GATEWAY_WATCH_WALLET     (default: gateway)
    GATEWAY_JWT_SECRET       (generate a real one for prod)
    GATEWAY_DB_PATH
    GATEWAY_POOL_FEE_BP      (default: 500 = 5%, matches firstislamiccoin-mobile's placeholder)
    GATEWAY_VAPID_PUBLIC_KEY / GATEWAY_VAPID_PRIVATE_KEY_PATH / GATEWAY_VAPID_SUBJECT
                             (Web Push -- see push.py and README.md's "Web Push" section)
    GATEWAY_FCM_SERVICE_ACCOUNT_PATH
                             (native mobile push via FCM -- see push_mobile.py)
    GATEWAY_KYC_ENCRYPTION_KEY
                             (Fernet key encrypting signup ID numbers at rest --
                              see kyc.py. Signup returns 503 without it.)
    GATEWAY_ADMIN_WALLET     (default: adminwallet -- funds referral payouts, see
                              referral.py. Must be funded manually by the project;
                              withdrawals fail with a clean error if it's empty.)
    GATEWAY_REFERRAL_REWARD_BP
                             (default: 1000 = 10%, see referral.py)

Fee estimation (/v1/fee-estimate) uses the node's live mempoolminfee and
mempool fullness as a heuristic -- see that endpoint's own comment for
why this codebase can't do real estimatesmartfee-style calibration.
"""
import datetime
import os
import time

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import auth
import db
import kyc
import price_alerts
import referral
import rpc
import staking
from rpc import RpcError

COIN = 100_000_000
NETWORK = os.environ.get("FIC_NETWORK", "mainnet")
WATCH_WALLET = os.environ.get("GATEWAY_WATCH_WALLET", "gateway")
FEE_RATE_SAT_VB = os.environ.get("GATEWAY_FEE_RATE_SAT_VB", "1000")

app = Flask(__name__)
# Web wallets (../firstislamiccoin-web-wallet/, not built yet -- see
# ../docs/repo-map.md) are, by definition, served from a different
# origin than this API -- browsers block cross-origin fetch() without
# this. Mobile apps (../firstislamiccoin-mobile/) don't go through a
# browser so this has no effect on them either way.
CORS(app, resources={r"/v1/*": {"origins": os.environ.get("GATEWAY_CORS_ORIGINS", "*")}})
limiter = Limiter(get_remote_address, app=app, default_limits=["120 per minute"], storage_uri="memory://")


def error(code, message, status=400, details=None):
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return jsonify(body), status


def require_auth():
    """Returns (user_id, None) or (None, error_response)."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None, error("unauthorized", "Missing or malformed Authorization header", 401)
    user_id = auth.verify_token(header[len("Bearer "):])
    if user_id is None:
        return None, error("unauthorized", "Invalid or expired token", 401)
    return user_id, None


def ensure_wallet_loaded():
    """Idempotently ensures the gateway's watch-only wallet exists and is
    loaded. Safe to call on every request that needs it -- cheap once the
    wallet is already loaded (a single listwallets RPC round-trip).

    Descriptor wallet (not legacy/BDB): matches CAC's own reasoning --
    modern nodes have BDB wallet creation disabled by default, so
    importdescriptors (descriptor wallet) is used instead of the
    deprecated importaddress (legacy/BDB wallet) path."""
    loaded = rpc.call("listwallets", wallet="")
    if WATCH_WALLET in loaded:
        return
    try:
        rpc.call("loadwallet", [WATCH_WALLET], wallet="")
        return
    except RpcError as e:
        on_disk = {w["name"] for w in rpc.call("listwalletdir", wallet="")["wallets"]}
        if WATCH_WALLET in on_disk:
            # See staking.py's ensure_pool_wallet_loaded for why this is
            # checked explicitly rather than falling through to
            # createwallet (which would just fail confusingly instead).
            raise RpcError(
                e.code, f"Wallet '{WATCH_WALLET}' exists on disk but failed to load: {e.message}"
            )
    rpc.call("createwallet", [WATCH_WALLET, True, True, "", False, True], wallet="")  # disable_private_keys=True, descriptors=True


def ensure_address_watched(address):
    with db.db() as conn:
        row = conn.execute("SELECT 1 FROM watched_addresses WHERE address = ?", (address,)).fetchone()
        if row:
            return
    ensure_wallet_loaded()
    # timestamp=0: rescan from genesis to pick up any history the address
    # already has before the gateway first heard about it. Cheap on this
    # project's current chain size -- see README.md's "Known limitation"
    # section for why this doesn't scale to a mature mainnet without
    # switching to an indexed backend (firstislamiccoin-electrumx).
    info = rpc.call("getdescriptorinfo", [f"addr({address})"])
    result = rpc.call(
        "importdescriptors",
        [[{"desc": info["descriptor"], "timestamp": 0, "watchonly": True, "label": address}]],
        wallet=WATCH_WALLET,
    )
    if not result[0].get("success"):
        raise RpcError(-1, f"importdescriptors failed: {result[0].get('error')}")
    with db.db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO watched_addresses (address, imported_at) VALUES (?, ?)",
            (address, db.now()),
        )
        conn.commit()


def is_valid_address(address):
    try:
        result = rpc.call("validateaddress", [address])
        return bool(result.get("isvalid"))
    except RpcError:
        return False


# ---------------------------------------------------------------- section 1


@app.route("/v1/network/status")
def network_status():
    try:
        info = rpc.call("getblockchaininfo")
    except RpcError as e:
        return error("electrum-backend-unavailable", str(e), 502)
    return jsonify({
        "network": info["chain"],
        "chain_height": info["blocks"],
        "best_block_hash": info["bestblockhash"],
        "backend": "rpc",  # deviation from spec's electrum_servers_* fields -- see module docstring
        "backend_healthy": True,
    })


# ---------------------------------------------------------------- section 2


@app.route("/v1/address/<address>/balance")
@limiter.limit("60 per minute")
def address_balance(address):
    if not is_valid_address(address):
        return error("invalid-address", "Not a valid FirstIslamicCoin address", 400)
    ensure_address_watched(address)
    utxos = rpc.call(
        "listunspent", [0, 9999999, [address], True], wallet=WATCH_WALLET
    )
    confirmed = sum(round(u["amount"] * COIN) for u in utxos if u["confirmations"] > 0)
    unconfirmed = sum(round(u["amount"] * COIN) for u in utxos if u["confirmations"] == 0)
    return jsonify({"address": address, "confirmed": str(confirmed), "unconfirmed": str(unconfirmed)})


# ---------------------------------------------------------------- section 3


@app.route("/v1/address/<address>/utxos")
@limiter.limit("60 per minute")
def address_utxos(address):
    if not is_valid_address(address):
        return error("invalid-address", "Not a valid FirstIslamicCoin address", 400)
    ensure_address_watched(address)
    tip = rpc.call("getblockcount")
    raw = rpc.call("listunspent", [0, 9999999, [address], True], wallet=WATCH_WALLET)
    utxos = []
    for u in raw:
        confs = u["confirmations"]
        height = (tip - confs + 1) if confs > 0 else None
        utxos.append({
            "txid": u["txid"],
            "vout": u["vout"],
            "value": str(round(u["amount"] * COIN)),
            "height": height,
            "confirmations": confs,
        })
    return jsonify({"address": address, "utxos": utxos})


# ---------------------------------------------------------------- section 4


@app.route("/v1/address/<address>/history")
@limiter.limit("60 per minute")
def address_history(address):
    if not is_valid_address(address):
        return error("invalid-address", "Not a valid FirstIslamicCoin address", 400)
    ensure_address_watched(address)
    try:
        limit = int(request.args.get("limit", "50"))
    except ValueError:
        return error("invalid-address", "limit must be an integer", 400)  # reusing code; not address-specific but keeps error shape simple
    before_height = request.args.get("before_height")
    before_height = int(before_height) if before_height else None

    raw = rpc.call("listtransactions", [address, max(limit * 2, 100), 0, True], wallet=WATCH_WALLET)
    seen = set()
    txs = []
    for t in raw:
        txid = t["txid"]
        if txid in seen:
            continue
        seen.add(txid)
        height = t.get("blockheight")
        if before_height is not None and height is not None and height >= before_height:
            continue
        txs.append({"txid": txid, "height": height, "fee": None})
    txs.sort(key=lambda t: (t["height"] is None, -(t["height"] or 0)))
    has_more = len(txs) > limit
    return jsonify({"address": address, "transactions": txs[:limit], "has_more": has_more})


@app.route("/v1/tx/<txid>")
def tx_detail(txid):
    try:
        tx = rpc.call("getrawtransaction", [txid, True])
    except RpcError:
        return error("not-found", "No such transaction", 404)

    is_coinstake = (
        len(tx["vin"]) > 0
        and "coinbase" not in tx["vin"][0]
        and len(tx["vout"]) >= 2
        and float(tx["vout"][0]["value"]) == 0
        and tx["vout"][0]["scriptPubKey"].get("hex", "") == ""
    )
    reward_satoshis = None
    if is_coinstake:
        out_total = sum(round(o["value"] * COIN) for o in tx["vout"])
        in_total = 0
        for vin in tx["vin"]:
            prevtx = rpc.call("getrawtransaction", [vin["txid"], True])
            in_total += round(prevtx["vout"][vin["vout"]]["value"] * COIN)
        reward_satoshis = out_total - in_total

    height = None
    confirmations = tx.get("confirmations", 0)
    if "blockhash" in tx:
        block = rpc.call("getblock", [tx["blockhash"], 1])
        height = block["height"]

    return jsonify({
        "txid": txid,
        "height": height,
        "confirmations": confirmations,
        "is_coinstake": is_coinstake,
        "reward_satoshis": str(reward_satoshis) if reward_satoshis is not None else None,
        "vin": tx["vin"],
        "vout": tx["vout"],
    })


@app.route("/v1/tx/broadcast", methods=["POST"])
@limiter.limit("20 per minute")
def broadcast():
    body = request.get_json(silent=True) or {}
    raw_hex = body.get("raw_tx_hex")
    if not raw_hex:
        return error("tx-rejected", "raw_tx_hex is required", 400)
    try:
        txid = rpc.call("sendrawtransaction", [raw_hex])
    except RpcError as e:
        return error("tx-rejected", e.message, 400)
    return jsonify({"txid": txid})


@app.route("/v1/fee-estimate")
def fee_estimate():
    # This Bitcoin-Core-derived codebase has no estimatesmartfee-style RPC
    # (confirmed empirically on CAC's identical codebase -- absent from
    # `help` output; FIC inherits the same RPC surface), which normally
    # calibrates against real confirmed-transaction fee/confirmation-time
    # history. What this DOES do, that a hardcoded constant didn't: use
    # the node's own real mempoolminfee as the floor (a real, live value
    # that can differ per network/node config, not something to
    # hardcode), and scale up from there based on actual current mempool
    # backlog relative to how many blocks the caller is willing to wait.
    # Documented as a heuristic, not a real fee market simulation.
    target = int(request.args.get("target_blocks", "6"))
    if target < 1:
        return error("invalid-request", "target_blocks must be >= 1")
    try:
        mempool = rpc.call("getmempoolinfo")
    except RpcError as e:
        return error("rpc-error", e.message, 502)

    min_rate = max(1, round(mempool["mempoolminfee"] * COIN / 1000))  # BTC/kvB -> sat/vB
    mempool_bytes = mempool["bytes"]
    max_mempool_bytes = mempool["maxmempool"]
    fullness = min(1.0, mempool_bytes / max_mempool_bytes) if max_mempool_bytes else 0.0

    # Urgency multiplier: an empty/light mempool needs nothing above the
    # floor regardless of target_blocks (nothing to compete with); a
    # fuller mempool scales the multiplier up, more steeply the fewer
    # blocks the caller is willing to wait for. Capped at 10x the floor
    # so a congested mempool can't produce an unbounded fee suggestion.
    urgency = 1.0 + fullness * (10.0 / target)
    fee_rate = min(round(min_rate * urgency), min_rate * 10)

    return jsonify({
        "target_blocks": target,
        "fee_rate_sat_per_vbyte": str(fee_rate),
        "mempool_min_fee_sat_per_vbyte": str(min_rate),
        "mempool_fullness": round(fullness, 4),
    })


# ---------------------------------------------------------- account signup


@app.route("/v1/auth/signup", methods=["POST"])
@limiter.limit("10 per hour")
def signup():
    # Signup fields below (full_name/date_of_birth/id_type/id_number) are
    # self-attested, not verified -- see kyc.py's module docstring. Not a
    # substitute for real identity verification; don't treat a filled-in
    # ID number as proof of anything.
    if not kyc.configured():
        return error("rpc-error", "Signup is temporarily unavailable (server misconfigured)", 503)

    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    full_name = (body.get("full_name") or "").strip()
    date_of_birth = (body.get("date_of_birth") or "").strip()
    id_type = (body.get("id_type") or "").strip().lower()
    id_number = (body.get("id_number") or "").strip()
    referral_code_used = (body.get("referral_code") or "").strip().upper()

    if not email or "@" not in email or len(password) < 8:
        return error("invalid-address", "Valid email and password (>=8 chars) required", 400)
    if not full_name:
        return error("invalid-address", "Full name is required", 400)
    try:
        dob = datetime.date.fromisoformat(date_of_birth)
    except ValueError:
        return error("invalid-address", "date_of_birth must be YYYY-MM-DD", 400)
    if dob >= datetime.date.today() or dob.year < 1900:
        return error("invalid-address", "date_of_birth is not a valid birth date", 400)
    if id_type not in kyc.VALID_ID_TYPES:
        return error("invalid-address", f"id_type must be one of {sorted(kyc.VALID_ID_TYPES)}", 400)
    if not id_number:
        return error("invalid-address", "id_number is required", 400)

    with db.db() as conn:
        existing = conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            return error("invalid-address", "An account with that email already exists", 409)

        referred_by = None
        if referral_code_used:
            referrer = conn.execute(
                "SELECT id FROM users WHERE referral_code = ?", (referral_code_used,)
            ).fetchone()
            if not referrer:
                return error("invalid-address", "Unknown referral code", 400)
            referred_by = referrer["id"]

        # Retry on the astronomically unlikely event of a referral_code
        # collision (8 chars of a ~32-symbol alphabet) rather than failing
        # signup outright.
        for _ in range(5):
            own_referral_code = referral.generate_referral_code()
            if not conn.execute(
                "SELECT 1 FROM users WHERE referral_code = ?", (own_referral_code,)
            ).fetchone():
                break

        cur = conn.execute(
            """INSERT INTO users
               (email, password_hash, created_at, full_name, date_of_birth, id_type, id_number_encrypted,
                referral_code, referred_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                email,
                auth.hash_password(password),
                db.now(),
                full_name,
                date_of_birth,
                id_type,
                kyc.encrypt_id_number(id_number),
                own_referral_code,
                referred_by,
            ),
        )
        conn.commit()
        user_id = cur.lastrowid
    return jsonify({"token": auth.issue_token(user_id)})


@app.route("/v1/auth/login", methods=["POST"])
@limiter.limit("20 per hour")
def login():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    with db.db() as conn:
        row = conn.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,)).fetchone()
    if not row or not auth.verify_password(password, row["password_hash"]):
        return error("unauthorized", "Invalid email or password", 401)
    return jsonify({"token": auth.issue_token(row["id"])})


# --------------------------------------------------------------- section 5


@app.route("/v1/push/vapid-public-key")
def push_vapid_public_key():
    key = os.environ.get("GATEWAY_VAPID_PUBLIC_KEY")
    if not key:
        return error("not-configured", "Push notifications are not configured on this server", 503)
    return jsonify({"public_key": key})


@app.route("/v1/push/subscribe", methods=["POST"])
def push_subscribe():
    user_id, err = require_auth()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    endpoint = body.get("endpoint")
    keys = body.get("keys") or {}
    p256dh, auth_key = keys.get("p256dh"), keys.get("auth")
    if not endpoint or not p256dh or not auth_key:
        return error("invalid-address", "endpoint and keys.p256dh/keys.auth are required", 400)
    with db.db() as conn:
        conn.execute(
            "INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth, created_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(endpoint) DO UPDATE SET user_id=excluded.user_id, p256dh=excluded.p256dh, auth=excluded.auth",
            (user_id, endpoint, p256dh, auth_key, db.now()),
        )
        conn.commit()
    return jsonify({"subscribed": True})


@app.route("/v1/push/mobile/register", methods=["POST"])
@limiter.limit("30 per minute")
def push_mobile_register():
    """No auth required -- same convention as the balance/utxo/history
    endpoints above (address-keyed, not account-keyed), since the
    mobile app doesn't require a staking-service login just to watch
    its own address for incoming payments. See mobile_notify.py for
    what actually triggers a notification."""
    body = request.get_json(silent=True) or {}
    address = body.get("address")
    platform = body.get("platform")
    token = body.get("token")
    if not address or platform not in ("android", "ios") or not token:
        return error("invalid-request", "address, platform ('android'|'ios'), and token are required", 400)
    if not is_valid_address(address):
        return error("invalid-address", "Not a valid FirstIslamicCoin address", 400)
    with db.db() as conn:
        conn.execute(
            "INSERT INTO mobile_push_registrations (address, platform, token, last_notified_balance, created_at) "
            "VALUES (?, ?, ?, 0, ?) "
            "ON CONFLICT(address, token) DO UPDATE SET platform=excluded.platform",
            (address, platform, token, db.now()),
        )
        conn.commit()
    return jsonify({"registered": True})


@app.route("/v1/staking/status")
def staking_status():
    user_id, err = require_auth()
    if err:
        return err
    return jsonify(staking.status_for_user(user_id))


@app.route("/v1/staking/deposit", methods=["POST"])
@limiter.limit("20 per hour")
def staking_deposit():
    user_id, err = require_auth()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    amount = body.get("amount")
    if not amount:
        return error("invalid-address", "amount is required", 400)
    ensure_wallet_loaded()
    deposit_address = staking.create_deposit(user_id)
    return jsonify({"deposit_address": deposit_address, "amount": str(amount)})


@app.route("/v1/staking/withdraw", methods=["POST"])
@limiter.limit("20 per hour")
def staking_withdraw():
    user_id, err = require_auth()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    amount = body.get("amount")
    to_address = body.get("to_address")
    if not amount or not to_address:
        return error("invalid-address", "amount and to_address are required", 400)
    if not is_valid_address(to_address):
        return error("invalid-address", "to_address is not a valid FirstIslamicCoin address", 400)
    try:
        txid = staking.withdraw(user_id, int(amount), to_address)
    except staking.StakingError as e:
        return error(e.code, str(e), 400)
    return jsonify({"txid": txid})


@app.route("/v1/referral/status")
def referral_status():
    user_id, err = require_auth()
    if err:
        return err
    return jsonify(referral.status_for_user(user_id))


@app.route("/v1/referral/history")
def referral_history():
    user_id, err = require_auth()
    if err:
        return err
    return jsonify({"referrals": referral.history_for_user(user_id)})


@app.route("/v1/referral/withdraw", methods=["POST"])
@limiter.limit("20 per hour")
def referral_withdraw():
    user_id, err = require_auth()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    to_address = body.get("to_address")
    if not to_address:
        return error("invalid-address", "to_address is required", 400)
    if not is_valid_address(to_address):
        return error("invalid-address", "to_address is not a valid FirstIslamicCoin address", 400)
    try:
        txid = referral.withdraw(user_id, to_address)
    except referral.ReferralError as e:
        return error(e.code, str(e), 400)
    return jsonify({"txid": txid})


def _validate_alert_body(body):
    """Returns (direction, threshold_usd, None) or (None, None, error_response)."""
    direction = body.get("direction")
    if direction not in ("above", "below"):
        return None, None, error("invalid-request", "direction must be 'above' or 'below'", 400)
    try:
        threshold_usd = float(body.get("threshold_usd"))
    except (TypeError, ValueError):
        return None, None, error("invalid-request", "threshold_usd must be a number", 400)
    if threshold_usd <= 0:
        return None, None, error("invalid-request", "threshold_usd must be positive", 400)
    return direction, threshold_usd, None


@app.route("/v1/price")
def current_price():
    """No auth required, same convention as balance/history. Unlike CAC's
    version of this endpoint, there is no price source at all right now
    (no DEX listing exists for FIC -- see price_alerts.py's module
    docstring), so this always answers 503 rather than a fabricated
    number. Both wallets already handle that response honestly (see
    firstislamiccoin-mobile/lib/widgets/fiat_placeholder.dart)."""
    price = price_alerts.fetch_fic_usd_price()
    if price is None:
        return error("not-available", "No price source is currently reachable", 503)
    return jsonify({"usd_per_fic": price})


@app.route("/v1/price-alerts/web", methods=["POST"])
@limiter.limit("30 per hour")
def price_alerts_web_create():
    user_id, err = require_auth()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    direction, threshold_usd, err = _validate_alert_body(body)
    if err:
        return err
    alert_id = price_alerts.create_web_alert(user_id, direction, threshold_usd)
    return jsonify({"id": alert_id})


@app.route("/v1/price-alerts/web")
def price_alerts_web_list():
    user_id, err = require_auth()
    if err:
        return err
    return jsonify({"alerts": price_alerts.list_web_alerts(user_id)})


@app.route("/v1/price-alerts/web/<int:alert_id>", methods=["DELETE"])
def price_alerts_web_delete(alert_id):
    user_id, err = require_auth()
    if err:
        return err
    if not price_alerts.delete_web_alert(user_id, alert_id):
        return error("not-found", "No such alert", 404)
    return jsonify({"deleted": True})


@app.route("/v1/price-alerts/mobile", methods=["POST"])
@limiter.limit("30 per hour")
def price_alerts_mobile_create():
    """No auth required -- same address+token convention as
    /v1/push/mobile/register."""
    body = request.get_json(silent=True) or {}
    address = body.get("address")
    token = body.get("token")
    if not address or not token:
        return error("invalid-request", "address and token are required", 400)
    if not is_valid_address(address):
        return error("invalid-address", "Not a valid FirstIslamicCoin address", 400)
    direction, threshold_usd, err = _validate_alert_body(body)
    if err:
        return err
    alert_id = price_alerts.create_mobile_alert(address, token, direction, threshold_usd)
    return jsonify({"id": alert_id})


@app.route("/v1/price-alerts/mobile")
def price_alerts_mobile_list():
    address = request.args.get("address")
    token = request.args.get("token")
    if not address or not token:
        return error("invalid-request", "address and token query params are required", 400)
    return jsonify({"alerts": price_alerts.list_mobile_alerts(address, token)})


@app.route("/v1/price-alerts/mobile/<int:alert_id>", methods=["DELETE"])
def price_alerts_mobile_delete(alert_id):
    address = request.args.get("address")
    token = request.args.get("token")
    if not address or not token:
        return error("invalid-request", "address and token query params are required", 400)
    if not price_alerts.delete_mobile_alert(address, token, alert_id):
        return error("not-found", "No such alert", 404)
    return jsonify({"deleted": True})


@app.errorhandler(429)
def ratelimit_handler(e):
    return error("rate-limited", "Too many requests -- please slow down.", 429)


if __name__ == "__main__":
    db.init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
else:
    db.init_db()

"""Price-threshold alerts: notify a user (Web Push) or device (mobile
FCM) once the FIC/USD price crosses a level they set.

CAC's version of this module sourced a real (if thin) price from a
PancakeSwap pool on BNB Chain and a Stellar DEX order book -- both only
possible because CodexaCoin issues wrapped tokens on those chains. FIC
has neither (see ../docs/CHANGELOG-FIC.md's Decision 3 and
../docs/repo-map.md's "Components with no FIC target") -- there is no
DEX pool or order book to read a price from at all, so
fetch_fic_usd_price() below always returns None rather than porting a
price feed that has nothing to point at. This means /v1/price always
answers "not-available" (see app.py) and this module's own watcher pass
never triggers an alert -- both honest, not bugs. Whoever eventually
sources a real FIC/USD number (an exchange listing, if one ever exists)
replaces just this one function; the CRUD and one-shot-trigger machinery
below needs no change to start using it.

One-shot by design: an alert fires once when its condition is first met
(triggered_at gets set) and is never re-evaluated after that, rather than
re-notifying on every watcher pass while the price stays past the
threshold. A user who wants another alert at the same level sets a new
one.
"""
import db
import push
import push_mobile


def fetch_fic_usd_price():
    """Returns a float USD/FIC price, or None if no source is available.

    Always None today -- see this module's docstring. Kept as its own
    function (not inlined into current_price() in app.py) so a future
    real source is a one-function change, not a re-plumb.
    """
    return None


# --------------------------------------------------------------- CRUD

def create_web_alert(user_id, direction, threshold_usd):
    with db.db() as conn:
        cur = conn.execute(
            "INSERT INTO price_alerts (channel, user_id, direction, threshold_usd, created_at) "
            "VALUES ('web', ?, ?, ?, ?)",
            (user_id, direction, threshold_usd, db.now()),
        )
        conn.commit()
        return cur.lastrowid


def list_web_alerts(user_id):
    with db.db() as conn:
        rows = conn.execute(
            "SELECT id, direction, threshold_usd, created_at, triggered_at FROM price_alerts "
            "WHERE channel = 'web' AND user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_web_alert(user_id, alert_id):
    with db.db() as conn:
        cur = conn.execute(
            "DELETE FROM price_alerts WHERE id = ? AND channel = 'web' AND user_id = ?", (alert_id, user_id)
        )
        conn.commit()
        return cur.rowcount > 0


def create_mobile_alert(address, token, direction, threshold_usd):
    with db.db() as conn:
        cur = conn.execute(
            "INSERT INTO price_alerts (channel, address, token, direction, threshold_usd, created_at) "
            "VALUES ('mobile', ?, ?, ?, ?, ?)",
            (address, token, direction, threshold_usd, db.now()),
        )
        conn.commit()
        return cur.lastrowid


def list_mobile_alerts(address, token):
    with db.db() as conn:
        rows = conn.execute(
            "SELECT id, direction, threshold_usd, created_at, triggered_at FROM price_alerts "
            "WHERE channel = 'mobile' AND address = ? AND token = ? ORDER BY created_at DESC",
            (address, token),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_mobile_alert(address, token, alert_id):
    with db.db() as conn:
        cur = conn.execute(
            "DELETE FROM price_alerts WHERE id = ? AND channel = 'mobile' AND address = ? AND token = ?",
            (alert_id, address, token),
        )
        conn.commit()
        return cur.rowcount > 0


# ------------------------------------------------------------- watcher

def _notify_web_user(user_id, title, body):
    """Best-effort, same reasoning as staking.py's _notify_user: sends to
    every subscription this user has registered, never raises."""
    with db.db() as conn:
        subs = conn.execute(
            "SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE user_id = ?", (user_id,)
        ).fetchall()
    for s in subs:
        push.send_notification(
            {"endpoint": s["endpoint"], "keys": {"p256dh": s["p256dh"], "auth": s["auth"]}}, title, body
        )


def run_watcher_pass():
    """Checks every untriggered alert against the current price once and
    fires (then marks triggered) any whose condition is now met. Always a
    no-op today since fetch_fic_usd_price() has no source (see module
    docstring) -- kept running anyway so alerts start firing immediately,
    with no code change needed, the day a real price source exists."""
    price = fetch_fic_usd_price()
    if price is None:
        return
    with db.db() as conn:
        alerts = conn.execute("SELECT * FROM price_alerts WHERE triggered_at IS NULL").fetchall()
    for a in alerts:
        met = (price >= a["threshold_usd"]) if a["direction"] == "above" else (price <= a["threshold_usd"])
        if not met:
            continue
        title = "FIC price alert"
        body = (
            f"FIC is now ~${price:.6f}, "
            f"{'above' if a['direction'] == 'above' else 'below'} your ${a['threshold_usd']:.6f} alert."
        )
        try:
            if a["channel"] == "web":
                _notify_web_user(a["user_id"], title, body)
            else:
                push_mobile.send_fcm_notification(a["token"], title, body, data={"kind": "price_alert"})
        except Exception as e:
            print(f"[price_alerts] failed to notify alert {a['id']}: {e}")
        with db.db() as conn:
            conn.execute("UPDATE price_alerts SET triggered_at = ? WHERE id = ?", (db.now(), a["id"]))
            conn.commit()

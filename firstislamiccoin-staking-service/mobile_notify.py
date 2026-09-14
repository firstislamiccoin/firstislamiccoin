"""Detects a registered address's on-chain balance increasing and
sends a native push notification via push_mobile.py -- the mobile
equivalent of staking.py's deposit/reward notifications, but for *any*
address a mobile wallet has registered (see /v1/push/mobile/register
in app.py), not just staking-pool deposits.

Deliberately simple: compares total confirmed+unconfirmed balance
against the last value this module itself notified for, rather than
tracking individual UTXOs/txids. This can't distinguish "one new 0.5
FIC payment" from "0.5 FIC arrived, then 0.3 FIC left, then 0.8 FIC
arrived" within a single watcher interval (it just reports the net
+0.8 FIC), and a balance that decreases then returns to exactly its
prior value within one interval wouldn't re-trigger a notification.
Both are accepted limitations for this phase -- the common case (a
payment arrives) is handled correctly, and doing this precisely would
need per-UTXO tracking closer to staking.py's deposit-matching logic
than a simple balance diff.

Only ever invoked from watcher.py's standalone script process, never
from a live Flask request -- importing app.py here (to reuse its
already-verified ensure_address_watched/is_valid_address rather than
duplicating that RPC/wallet logic) is safe specifically because app.py
never imports this module back.
"""
import db
import push_mobile
import rpc
from app import COIN, WATCH_WALLET, ensure_address_watched, is_valid_address


def check_incoming_payments():
    with db.db() as conn:
        registrations = conn.execute(
            "SELECT id, address, token, last_notified_balance FROM mobile_push_registrations"
        ).fetchall()

    # Group by address so an address with several registered devices
    # only costs one listunspent call, not one per device.
    by_address = {}
    for r in registrations:
        by_address.setdefault(r["address"], []).append(r)

    for address, regs in by_address.items():
        if not is_valid_address(address):
            continue
        try:
            ensure_address_watched(address)
            utxos = rpc.call("listunspent", [0, 9999999, [address], True], wallet=WATCH_WALLET)
        except Exception as e:
            print(f"[mobile_notify] could not check {address}: {e}")
            continue
        current_balance = sum(round(u["amount"] * COIN) for u in utxos)

        for r in regs:
            if current_balance > r["last_notified_balance"]:
                delta = current_balance - r["last_notified_balance"]
                push_mobile.send_fcm_notification(
                    r["token"],
                    "Payment received",
                    f"You received {delta / COIN:.8f} FIC.",
                    data={"address": address},
                )
            if current_balance != r["last_notified_balance"]:
                with db.db() as conn:
                    conn.execute(
                        "UPDATE mobile_push_registrations SET last_notified_balance = ? WHERE id = ?",
                        (current_balance, r["id"]),
                    )
                    conn.commit()

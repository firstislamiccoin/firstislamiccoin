"""Web Push notifications (RFC 8291/8292 -- VAPID + encrypted payload),
via pywebpush. Sent when the staking pool watcher (staking.py) detects a
deposit being funded or a staking reward being credited.

Configuration:
    GATEWAY_VAPID_PRIVATE_KEY_PATH  path to a PEM EC private key (P-256)
    GATEWAY_VAPID_SUBJECT           mailto: or https: URL identifying the
                                     sending application, per RFC 8292

If unset, send_notification() is a no-op (logged, not raised) -- push
notifications are an enhancement, not something that should ever break
the watcher pass or any request that triggers one."""
import json
import os

from pywebpush import WebPushException, webpush

VAPID_PRIVATE_KEY_PATH = os.environ.get("GATEWAY_VAPID_PRIVATE_KEY_PATH")
VAPID_SUBJECT = os.environ.get("GATEWAY_VAPID_SUBJECT", "mailto:admin@firstislamiccoin.example")


def configured():
    return bool(VAPID_PRIVATE_KEY_PATH) and os.path.exists(VAPID_PRIVATE_KEY_PATH)


def send_notification(subscription, title, body, url=None):
    """subscription: {"endpoint": ..., "keys": {"p256dh": ..., "auth": ...}}
    (the shape the browser's PushSubscription.toJSON() produces, and what
    push_subscriptions stores per user). Failures are logged, not raised
    -- a dead/expired subscription shouldn't fail the watcher pass that's
    also crediting real money."""
    if not configured():
        print(f"[push] not configured, skipping notification: {title}")
        return False
    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=VAPID_PRIVATE_KEY_PATH,
            vapid_claims={"sub": VAPID_SUBJECT},
        )
        return True
    except WebPushException as e:
        print(f"[push] failed to send to {subscription.get('endpoint', '?')[:60]}...: {e}")
        return False

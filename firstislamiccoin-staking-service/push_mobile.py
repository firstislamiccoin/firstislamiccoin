"""Native mobile push notifications (Android/iOS) via Firebase Cloud
Messaging's HTTP v1 API, using a service account for OAuth2 -- a
different mechanism from push.py's Web Push/VAPID (browser-only, no
equivalent in the Flutter app). Sent when the incoming-payment watcher
(mobile_notify.py) detects a registered address's balance increase.

Configuration:
    GATEWAY_FCM_SERVICE_ACCOUNT_PATH  path to a Firebase service account
                                       JSON key (Firebase Console ->
                                       Project Settings -> Service
                                       Accounts -> Generate new private
                                       key). The project ID FCM sends
                                       to is read from this same file,
                                       not a separate env var.

If unset, send_fcm_notification() is a no-op (logged, not raised) --
same convention as push.py, for the same reason: a push failure should
never break a watcher pass or a request that triggers one.
"""
import json
import os

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

SERVICE_ACCOUNT_PATH = os.environ.get("GATEWAY_FCM_SERVICE_ACCOUNT_PATH")
_SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]

_cached_credentials = None
_cached_project_id = None


def configured():
    return bool(SERVICE_ACCOUNT_PATH) and os.path.exists(SERVICE_ACCOUNT_PATH)


def _credentials():
    global _cached_credentials, _cached_project_id
    if _cached_credentials is None:
        _cached_credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_PATH, scopes=_SCOPES
        )
        with open(SERVICE_ACCOUNT_PATH) as f:
            _cached_project_id = json.load(f)["project_id"]
    return _cached_credentials, _cached_project_id


def send_fcm_notification(token, title, body, data=None):
    """token: an FCM registration token, as returned by the Flutter
    app's firebase_messaging.getToken() and stored in
    mobile_push_registrations. Failures are logged, not raised -- same
    reasoning as push.py's send_notification."""
    if not configured():
        print(f"[push_mobile] not configured, skipping notification: {title}")
        return False
    try:
        credentials, project_id = _credentials()
        credentials.refresh(Request())
        message = {"message": {"token": token, "notification": {"title": title, "body": body}}}
        if data:
            message["message"]["data"] = {k: str(v) for k, v in data.items()}
        resp = requests.post(
            f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send",
            headers={
                "Authorization": f"Bearer {credentials.token}",
                "Content-Type": "application/json",
            },
            json=message,
            timeout=10,
        )
        if resp.status_code >= 300:
            print(f"[push_mobile] FCM send failed ({resp.status_code}): {resp.text[:200]}")
            return False
        return True
    except Exception as e:
        print(f"[push_mobile] failed to send to {token[:20]}...: {e}")
        return False

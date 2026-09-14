"""Bearer-token auth for the staking endpoints (mobile-api.md section 5
leaves the exact mechanism TBD for 6A; this is that decision: JWT issued
at signup/login, tied to the pool's own user accounts). Password hashing
via werkzeug (already a Flask dependency, no extra package needed)."""
import datetime
import os

import jwt
from werkzeug.security import check_password_hash, generate_password_hash

JWT_SECRET = os.environ.get("GATEWAY_JWT_SECRET", "dev-only-change-me")
JWT_ALGORITHM = "HS256"
JWT_TTL_HOURS = 24 * 30


def hash_password(password):
    return generate_password_hash(password)


def verify_password(password, password_hash):
    return check_password_hash(password_hash, password)


def issue_token(user_id):
    payload = {
        "sub": user_id,
        "iat": datetime.datetime.now(datetime.timezone.utc),
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=JWT_TTL_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token):
    """Returns the user_id, or None if the token is missing/invalid/expired."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload["sub"]
    except jwt.PyJWTError:
        return None

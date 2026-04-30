import base64
import hashlib
import hmac
import json
import os
import secrets
import time


SESSION_COOKIE = "ttm_session"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 7


def _secret_key():
    return os.environ.get("SECRET_KEY", "dev-secret-change-me")


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"{salt}${digest.hex()}"


def verify_password(password, stored_hash):
    try:
        salt, digest = stored_hash.split("$", 1)
    except ValueError:
        return False
    candidate = hash_password(password, salt).split("$", 1)[1]
    return hmac.compare_digest(candidate, digest)


def create_session_token(user_id):
    payload = {"user_id": user_id, "exp": int(time.time()) + SESSION_TTL_SECONDS}
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    body = base64.urlsafe_b64encode(payload_bytes).decode().rstrip("=")
    signature = hmac.new(_secret_key().encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def read_session_token(token):
    if not token or "." not in token:
        return None
    body, signature = token.rsplit(".", 1)
    expected = hmac.new(_secret_key().encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except (ValueError, json.JSONDecodeError):
        return None
    if payload.get("exp", 0) < int(time.time()):
        return None
    return payload

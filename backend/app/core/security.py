"""Password hashing and signed session tokens.

Both are implemented with the Python standard library only, so the auth layer
adds no new runtime dependency. Passwords use PBKDF2-HMAC-SHA256 with a random
per-password salt; session tokens are compact HMAC-SHA256 signed payloads (this
is deliberately not a JWT and carries no claims beyond the user id and expiry).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 240_000
_SALT_BYTES = 16
_TOKEN_VERSION = 1


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password must not be empty.")
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"{_ALGORITHM}${_ITERATIONS}${_b64encode(salt)}${_b64encode(derived)}"


def verify_password(password: str, hashed: str | None) -> bool:
    if not password or not hashed:
        return False
    try:
        algorithm, iterations_raw, salt_raw, expected_raw = hashed.split("$")
        if algorithm != _ALGORITHM:
            return False
        iterations = int(iterations_raw)
        salt = _b64decode(salt_raw)
        expected = _b64decode(expected_raw)
    except (ValueError, TypeError):
        return False
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(derived, expected)


def _sign(payload_segment: str, secret: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"), payload_segment.encode("ascii"), hashlib.sha256
    ).digest()
    return _b64encode(digest)


def create_access_token(user_id: int, *, secret: str, ttl_seconds: int) -> str:
    now = int(time.time())
    payload = {"v": _TOKEN_VERSION, "sub": user_id, "iat": now, "exp": now + ttl_seconds}
    segment = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{segment}.{_sign(segment, secret)}"


def decode_access_token(token: str, *, secret: str) -> int | None:
    """Return the user id for a valid, unexpired token, otherwise ``None``."""

    if not token or "." not in token:
        return None
    segment, signature = token.split(".", 1)
    if not hmac.compare_digest(_sign(segment, secret), signature):
        return None
    try:
        payload = json.loads(_b64decode(segment))
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or payload.get("v") != _TOKEN_VERSION:
        return None
    subject = payload.get("sub")
    expires_at = payload.get("exp")
    if not isinstance(subject, int) or not isinstance(expires_at, int):
        return None
    if expires_at < int(time.time()):
        return None
    return subject


__all__ = [
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "verify_password",
]

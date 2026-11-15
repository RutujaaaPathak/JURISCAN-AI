"""Regression tests for server-side session revocation (Phase 6B.3 / SEC-03).

Covers token versioning on logout, replay of revoked tokens, multiple sessions,
password-change revocation, and consistent handling of malformed/expired/
outdated tokens.
"""

from __future__ import annotations

import json
import time

from fastapi.testclient import TestClient

from app.config import settings
from app.core.database import SessionLocal
from app.core.security import (
    _b64encode,
    _sign,
    create_access_token,
    decode_access_token_claims,
)
from app.models import User

REGISTER = "/api/auth/register"
LOGIN = "/api/auth/login"
LOGOUT = "/api/auth/logout"
CHANGE_PASSWORD = "/api/auth/change-password"
ME = "/api/auth/me"

EMAIL = "session@example.com"
PASSWORD = "supersecret1"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, email: str = EMAIL, password: str = PASSWORD) -> str:
    response = client.post(
        REGISTER,
        json={
            "role": "individual",
            "email": email,
            "password": password,
            "full_name": "Session User",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def _login(client: TestClient, email: str = EMAIL, password: str = PASSWORD) -> str:
    response = client.post(LOGIN, json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _legacy_token_without_version(user_id: int) -> str:
    """Mimic a token issued before Phase 6B.3 (no ``ver`` claim)."""

    now = int(time.time())
    payload = {"v": 1, "sub": user_id, "iat": now, "exp": now + 3600}
    segment = _b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    return f"{segment}.{_sign(segment, settings.secret_key)}"


def test_issued_tokens_include_the_current_token_version(client: TestClient):
    token = _register(client)
    claims = decode_access_token_claims(token, secret=settings.secret_key)
    assert claims is not None
    assert claims.token_version == 1

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == EMAIL).one()
        assert user.token_version == 1


def test_logout_revokes_all_sessions_and_old_tokens_cannot_be_replayed(
    client: TestClient,
):
    first = _register(client)
    second = _login(client)

    assert client.get(ME, headers=_auth(first)).status_code == 200
    assert client.get(ME, headers=_auth(second)).status_code == 200

    logout = client.post(LOGOUT, headers=_auth(first))
    assert logout.status_code == 204

    # Both sessions are invalid immediately, not just the one that logged out.
    for token in (first, second):
        replay = client.get(ME, headers=_auth(token))
        assert replay.status_code == 401
        assert replay.json()["error"]["code"] == "invalid_token"

    # A revoked token cannot be used to call logout again either.
    assert client.post(LOGOUT, headers=_auth(first)).status_code == 401

    # A fresh login works and carries the incremented version.
    third = _login(client)
    assert client.get(ME, headers=_auth(third)).status_code == 200
    claims = decode_access_token_claims(third, secret=settings.secret_key)
    assert claims is not None
    assert claims.token_version == 2


def test_password_change_revokes_previous_sessions_and_requires_the_new_password(
    client: TestClient,
):
    first = _register(client)
    second = _login(client)

    wrong = client.post(
        CHANGE_PASSWORD,
        headers=_auth(first),
        json={"current_password": "not-the-password", "new_password": "brand-new-pass"},
    )
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "invalid_current_password"
    assert client.get(ME, headers=_auth(first)).status_code == 200

    changed = client.post(
        CHANGE_PASSWORD,
        headers=_auth(first),
        json={"current_password": PASSWORD, "new_password": "brand-new-pass"},
    )
    assert changed.status_code == 204

    for token in (first, second):
        replay = client.get(ME, headers=_auth(token))
        assert replay.status_code == 401
        assert replay.json()["error"]["code"] == "invalid_token"

    assert (
        client.post(LOGIN, json={"email": EMAIL, "password": PASSWORD}).status_code
        == 401
    )
    new_token = _login(client, password="brand-new-pass")
    assert client.get(ME, headers=_auth(new_token)).status_code == 200
    claims = decode_access_token_claims(new_token, secret=settings.secret_key)
    assert claims is not None
    assert claims.token_version == 2


def test_malformed_expired_outdated_and_revoked_tokens_are_rejected_consistently(
    client: TestClient,
):
    token = _register(client)
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == EMAIL).one()
        user_id = user.id

    expired = create_access_token(
        user_id, secret=settings.secret_key, ttl_seconds=-1
    )
    outdated = create_access_token(
        user_id,
        secret=settings.secret_key,
        ttl_seconds=3600,
        token_version=99,
    )
    zero_version = create_access_token(
        user_id,
        secret=settings.secret_key,
        ttl_seconds=3600,
        token_version=0,
    )
    legacy = _legacy_token_without_version(user_id)

    for bad_token in (
        "not-a-real-token",
        legacy,
        expired,
        outdated,
        zero_version,
    ):
        response = client.get(ME, headers=_auth(bad_token))
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_token"

    assert client.post(LOGOUT, headers=_auth(token)).status_code == 204
    revoked = client.get(ME, headers=_auth(token))
    assert revoked.status_code == 401
    assert revoked.json()["error"]["code"] == "invalid_token"

    # Logout itself requires a currently valid session.
    assert client.post(LOGOUT).status_code == 401

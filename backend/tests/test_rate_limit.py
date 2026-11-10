"""Regression tests for brute-force protection and auth hardening.

Covers:

* the stdlib sliding-window rate limiter (unit level, with a fake clock),
* the ``429`` behavior of ``/auth/login`` and ``/auth/register`` including the
  ``Retry-After`` header and stable error code,
* login timing equalization (unknown emails still burn a PBKDF2 cycle),
* the registration IntegrityError race (concurrent duplicate sign-up),
* disabling the interactive API docs outside development.

The suite-wide ``AUTH_RATE_LIMIT_MAX_REQUESTS=0`` (see conftest) keeps the
shared session client unthrottled; these tests re-enable the limiter through
``monkeypatch`` so every case starts from a clean, known configuration.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.ratelimit import SlidingWindowRateLimiter

REGISTER = "/api/auth/register"
LOGIN = "/api/auth/login"


def _limits_factory(limit: int, window: float):
    def factory() -> tuple[int, float]:
        return limit, window

    return factory


def _login_payload(email: str = "alex@example.com") -> dict:
    return {"email": email, "password": "supersecret1"}


@pytest.fixture(autouse=True)
def _reset_auth_limiter():
    """Start and end every test with clean rate-limit counters."""

    from app.api import auth as auth_module

    auth_module._auth_rate_limiter.reset()
    yield
    auth_module._auth_rate_limiter.reset()


# ---------------------------------------------------------------------------
# SlidingWindowRateLimiter (unit level)


def test_limiter_allows_up_to_max_requests_within_window():
    limiter = SlidingWindowRateLimiter(_limits_factory(3, 60))
    assert limiter.check("a", now=0.0).allowed is True
    assert limiter.check("a", now=1.0).allowed is True
    assert limiter.check("a", now=2.0).allowed is True
    decision = limiter.check("a", now=3.0)
    assert decision.allowed is False


def test_limiter_window_slides_and_recovers():
    limiter = SlidingWindowRateLimiter(_limits_factory(2, 10))
    assert limiter.check("a", now=0.0).allowed is True
    assert limiter.check("a", now=1.0).allowed is True
    assert limiter.check("a", now=2.0).allowed is False
    # The oldest hit expires at t=10, freeing a slot.
    assert limiter.check("a", now=10.0).allowed is True


def test_limiter_retry_after_reports_wait_until_free_slot():
    limiter = SlidingWindowRateLimiter(_limits_factory(1, 60))
    assert limiter.check("a", now=100.0).allowed is True
    decision = limiter.check("a", now=110.0)
    assert decision.allowed is False
    assert decision.retry_after_seconds == 50


def test_limiter_keys_are_independent():
    limiter = SlidingWindowRateLimiter(_limits_factory(1, 60))
    assert limiter.check("1.1.1.1", now=0.0).allowed is True
    assert limiter.check("2.2.2.2", now=0.0).allowed is True
    assert limiter.check("1.1.1.1", now=0.0).allowed is False
    assert limiter.check("2.2.2.2", now=0.0).allowed is False


def test_limiter_disabled_when_max_requests_is_zero():
    limiter = SlidingWindowRateLimiter(_limits_factory(0, 60))
    for _ in range(50):
        assert limiter.check("a", now=0.0).allowed is True


def test_limiter_reads_new_limits_without_restart():
    holder = {"limit": 1}

    def factory() -> tuple[int, float]:
        return holder["limit"], 60

    limiter = SlidingWindowRateLimiter(factory)
    assert limiter.check("a", now=0.0).allowed is True
    assert limiter.check("a", now=0.0).allowed is False
    holder["limit"] = 2
    assert limiter.check("a", now=0.0).allowed is True


def test_limiter_reset_clears_counters():
    limiter = SlidingWindowRateLimiter(_limits_factory(1, 60))
    assert limiter.check("a", now=0.0).allowed is True
    assert limiter.check("a", now=0.0).allowed is False
    limiter.reset()
    assert limiter.check("a", now=0.0).allowed is True


def test_limiter_prunes_expired_keys_under_pressure():
    limiter = SlidingWindowRateLimiter(_limits_factory(1, 60))
    for index in range(70_000):
        limiter.check(f"host-{index}", now=float(index))
    # The internal map must stay bounded despite the flood of unique keys.
    assert len(limiter._events) <= 65_536


# ---------------------------------------------------------------------------
# HTTP behavior of /auth/login and /auth/register


def test_login_is_rate_limited_after_max_attempts(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "auth_rate_limit_max_requests", 3)
    monkeypatch.setattr(settings, "auth_rate_limit_window_seconds", 60)

    for _ in range(3):
        response = client.post(LOGIN, json=_login_payload())
        assert response.status_code == 401  # wrong credentials, not throttled

    throttled = client.post(LOGIN, json=_login_payload())
    assert throttled.status_code == 429
    body = throttled.json()
    assert body["error"]["code"] == "rate_limited"
    retry_after = throttled.headers["Retry-After"]
    assert retry_after.isdigit() and int(retry_after) >= 1


def test_register_is_rate_limited_after_max_attempts(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "auth_rate_limit_max_requests", 2)
    monkeypatch.setattr(settings, "auth_rate_limit_window_seconds", 60)

    payload = {
        "role": "individual",
        "email": "flood@example.com",
        "password": "supersecret1",
        "full_name": "Flood Test",
    }
    # Schema-validation failures (valid JSON, missing fields) consume the
    # budget: route-level dependencies run before endpoint parameters are
    # validated, so hammering the endpoint cannot bypass the limiter.
    assert client.post(REGISTER, json=payload).status_code == 201
    del payload["email"]
    assert client.post(REGISTER, json=payload).status_code == 422

    throttled = client.post(REGISTER, json={})
    assert throttled.status_code == 429
    assert throttled.json()["error"]["code"] == "rate_limited"


def test_rate_limit_does_not_leak_between_tests(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "auth_rate_limit_max_requests", 1)
    monkeypatch.setattr(settings, "auth_rate_limit_window_seconds", 60)
    assert client.post(LOGIN, json=_login_payload()).status_code == 401
    # The autouse reset fixture gives the next test a fresh budget.
    assert client.post(LOGIN, json=_login_payload()).status_code == 429


def test_malformed_json_rejects_before_rate_limiting(client: TestClient, monkeypatch):
    """Documents FastAPI 0.115 behavior: syntactically invalid JSON raises a
    parse error before route dependencies run, so it never consumes budget.

    This is acceptable: parse failures are cheap rejects that never reach the
    endpoint, so no PBKDF2 work or credential attempt is possible without a
    valid JSON body (and those are always counted — see the register test
    above). Edge-level throttling (nginx limit_req) covers raw floods.
    """

    monkeypatch.setattr(settings, "auth_rate_limit_max_requests", 1)
    monkeypatch.setattr(settings, "auth_rate_limit_window_seconds", 60)
    # One counted request exhausts the budget...
    assert client.post(LOGIN, json=_login_payload()).status_code == 401
    assert client.post(LOGIN, json=_login_payload()).status_code == 429
    # ...while garbage bodies are rejected (422) without being counted.
    garbage = client.post(
        LOGIN, content=b"not-json", headers={"Content-Type": "application/json"}
    )
    assert garbage.status_code == 422


def test_login_for_unknown_email_still_verifies_a_password(client: TestClient, monkeypatch):
    """An unknown email must cost a full PBKDF2 cycle (no timing enumeration)."""

    from app.api import auth as auth_module

    seen_hashes: list[str] = []

    def spy_verify(password: str, hashed: str) -> bool:
        seen_hashes.append(hashed)
        return False

    monkeypatch.setattr(auth_module, "verify_password", spy_verify)
    monkeypatch.setattr(settings, "auth_rate_limit_max_requests", 0)

    response = client.post(LOGIN, json=_login_payload("ghost@example.com"))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"
    assert seen_hashes == [auth_module._DUMMY_HASH]


def test_login_for_known_email_verifies_real_hash_not_dummy(client: TestClient, monkeypatch):
    from sqlalchemy import select

    from app.api import auth as auth_module
    from app.core.database import SessionLocal
    from app.models import User

    register_payload = {
        "role": "individual",
        "email": "alex@example.com",
        "password": "supersecret1",
        "full_name": "Alex Doe",
    }
    assert client.post(REGISTER, json=register_payload).status_code == 201

    with SessionLocal() as db:
        stored_hash = db.scalar(
            select(User.hashed_password).where(User.email == "alex@example.com")
        )
    assert stored_hash and stored_hash != auth_module._DUMMY_HASH

    seen_hashes: list[str] = []

    def spy_verify(password: str, hashed: str) -> bool:
        seen_hashes.append(hashed)
        return False

    monkeypatch.setattr(auth_module, "verify_password", spy_verify)
    monkeypatch.setattr(settings, "auth_rate_limit_max_requests", 0)

    response = client.post(LOGIN, json=_login_payload("alex@example.com"))
    assert response.status_code == 401
    # The real stored hash is verified exactly once; the dummy is never used
    # for an account that exists.
    assert seen_hashes == [stored_hash]


def test_dummy_hash_is_not_verifiable_by_any_password(client: TestClient):
    from app.api import auth as auth_module
    from app.core.security import verify_password

    for password in (
        "timing-equalization-dummy",
        "password",
        "",
        "supersecret1",
        "UCP8bIBnunOvBSFYVpl3uQ",
    ):
        assert verify_password(password, auth_module._DUMMY_HASH) is False


def test_register_concurrent_duplicate_returns_conflict_not_500(
    client: TestClient, monkeypatch
):
    """A lost duplicate-check race (IntegrityError on commit) is a 409."""

    monkeypatch.setattr(settings, "auth_rate_limit_max_requests", 0)

    def racing_commit(self: Session) -> None:
        raise IntegrityError("INSERT ...", {}, Exception("UNIQUE constraint failed"))

    monkeypatch.setattr(Session, "commit", racing_commit)

    payload = {
        "role": "individual",
        "email": "racer@example.com",
        "password": "supersecret1",
        "full_name": "Racer Test",
    }
    response = client.post(REGISTER, json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "registration_conflict"


def test_api_docs_disabled_outside_development(monkeypatch):
    """Production/staging must not expose /docs, /redoc, /openapi.json."""

    from main import create_app

    monkeypatch.setattr(settings, "app_env", "production")
    production_app = create_app()
    assert production_app.docs_url is None
    assert production_app.redoc_url is None
    assert production_app.openapi_url is None

    monkeypatch.setattr(settings, "app_env", "staging")
    staging_app = create_app()
    assert staging_app.docs_url is None
    assert staging_app.redoc_url is None
    assert staging_app.openapi_url is None


def test_api_docs_available_in_development(monkeypatch):
    from main import create_app

    monkeypatch.setattr(settings, "app_env", "development")
    dev_app = create_app()
    assert dev_app.docs_url == "/docs"
    assert dev_app.redoc_url == "/redoc"
    assert dev_app.openapi_url == "/openapi.json"

"""Tests for the authentication layer (registration, login, sessions).

These exercise the real bearer-token flow rather than the development role
preview, and assert that the backend treats the authenticated role as the single
source of truth.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

REGISTER = "/api/auth/register"
LOGIN = "/api/auth/login"
ME = "/api/auth/me"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, **overrides) -> dict:
    payload = {
        "role": "individual",
        "email": "alex@example.com",
        "password": "supersecret1",
        "full_name": "Alex Doe",
    }
    payload.update(overrides)
    return client.post(REGISTER, json=payload)


def test_register_individual_returns_session(client: TestClient):
    response = _register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["role"] == "individual"
    assert body["user"]["email"] == "alex@example.com"

    me = client.get(ME, headers=_auth(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "alex@example.com"


def test_register_company_requires_organization_name(client: TestClient):
    missing = _register(client, role="company")
    assert missing.status_code == 422

    ok = _register(
        client,
        role="company",
        email="ops@acme-legal.com",
        organization_name="Acme Legal",
        full_name="Acme Admin",
    )
    assert ok.status_code == 201
    body = ok.json()
    assert body["user"]["role"] == "company"
    assert body["user"]["organization_name"] == "Acme Legal"


def test_register_lawyer_requires_professional_details(client: TestClient):
    missing = _register(client, role="lawyer", email="law@example.com")
    assert missing.status_code == 422

    ok = _register(
        client,
        role="lawyer",
        email="law@example.com",
        full_name="Priya Counsel",
        bar_registration_number="BAR-12345",
        jurisdiction="Maharashtra",
        years_experience=9,
        practice_areas=["property", "family"],
        bio="Property and family practice.",
    )
    assert ok.status_code == 201
    token = ok.json()["access_token"]

    profile = client.get("/api/lawyer/profile", headers=_auth(token))
    assert profile.status_code == 200
    data = profile.json()
    assert data["bar_registration_number"] == "BAR-12345"
    assert data["practice_areas"] == ["property", "family"]
    assert data["verification_status"] == "UNVERIFIED"


def test_admin_role_cannot_be_self_registered(client: TestClient):
    response = _register(client, role="admin", email="admin@example.com")
    assert response.status_code == 422


def test_duplicate_email_is_rejected(client: TestClient):
    assert _register(client).status_code == 201
    duplicate = _register(client, full_name="Someone Else")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "email_taken"


def test_login_success_and_failure(client: TestClient):
    _register(client)

    ok = client.post(LOGIN, json={"email": "alex@example.com", "password": "supersecret1"})
    assert ok.status_code == 200
    assert ok.json()["user"]["username"]

    wrong = client.post(LOGIN, json={"email": "alex@example.com", "password": "nope-nope"})
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "invalid_credentials"

    unknown = client.post(LOGIN, json={"email": "ghost@example.com", "password": "supersecret1"})
    assert unknown.status_code == 401


def test_me_requires_a_token(client: TestClient):
    response = client.get(ME)
    assert response.status_code == 401


def test_invalid_token_is_rejected(client: TestClient):
    response = client.get(ME, headers=_auth("not-a-real-token"))
    assert response.status_code == 401


def test_authenticated_role_is_authoritative_over_preview_header(client: TestClient):
    token = _register(client).json()["access_token"]

    headers = _auth(token)
    headers["X-Developer-Role"] = "lawyer"

    forbidden = client.get("/api/lawyer/profile", headers=headers)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "insufficient_role"

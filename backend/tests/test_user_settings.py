"""Tests for the authenticated user settings endpoints.

These exercise the real bearer-token flow and assert per-account isolation: one
account must never be able to read or change another account's settings, and the
account email is not mutable through the settings form.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

REGISTER = "/api/auth/register"
LOGIN = "/api/auth/login"
SETTINGS = "/api/settings"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, **overrides) -> dict:
    payload = {
        "role": "individual",
        "email": "shrey@example.com",
        "password": "supersecret1",
        "full_name": "Shrey Ruparel",
    }
    payload.update(overrides)
    return client.post(REGISTER, json=payload).json()


def _token(client: TestClient, email: str) -> str:
    response = client.post(LOGIN, json={"email": email, "password": "supersecret1"})
    return response.json()["access_token"]


def test_settings_require_authentication(client: TestClient):
    assert client.get(SETTINGS).status_code == 401
    assert client.put(SETTINGS, json={"full_name": "Nobody"}).status_code == 401


def test_new_account_gets_its_own_defaults(client: TestClient):
    user = _register(client)["user"]

    body = client.get(SETTINGS, headers=_auth(_token(client, user["email"])))
    assert body.status_code == 200
    data = body.json()

    # Profile fields reflect the authenticated account, never another user's.
    assert data["email"] == "shrey@example.com"
    assert data["full_name"] == "Shrey Ruparel"
    assert data["role"] == "individual"
    assert data["organization_name"] is None
    # Unconfigured jurisdiction is an explicit empty state, not "England & Wales".
    assert data["jurisdiction"] is None
    # Sensible engine defaults.
    assert data["min_severity"] == "medium"
    assert data["analysis_model"] == "rules"
    assert data["auto_analyze"] is True
    assert data["notify_email_digest"] is True
    assert data["notify_high_risk"] is True
    assert data["notify_weekly_report"] is False


def test_settings_persist_across_sessions(client: TestClient):
    _register(client)
    token = _token(client, "shrey@example.com")

    updated = client.put(
        SETTINGS,
        headers=_auth(token),
        json={
            "full_name": "Shrey R.",
            "jurisdiction": "Maharashtra",
            "min_severity": "high",
            "analysis_model": "heuristic",
            "auto_analyze": False,
            "notify_weekly_report": True,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Shrey R."
    assert updated.json()["min_severity"] == "high"

    # A brand-new login gets a fresh token; persisted values must still be there.
    fresh = _token(client, "shrey@example.com")
    reloaded = client.get(SETTINGS, headers=_auth(fresh)).json()
    assert reloaded["full_name"] == "Shrey R."
    assert reloaded["jurisdiction"] == "Maharashtra"
    assert reloaded["analysis_model"] == "heuristic"
    assert reloaded["auto_analyze"] is False
    assert reloaded["notify_weekly_report"] is True


def test_email_is_not_mutable_through_settings(client: TestClient):
    _register(client)
    token = _token(client, "shrey@example.com")

    response = client.put(
        SETTINGS,
        headers=_auth(token),
        json={"email": "attacker@evil.example", "full_name": "Still Shrey"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "shrey@example.com"

    assert client.get(SETTINGS, headers=_auth(token)).json()["email"] == "shrey@example.com"


def test_settings_are_isolated_between_accounts(client: TestClient):
    _register(client, email="first@example.com", full_name="First User")
    _register(client, email="second@example.com", full_name="Second User")

    first = _auth(_token(client, "first@example.com"))
    second = _auth(_token(client, "second@example.com"))

    client.put(
        SETTINGS,
        headers=first,
        json={"full_name": "First Renamed", "jurisdiction": "Karnataka", "min_severity": "critical"},
    )

    first_view = client.get(SETTINGS, headers=first).json()
    second_view = client.get(SETTINGS, headers=second).json()

    assert first_view["full_name"] == "First Renamed"
    assert first_view["jurisdiction"] == "Karnataka"
    assert first_view["min_severity"] == "critical"

    # The second account is completely unaffected.
    assert second_view["email"] == "second@example.com"
    assert second_view["full_name"] == "Second User"
    assert second_view["jurisdiction"] is None
    assert second_view["min_severity"] == "medium"


def test_organization_only_persists_for_company_accounts(client: TestClient):
    _register(client, email="solo@example.com")
    individual = _auth(_token(client, "solo@example.com"))
    client.put(SETTINGS, headers=individual, json={"organization_name": "Sneaky Ltd"})
    assert client.get(SETTINGS, headers=individual).json()["organization_name"] is None

    _register(
        client,
        role="company",
        email="ops@acme.com",
        full_name="Acme Admin",
        organization_name="Acme Legal",
    )
    company = _auth(_token(client, "ops@acme.com"))
    updated = client.put(
        SETTINGS, headers=company, json={"organization_name": "Acme Legal LLP"}
    )
    assert updated.json()["organization_name"] == "Acme Legal LLP"


def test_lawyer_jurisdiction_falls_back_to_profile(client: TestClient):
    _register(
        client,
        role="lawyer",
        email="counsel@example.com",
        full_name="Priya Counsel",
        bar_registration_number="BAR-1",
        jurisdiction="Delhi",
        years_experience=5,
        practice_areas=["property"],
        bio="Property practice.",
    )
    token = _auth(_token(client, "counsel@example.com"))
    data = client.get(SETTINGS, headers=token).json()
    assert data["role"] == "lawyer"
    assert data["jurisdiction"] == "Delhi"

"""Tests for the case browsing and lawyer decision workflow.

These tests exercise real server-side authorization by overriding the current
user dependency, because no authentication layer exists yet.
"""

import pytest

from app.api.deps import get_current_user
from app.core.database import SessionLocal
from app.models import User

CONTRACT = """1. Indemnity
The Supplier shall indemnify the Customer against all losses without any cap.

2. Termination
The Customer may terminate this Agreement for convenience at any time.
"""


def _make_user(role: str, name: str) -> User:
    db = SessionLocal()
    try:
        user = User(
            email=f"{name}@example.com",
            username=name,
            full_name=name.replace("-", " ").title(),
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()


@pytest.fixture
def login(client):
    def _login(user: User) -> User:
        client.app.dependency_overrides[get_current_user] = lambda: user
        return user

    yield _login
    client.app.dependency_overrides.clear()


def _create_case(client, **overrides):
    payload = {
        "title": "Boundary dispute with neighbour",
        "category": "property",
        "summary": "A fence was built across the shared driveway boundary.",
        "urgency": "MEDIUM",
    }
    payload.update(overrides)
    return client.post("/api/cases", json=payload)


def test_developer_role_header_is_dev_only(client):
    # No header -> demo user is an individual -> forbidden.
    assert client.get("/api/cases/mine").status_code == 403
    # Development-only header switches the preview role.
    assert (
        client.get("/api/cases/mine", headers={"X-Developer-Role": "lawyer"}).status_code
        == 200
    )


def test_lawyer_sees_available_cases_but_other_clients_do_not(client, login):
    client_user = _make_user("individual", "client-one")
    lawyer = _make_user("lawyer", "lawyer-one")
    other_client = _make_user("individual", "client-two")

    login(client_user)
    created = _create_case(client)
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]

    login(lawyer)
    available = client.get("/api/cases")
    assert available.status_code == 200
    assert [item["id"] for item in available.json()["items"]] == [case_id]
    assert available.json()["items"][0]["my_decision"] is None

    login(other_client)
    assert client.get("/api/cases").json()["items"] == []
    assert client.get(f"/api/cases/{case_id}").status_code == 404


def test_client_only_sees_own_posted_cases(client, login):
    client_user = _make_user("individual", "client-owner")
    login(client_user)
    _create_case(client, title="My own matter")
    response = client.get("/api/cases")
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_role_checks_block_non_lawyers(client, login):
    client_user = _make_user("individual", "client-role")
    login(client_user)
    case_id = _create_case(client).json()["id"]

    assert client.get("/api/cases/mine").status_code == 403
    assert client.get("/api/cases/overview").status_code == 403
    assert client.post(f"/api/cases/{case_id}/accept").status_code == 403
    assert client.post(f"/api/cases/{case_id}/reject", json={"reason": "no"}).status_code == 403


def test_accept_assigns_case_exclusively(client, login):
    client_user = _make_user("individual", "client-accept")
    lawyer_a = _make_user("lawyer", "lawyer-a")
    lawyer_b = _make_user("lawyer", "lawyer-b")

    login(client_user)
    case_id = _create_case(client).json()["id"]

    login(lawyer_a)
    first = client.post(f"/api/cases/{case_id}/accept")
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["status"] == "ASSIGNED"
    assert body["assigned_lawyer_id"] == lawyer_a.id
    assert body["my_decision"] == "ACCEPT"

    # Second lawyer must not be able to take an already-assigned case.
    login(lawyer_b)
    second = client.post(f"/api/cases/{case_id}/accept")
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "case_already_assigned"
    assert client.get("/api/cases").json()["items"] == []

    # The first lawyer still owns it.
    login(lawyer_a)
    assert client.get("/api/cases/mine").json()["active"][0]["id"] == case_id


def test_reject_requires_reason(client, login):
    client_user = _make_user("individual", "client-reject")
    lawyer = _make_user("lawyer", "lawyer-reject")
    login(client_user)
    case_id = _create_case(client).json()["id"]

    login(lawyer)
    assert client.post(f"/api/cases/{case_id}/reject", json={}).status_code == 422
    assert (
        client.post(f"/api/cases/{case_id}/reject", json={"reason": "Conflict of interest"}).status_code
        == 200
    )


def test_decline_hides_case_from_that_lawyer_only(client, login):
    client_user = _make_user("individual", "client-decline")
    lawyer_a = _make_user("lawyer", "lawyer-decline-a")
    lawyer_b = _make_user("lawyer", "lawyer-decline-b")
    login(client_user)
    case_id = _create_case(client).json()["id"]

    login(lawyer_a)
    declined = client.post(
        f"/api/cases/{case_id}/reject", json={"reason": "Outside my practice area"}
    )
    assert declined.status_code == 200
    assert declined.json()["my_decision"] == "REJECT"
    assert client.get("/api/cases").json()["items"] == []
    assert [item["id"] for item in client.get("/api/cases/mine").json()["declined"]] == [case_id]

    # Another lawyer still sees it as available.
    login(lawyer_b)
    assert [item["id"] for item in client.get("/api/cases").json()["items"]] == [case_id]


def test_request_info_moves_case_to_pending(client, login):
    client_user = _make_user("individual", "client-info")
    lawyer = _make_user("lawyer", "lawyer-info")
    login(client_user)
    case_id = _create_case(client).json()["id"]

    login(lawyer)
    assert client.post(f"/api/cases/{case_id}/request-info", json={}).status_code == 422
    first = client.post(
        f"/api/cases/{case_id}/request-info",
        json={"message": "Please share the property deed."},
    )
    assert first.status_code == 200
    assert first.json()["my_decision"] == "REQUEST_INFO"
    assert [item["id"] for item in client.get("/api/cases").json()["items"]] == []
    assert [item["id"] for item in client.get("/api/cases/mine").json()["pending"]] == [case_id]

    # Duplicate request is rejected by the unique decision constraint.
    duplicate = client.post(
        f"/api/cases/{case_id}/request-info", json={"message": "Again"}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "already_requested"


def test_assigned_lawyer_can_open_attached_document(client, login):
    client_user = _make_user("individual", "client-doc")
    lawyer = _make_user("lawyer", "lawyer-doc")
    stranger = _make_user("lawyer", "lawyer-stranger")

    login(client_user)
    upload = client.post(
        "/api/documents",
        files={"file": ("contract.txt", CONTRACT.encode("utf-8"), "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]

    case_id = _create_case(client, document_ids=[document_id]).json()["id"]
    assert client.get(f"/api/cases/{case_id}").json()["document_count"] == 1

    # Before accepting, a lawyer is not authorized for the private document.
    login(lawyer)
    assert client.get(f"/api/documents/{document_id}").status_code == 404
    assert client.post(f"/api/cases/{case_id}/accept").status_code == 200
    assert client.get(f"/api/documents/{document_id}").status_code == 200
    detail = client.get(f"/api/cases/{case_id}").json()
    assert detail["documents"][0]["document_id"] == document_id

    # An unrelated lawyer is still denied.
    login(stranger)
    assert client.get(f"/api/documents/{document_id}").status_code == 404


def test_cannot_attach_documents_you_do_not_own(client, login):
    owner = _make_user("individual", "doc-owner")
    intruder = _make_user("individual", "doc-intruder")

    login(owner)
    document_id = client.post(
        "/api/documents",
        files={"file": ("contract.txt", CONTRACT.encode("utf-8"), "text/plain")},
    ).json()["id"]

    login(intruder)
    response = _create_case(client, document_ids=[document_id])
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_documents"


def test_private_notes_only_for_assigned_lawyer(client, login):
    client_user = _make_user("individual", "client-notes")
    lawyer = _make_user("lawyer", "lawyer-notes")
    stranger = _make_user("lawyer", "lawyer-notes-stranger")
    login(client_user)
    case_id = _create_case(client).json()["id"]

    login(stranger)
    assert client.post(f"/api/cases/{case_id}/notes", json={"body": "nope"}).status_code == 403

    login(lawyer)
    client.post(f"/api/cases/{case_id}/accept")
    note = client.post(f"/api/cases/{case_id}/notes", json={"body": "Prep hearing bundle."})
    assert note.status_code == 201, note.text
    assert [item["body"] for item in note.json()["notes"]] == ["Prep hearing bundle."]

    # The client never sees private working notes.
    login(client_user)
    assert client.get(f"/api/cases/{case_id}").json()["notes"] == []


def test_complete_requires_assignment(client, login):
    client_user = _make_user("individual", "client-complete")
    lawyer = _make_user("lawyer", "lawyer-complete")
    other = _make_user("lawyer", "lawyer-complete-other")
    login(client_user)
    case_id = _create_case(client).json()["id"]

    login(other)
    assert client.post(f"/api/cases/{case_id}/complete").status_code == 403

    login(lawyer)
    client.post(f"/api/cases/{case_id}/accept")
    completed = client.post(f"/api/cases/{case_id}/complete")
    assert completed.status_code == 200
    assert completed.json()["status"] == "COMPLETED"
    assert client.get("/api/cases/mine").json()["completed"][0]["id"] == case_id


def test_lawyer_overview_reports_real_counts(client, login):
    client_user = _make_user("individual", "client-overview")
    lawyer = _make_user("lawyer", "lawyer-overview")
    login(client_user)
    open_case = _create_case(client, title="Open matter here").json()["id"]
    _create_case(client, title="Second open matter", category="family")
    accepted_case = _create_case(client, title="Accepted matter", category="employment").json()["id"]

    login(lawyer)
    client.post(f"/api/cases/{open_case}/reject", json={"reason": "Conflict"})
    client.post(f"/api/cases/{accepted_case}/accept")

    overview = client.get("/api/cases/overview").json()
    assert overview["available_cases"] == 1
    assert overview["active_cases"] == 1
    assert overview["completed_cases"] == 0
    assert overview["pending_requests"] == 0
    assert overview["unread_messages"] == 0
    assert overview["case_status_distribution"]["ASSIGNED"] == 1
    categories = {row["category"] for row in overview["case_category_distribution"]}
    assert {"family", "employment"} <= categories


def test_lawyer_profile_defaults_and_update(client, login):
    lawyer = _make_user("lawyer", "lawyer-profile")
    login(lawyer)

    profile = client.get("/api/lawyer/profile")
    assert profile.status_code == 200
    assert profile.json()["verification_status"] == "UNVERIFIED"
    assert profile.json()["profile_complete"] is False

    updated = client.put(
        "/api/lawyer/profile",
        json={
            "bar_registration_number": "BAR-12345",
            "jurisdiction": "Maharashtra",
            "years_experience": 8,
            "practice_areas": ["property", "family"],
            "bio": "Property and family litigation.",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["profile_complete"] is True

    submitted = client.post("/api/lawyer/profile/verification")
    assert submitted.status_code == 200
    assert submitted.json()["verification_status"] == "PENDING"

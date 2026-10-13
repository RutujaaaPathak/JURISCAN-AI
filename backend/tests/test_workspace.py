"""Tests for the client-facing workflow: lawyer directory, private case
workspace (messages, fees, appointments), document sharing, client overview and
notifications.

Authorization is exercised for real by overriding the current-user dependency,
since no authentication layer exists yet. Privacy tests assert that unrelated
users receive 404 rather than being able to see another party's case.
"""

import threading

import pytest

from app.api.deps import get_current_user
from app.core.database import SessionLocal
from app.models import LawyerProfile, User

CONTRACT = """1. Indemnity
The Supplier shall indemnify the Customer against all losses without any cap.
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


def _make_lawyer(client, login, name, **profile):
    lawyer = _make_user("lawyer", name)
    login(lawyer)
    data = {
        "bar_registration_number": f"BAR-{name}",
        "jurisdiction": "Maharashtra",
        "years_experience": 5,
        "practice_areas": ["property"],
        "languages": ["English"],
        "location": "Pune",
        "consultation_modes": ["video"],
        "bio": "Property litigation.",
    }
    data.update(profile)
    response = client.put("/api/lawyer/profile", json=data)
    assert response.status_code == 200, response.text
    return lawyer


def _verify(user_id: int) -> None:
    db = SessionLocal()
    try:
        profile = db.query(LawyerProfile).filter_by(user_id=user_id).one()
        profile.verification_status = "VERIFIED"
        db.commit()
    finally:
        db.close()


def _assigned_case(client, login):
    """Create a case owned by a new client and assign it to a new lawyer.
    Returns (client_user, lawyer, case_id)."""

    client_user = _make_user("individual", "ws-client")
    login(client_user)
    case_id = _create_case(client).json()["id"]
    lawyer = _make_user("lawyer", "ws-lawyer")
    login(lawyer)
    accepted = client.post(f"/api/cases/{case_id}/accept")
    assert accepted.status_code == 200, accepted.text
    return client_user, lawyer, case_id


# ---------------------------------------------------------------------------
# Lawyer directory
# ---------------------------------------------------------------------------


def test_lawyer_directory_lists_and_filters(client, login):
    client_user = _make_user("individual", "dir-client")
    lawyer_a = _make_lawyer(
        client,
        login,
        "dir-a",
        practice_areas=["property"],
        location="Pune",
        years_experience=10,
        consultation_modes=["video", "phone"],
    )
    lawyer_b = _make_lawyer(
        client,
        login,
        "dir-b",
        practice_areas=["family"],
        jurisdiction="Delhi",
        location="Delhi",
        years_experience=2,
        consultation_modes=["in-person"],
    )

    login(client_user)
    everything = client.get("/api/lawyers")
    assert everything.status_code == 200
    assert everything.json()["total"] == 2

    by_category = client.get("/api/lawyers?category=property").json()
    assert by_category["total"] == 1
    assert by_category["items"][0]["user_id"] == lawyer_a.id

    by_location = client.get("/api/lawyers?location=pune").json()
    assert by_location["total"] == 1
    assert by_location["items"][0]["user_id"] == lawyer_a.id

    by_experience = client.get("/api/lawyers?min_experience=5").json()
    assert by_experience["total"] == 1
    assert by_experience["items"][0]["user_id"] == lawyer_a.id

    by_mode = client.get("/api/lawyers?consultation_mode=in-person").json()
    assert by_mode["total"] == 1
    assert by_mode["items"][0]["user_id"] == lawyer_b.id

    by_query = client.get("/api/lawyers?q=family").json()
    assert by_query["total"] == 1
    assert by_query["items"][0]["user_id"] == lawyer_b.id

    detail = client.get(f"/api/lawyers/{lawyer_a.id}")
    assert detail.status_code == 200
    assert detail.json()["practice_areas"] == ["property"]


def test_lawyer_directory_verified_filter_and_ordering(client, login):
    client_user = _make_user("individual", "dir-verified-client")
    junior = _make_lawyer(client, login, "dir-junior", years_experience=3)
    senior = _make_lawyer(client, login, "dir-senior", years_experience=20)
    _verify(senior.id)

    login(client_user)
    verified = client.get("/api/lawyers?verified_only=true").json()
    assert verified["total"] == 1
    assert verified["items"][0]["user_id"] == senior.id

    ordered = client.get("/api/lawyers").json()["items"]
    assert [entry["user_id"] for entry in ordered][0] == senior.id
    assert junior.id in {entry["user_id"] for entry in ordered}


def test_lawyer_directory_unknown_returns_404(client, login):
    login(_make_user("individual", "dir-none"))
    response = client.get("/api/lawyers/999999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "lawyer_not_found"


# ---------------------------------------------------------------------------
# Private workspace access control
# ---------------------------------------------------------------------------


def test_workspace_requires_assignment_and_party(client, login):
    client_user = _make_user("individual", "guard-client")
    login(client_user)
    case_id = _create_case(client).json()["id"]

    # Assigned lawyer does not exist yet -> conflict, not a leak.
    assert client.get(f"/api/cases/{case_id}/messages").status_code == 409

    stranger_lawyer = _make_user("lawyer", "guard-stranger")
    stranger_client = _make_user("individual", "guard-other-client")

    login(stranger_lawyer)
    assert client.get(f"/api/cases/{case_id}/messages").status_code == 404
    assert client.post(f"/api/cases/{case_id}/messages", json={"body": "hi"}).status_code == 404

    login(stranger_client)
    assert client.get(f"/api/cases/{case_id}/messages").status_code == 404

    lawyer = _make_user("lawyer", "guard-lawyer")
    login(lawyer)
    assert client.post(f"/api/cases/{case_id}/accept").status_code == 200

    login(client_user)
    assert client.get(f"/api/cases/{case_id}/messages").status_code == 200


def test_messaging_between_parties_and_unread_counts(client, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    login(client_user)
    sent = client.post(f"/api/cases/{case_id}/messages", json={"body": "Hello counsel."})
    assert sent.status_code == 201
    assert sent.json()["unread"] == 0
    assert len(sent.json()["items"]) == 1

    login(lawyer)
    inbox = client.get(f"/api/cases/{case_id}/messages").json()
    assert inbox["unread"] == 1
    assert inbox["items"][0]["sender_name"]

    read = client.post(f"/api/cases/{case_id}/messages/read")
    assert read.status_code == 200
    assert read.json()["unread"] == 0

    client.post(f"/api/cases/{case_id}/messages", json={"body": "Reviewing now."})
    login(client_user)
    assert client.get(f"/api/cases/{case_id}/messages").json()["unread"] == 1


def test_fee_proposal_negotiation(client, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    stranger = _make_user("lawyer", "fee-stranger")
    login(stranger)
    assert client.get(f"/api/cases/{case_id}/fees").status_code == 404

    login(client_user)
    first = client.post(
        f"/api/cases/{case_id}/fees", json={"amount": "5000", "note": "Retainer"}
    )
    assert first.status_code == 201
    assert first.json()[0]["status"] == "PROPOSED"

    second = client.post(f"/api/cases/{case_id}/fees", json={"amount": "6500"}).json()
    statuses = {row["status"] for row in second}
    assert "SUPERSEDED" in statuses and "PROPOSED" in statuses
    proposal_id = next(row["id"] for row in second if row["status"] == "PROPOSED")

    login(lawyer)
    accepted = client.post(f"/api/cases/{case_id}/fees/{proposal_id}/accept")
    assert accepted.status_code == 200
    assert next(row for row in accepted.json() if row["id"] == proposal_id)["status"] == "ACCEPTED"

    assert client.post(f"/api/cases/{case_id}/fees/{proposal_id}/accept").status_code == 409


def test_appointment_propose_confirm_cancel(client, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    login(client_user)
    proposed = client.post(
        f"/api/cases/{case_id}/appointments",
        json={
            "scheduled_at": "2030-01-01T10:00:00+00:00",
            "duration_minutes": 30,
            "mode": "video",
        },
    )
    assert proposed.status_code == 201
    appointment_id = proposed.json()[0]["id"]
    assert proposed.json()[0]["status"] == "PROPOSED"

    login(lawyer)
    confirmed = client.post(f"/api/cases/{case_id}/appointments/{appointment_id}/confirm")
    assert confirmed.json()[0]["status"] == "CONFIRMED"

    login(client_user)
    cancelled = client.post(f"/api/cases/{case_id}/appointments/{appointment_id}/cancel")
    assert cancelled.json()[0]["status"] == "CANCELLED"

    assert (
        client.post(f"/api/cases/{case_id}/appointments/{appointment_id}/confirm").status_code
        == 409
    )


# ---------------------------------------------------------------------------
# Document sharing
# ---------------------------------------------------------------------------


def test_document_sharing_permissions(client, login):
    client_user = _make_user("individual", "share-client")
    login(client_user)
    owned = client.post(
        "/api/documents",
        files={"file": ("contract.txt", CONTRACT.encode("utf-8"), "text/plain")},
    ).json()["id"]
    case_id = _create_case(client).json()["id"]

    attached = client.post(
        f"/api/cases/{case_id}/documents", json={"document_id": owned}
    )
    assert attached.status_code == 201
    assert attached.json()["document_count"] == 1

    duplicate = client.post(f"/api/cases/{case_id}/documents", json={"document_id": owned})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "document_already_attached"

    stranger = _make_user("individual", "share-stranger")
    login(stranger)
    other_doc = client.post(
        "/api/documents",
        files={"file": ("other.txt", b"1. Lease\nA distinct lease agreement body.", "text/plain")},
    ).json()["id"]
    # Neither a foreign case nor a foreign document is accessible.
    assert (
        client.post(f"/api/cases/{case_id}/documents", json={"document_id": other_doc}).status_code
        == 404
    )


# ---------------------------------------------------------------------------
# Overview + notifications
# ---------------------------------------------------------------------------


def test_client_overview_reports_real_counts(client, login):
    client_user = _make_user("individual", "ov-client")
    login(client_user)
    case_a = _create_case(client, title="Open request A").json()["id"]
    _create_case(client, title="Open request B")
    case_c = _create_case(client, title="Matter C").json()["id"]

    lawyer = _make_user("lawyer", "ov-lawyer")
    login(lawyer)
    client.post(f"/api/cases/{case_c}/accept")
    appointment_id = client.post(
        f"/api/cases/{case_c}/appointments",
        json={"scheduled_at": "2030-05-01T09:00:00+00:00", "mode": "video"},
    ).json()[0]["id"]

    login(client_user)
    client.post(f"/api/cases/{case_c}/appointments/{appointment_id}/confirm")
    client.post(f"/api/cases/{case_c}/messages", json={"body": "Question"})

    overview = client.get("/api/cases/user-overview").json()
    assert overview["submitted_cases"] == 3
    assert overview["open_requests"] == 2
    assert overview["active_matters"] == 1
    assert overview["completed_matters"] == 0
    assert overview["upcoming_consultations"] == 1

    # A message from the lawyer would be unread; the client's own message is not.
    assert overview["unread_messages"] == 0
    login(lawyer)
    client.post(f"/api/cases/{case_c}/messages", json={"body": "Answer"})
    login(client_user)
    assert client.get("/api/cases/user-overview").json()["unread_messages"] == 1


def test_notifications_reflect_other_parties(client, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    login(client_user)
    kinds = {item["kind"] for item in client.get("/api/notifications").json()}
    assert "ACCEPTED" in kinds
    assert "CREATED" not in kinds  # own action is not a notification

    login(lawyer)
    lawyer_kinds = {item["kind"] for item in client.get("/api/notifications").json()}
    assert "CREATED" in lawyer_kinds
    assert "ACCEPTED" not in lawyer_kinds  # own action

    login(client_user)
    client.post(f"/api/cases/{case_id}/messages", json={"body": "Keep me posted."})
    login(lawyer)
    messages = [item for item in client.get("/api/notifications").json() if item["kind"] == "MESSAGE"]
    assert messages and messages[0]["case_id"] == case_id


def test_lawyer_overview_reports_unread_and_handled(client, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    login(lawyer)
    overview = client.get("/api/cases/overview").json()
    assert overview["active_cases"] == 1
    # An accepted case counts once as handled, not twice (active + decision).
    assert overview["total_handled"] == 1
    assert overview["unread_messages"] == 0

    login(client_user)
    client.post(f"/api/cases/{case_id}/messages", json={"body": "Any update?"})

    login(lawyer)
    assert client.get("/api/cases/overview").json()["unread_messages"] == 1

    client.post(f"/api/cases/{case_id}/messages/read")
    assert client.get("/api/cases/overview").json()["unread_messages"] == 0

    client.post(f"/api/cases/{case_id}/complete")
    after = client.get("/api/cases/overview").json()
    assert after["completed_cases"] == 1
    assert after["active_cases"] == 0
    # Still handled exactly once after completion.
    assert after["total_handled"] == 1


def test_end_to_end_client_lawyer_workflow(client, login):
    """Drive one matter through the whole lifecycle across both dashboards:
    upload -> post with document -> accept -> message -> fee -> consultation ->
    complete, then check the client overview reflects reality."""

    client_user = _make_user("individual", "e2e-client")
    login(client_user)
    document_id = client.post(
        "/api/documents",
        files={"file": ("lease.txt", CONTRACT.encode("utf-8"), "text/plain")},
    ).json()["id"]
    case_id = _create_case(
        client, title="Lease review needed", document_ids=[document_id]
    ).json()["id"]

    lawyer = _make_user("lawyer", "e2e-lawyer")
    login(lawyer)
    # The open case shows up in the marketplace with its attached document.
    available = client.get("/api/cases?limit=50").json()
    assert case_id in {item["id"] for item in available["items"]}
    detail = client.get(f"/api/cases/{case_id}").json()
    assert detail["documents"][0]["document_id"] == document_id

    assert client.post(f"/api/cases/{case_id}/accept").status_code == 200

    # Both directions of the private conversation.
    client.post(f"/api/cases/{case_id}/messages", json={"body": "I can take this."})
    login(client_user)
    assert client.get(f"/api/cases/{case_id}/messages").json()["unread"] == 1
    client.post(f"/api/cases/{case_id}/messages/read")
    client.post(f"/api/cases/{case_id}/messages", json={"body": "Thank you."})

    # Fee negotiation: lawyer proposes, client accepts.
    login(lawyer)
    fee_id = client.post(f"/api/cases/{case_id}/fees", json={"amount": "12000"}).json()[0]["id"]
    login(client_user)
    accepted = client.post(f"/api/cases/{case_id}/fees/{fee_id}/accept").json()
    assert next(row for row in accepted if row["id"] == fee_id)["status"] == "ACCEPTED"

    # Consultation: lawyer proposes, client confirms.
    login(lawyer)
    appointment_id = client.post(
        f"/api/cases/{case_id}/appointments",
        json={
            "scheduled_at": "2030-06-01T10:00:00+00:00",
            "duration_minutes": 45,
            "mode": "video",
        },
    ).json()[0]["id"]
    login(client_user)
    confirmed = client.post(
        f"/api/cases/{case_id}/appointments/{appointment_id}/confirm"
    ).json()
    assert confirmed[0]["status"] == "CONFIRMED"

    # Lawyer completes the matter.
    login(lawyer)
    assert client.post(f"/api/cases/{case_id}/complete").json()["status"] == "COMPLETED"

    # The client's own dashboard now reflects the finished matter.
    login(client_user)
    overview = client.get("/api/cases/user-overview").json()
    assert overview["active_matters"] == 0
    assert overview["completed_matters"] == 1
    assert overview["upcoming_consultations"] == 1


# ---------------------------------------------------------------------------
# Concurrent exclusive acceptance (database-level atomicity)
# ---------------------------------------------------------------------------


def test_concurrent_accept_only_one_wins(client, login):
    from sqlalchemy import update

    from app.models import Case

    client_user = _make_user("individual", "race-client")
    lawyer_a = _make_user("lawyer", "race-lawyer-a")
    lawyer_b = _make_user("lawyer", "race-lawyer-b")

    login(client_user)
    case_id = _create_case(client).json()["id"]

    barrier = threading.Barrier(2)
    results: list[int] = []
    lock = threading.Lock()

    def attempt(user_id: int) -> None:
        db = SessionLocal()
        try:
            barrier.wait()
            result = db.execute(
                update(Case)
                .where(
                    Case.id == case_id,
                    Case.status == "OPEN",
                    Case.assigned_lawyer_id.is_(None),
                )
                .values(status="ASSIGNED", assigned_lawyer_id=user_id)
            )
            db.commit()
            with lock:
                results.append(result.rowcount)
        finally:
            db.close()

    threads = [threading.Thread(target=attempt, args=(uid,)) for uid in (lawyer_a.id, lawyer_b.id)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == [0, 1]

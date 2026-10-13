"""Hardening tests for case privacy, the pre-assignment clarification workflow,
and server-side permission rules (fee proposals, appointment confirmation, case
status transitions).

Authorization is exercised for real by overriding the current-user dependency,
because no authentication layer exists yet. Privacy tests assert that unrelated
users either receive 404 or see empty collections rather than another party's
private data.
"""

import pytest

from app.api.deps import get_current_user
from app.core.database import SessionLocal
from app.models import User


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


def _assigned_case(client, login):
    client_user = _make_user("individual", "hard-client")
    login(client_user)
    case_id = _create_case(client).json()["id"]
    lawyer = _make_user("lawyer", "hard-lawyer")
    login(lawyer)
    accepted = client.post(f"/api/cases/{case_id}/accept")
    assert accepted.status_code == 200, accepted.text
    return client_user, lawyer, case_id


# ---------------------------------------------------------------------------
# Case privacy: other lawyers must not see decisions / activities
# ---------------------------------------------------------------------------


def test_browsing_lawyer_cannot_see_other_lawyers_decisions(client, login):
    client_user = _make_user("individual", "priv-client")
    login(client_user)
    case_id = _create_case(client).json()["id"]

    lawyer_a = _make_user("lawyer", "priv-lawyer-a")
    login(lawyer_a)
    declined = client.post(
        f"/api/cases/{case_id}/reject",
        json={"reason": "Conflict of interest: former client."},
    )
    assert declined.status_code == 200

    # A different lawyer browsing the still-open case sees the marketplace view
    # but none of lawyer A's private decision data or the activity trail.
    lawyer_b = _make_user("lawyer", "priv-lawyer-b")
    login(lawyer_b)
    detail = client.get(f"/api/cases/{case_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["my_decision"] is None
    assert body["decisions"] == []
    assert body["activities"] == []
    assert "Conflict of interest" not in detail.text

    # The client, as a party, still sees the full history.
    login(client_user)
    own = client.get(f"/api/cases/{case_id}").json()
    assert len(own["decisions"]) == 1
    assert own["decisions"][0]["reason"] == "Conflict of interest: former client."
    assert any(item["action"] == "DECLINED" for item in own["activities"])


def test_browsing_lawyer_does_not_see_request_info_decision(client, login):
    client_user = _make_user("individual", "priv-info-client")
    login(client_user)
    case_id = _create_case(client).json()["id"]

    lawyer_a = _make_user("lawyer", "priv-info-a")
    login(lawyer_a)
    asked = client.post(
        f"/api/cases/{case_id}/request-info",
        json={"message": "Please share the property deed."},
    )
    assert asked.status_code == 200

    lawyer_b = _make_user("lawyer", "priv-info-b")
    login(lawyer_b)
    body = client.get(f"/api/cases/{case_id}").json()
    assert body["decisions"] == []
    assert body["activities"] == []
    assert "property deed" not in client.get(f"/api/cases/{case_id}").text

    # And lawyer B cannot read lawyer A's clarification thread either.
    threads = client.get(f"/api/cases/{case_id}/clarifications").json()["threads"]
    assert threads == []


def test_stranger_client_cannot_view_case_or_clarifications(client, login):
    client_user = _make_user("individual", "priv-owner")
    login(client_user)
    case_id = _create_case(client).json()["id"]

    stranger = _make_user("individual", "priv-stranger")
    login(stranger)
    assert client.get(f"/api/cases/{case_id}").status_code == 404
    assert client.get(f"/api/cases/{case_id}/clarifications").status_code == 404


# ---------------------------------------------------------------------------
# Clarification workflow
# ---------------------------------------------------------------------------


def test_clarification_thread_is_private_between_lawyer_and_client(client, login):
    client_user = _make_user("individual", "clar-client")
    login(client_user)
    case_id = _create_case(client).json()["id"]

    lawyer_a = _make_user("lawyer", "clar-a")
    login(lawyer_a)
    asked = client.post(
        f"/api/cases/{case_id}/clarifications",
        json={"message": "Is there a written agreement?"},
    )
    assert asked.status_code == 201, asked.text
    threads = asked.json()["threads"]
    assert len(threads) == 1
    assert threads[0]["lawyer_id"] == lawyer_a.id
    assert [item["body"] for item in threads[0]["items"]] == ["Is there a written agreement?"]
    # Starting a clarification moves the case into the lawyer's pending list.
    assert [row["id"] for row in client.get("/api/cases/mine").json()["pending"]] == [case_id]

    # The client sees the thread and its unread question, and can answer.
    login(client_user)
    owner_view = client.get(f"/api/cases/{case_id}/clarifications").json()["threads"]
    assert len(owner_view) == 1
    assert owner_view[0]["lawyer_name"]
    assert owner_view[0]["unread"] == 1
    replied = client.post(
        f"/api/cases/{case_id}/clarifications",
        json={"message": "Yes, a signed agreement exists.", "lawyer_id": lawyer_a.id},
    )
    assert replied.status_code == 201, replied.text
    assert len(replied.json()["threads"][0]["items"]) == 2

    # A competing lawyer can start their own thread but never sees lawyer A's.
    lawyer_b = _make_user("lawyer", "clar-b")
    login(lawyer_b)
    assert client.get(f"/api/cases/{case_id}/clarifications").json()["threads"] == []
    own = client.post(
        f"/api/cases/{case_id}/clarifications",
        json={"message": "Do you have survey documents?"},
    )
    assert own.status_code == 201
    b_threads = own.json()["threads"]
    assert len(b_threads) == 1 and b_threads[0]["lawyer_id"] == lawyer_b.id

    # Lawyer A only ever sees A's thread, including the client's answer, and
    # never sees lawyer B's question.
    login(lawyer_a)
    a_threads = client.get(f"/api/cases/{case_id}/clarifications").json()["threads"]
    assert len(a_threads) == 1
    bodies = [item["body"] for item in a_threads[0]["items"]]
    assert "Yes, a signed agreement exists." in bodies
    assert all(thread["lawyer_id"] == lawyer_a.id for thread in a_threads)
    assert "survey documents" not in client.get(f"/api/cases/{case_id}/clarifications").text


def test_clarification_reply_requires_existing_thread(client, login):
    client_user = _make_user("individual", "clar-reply-client")
    login(client_user)
    case_id = _create_case(client).json()["id"]

    # No request has been made, so there is nothing to answer.
    missing = _make_user("lawyer", "clar-absent-lawyer")
    assert (
        client.post(
            f"/api/cases/{case_id}/clarifications",
            json={"message": "Answer", "lawyer_id": missing.id},
        ).status_code
        == 404
    )
    # A lawyer id is required for the client to reply.
    assert (
        client.post(
            f"/api/cases/{case_id}/clarifications", json={"message": "Answer"}
        ).status_code
        == 422
    )


def test_clarifications_hidden_after_assignment(client, login):
    client_user, lawyer, case_id = _assigned_case(client, login)
    other = _make_user("lawyer", "clar-after-other")

    # An unrelated lawyer cannot even reach the case once assigned.
    login(other)
    assert client.get(f"/api/cases/{case_id}/clarifications").status_code == 404

    # The assigned lawyer (a party) may still list threads (none here).
    login(lawyer)
    assert client.get(f"/api/cases/{case_id}/clarifications").json()["threads"] == []


def test_lawyer_owned_case_owner_sees_all_threads(client, login):
    # A lawyer can also post a case; when they are the owner they must see every
    # clarification thread, not be mistaken for an interested lawyer.
    owner = _make_user("lawyer", "clar-owner")
    login(owner)
    case_id = _create_case(client, title="Lawyer's own matter").json()["id"]

    requester = _make_user("lawyer", "clar-requester")
    login(requester)
    assert (
        client.post(
            f"/api/cases/{case_id}/clarifications", json={"message": "Any updates?"}
        ).status_code
        == 201
    )

    login(owner)
    threads = client.get(f"/api/cases/{case_id}/clarifications").json()["threads"]
    assert len(threads) == 1
    assert threads[0]["lawyer_id"] == requester.id
    answered = client.post(
        f"/api/cases/{case_id}/clarifications",
        json={"message": "Not yet.", "lawyer_id": requester.id},
    )
    assert answered.status_code == 201


def test_clarification_read_marks_and_notifications(client, login):
    client_user = _make_user("individual", "clar-notif-client")
    login(client_user)
    case_id = _create_case(client).json()["id"]

    lawyer = _make_user("lawyer", "clar-notif-lawyer")
    login(lawyer)
    client.post(f"/api/cases/{case_id}/clarifications", json={"message": "Question one?"})

    # The client has an unread clarification and a notification for it.
    login(client_user)
    assert client.get(f"/api/cases/{case_id}/clarifications").json()["threads"][0]["unread"] == 1
    assert client.get("/api/cases/user-overview").json()["unread_messages"] == 1
    kinds = {item["kind"] for item in client.get("/api/notifications").json()}
    assert "MESSAGE" in kinds
    client.post(f"/api/cases/{case_id}/clarifications/read", json={})
    assert client.get(f"/api/cases/{case_id}/clarifications").json()["threads"][0]["unread"] == 0
    assert client.get("/api/cases/user-overview").json()["unread_messages"] == 0

    # The client replies; the lawyer now has one unread clarification.
    client.post(
        f"/api/cases/{case_id}/clarifications",
        json={"message": "Answer one.", "lawyer_id": lawyer.id},
    )
    login(lawyer)
    assert client.get(f"/api/cases/{case_id}/clarifications").json()["threads"][0]["unread"] == 1
    assert client.get("/api/cases/overview").json()["unread_messages"] == 1
    client.post(f"/api/cases/{case_id}/clarifications/read", json={})
    assert client.get("/api/cases/overview").json()["unread_messages"] == 0


# ---------------------------------------------------------------------------
# Invalid state transitions and permission rules
# ---------------------------------------------------------------------------


def test_accept_after_reject_is_blocked(client, login):
    client_user = _make_user("individual", "trans-client")
    login(client_user)
    case_id = _create_case(client).json()["id"]

    lawyer = _make_user("lawyer", "trans-lawyer")
    login(lawyer)
    assert (
        client.post(f"/api/cases/{case_id}/reject", json={"reason": "Conflict"}).status_code
        == 200
    )
    again = client.post(f"/api/cases/{case_id}/accept")
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "already_declined"


def test_lawyer_can_accept_after_requesting_info(client, login):
    client_user = _make_user("individual", "trans-info-client")
    login(client_user)
    case_id = _create_case(client).json()["id"]

    lawyer = _make_user("lawyer", "trans-info-lawyer")
    login(lawyer)
    assert (
        client.post(
            f"/api/cases/{case_id}/request-info", json={"message": "Need the deed."}
        ).status_code
        == 200
    )
    # Requesting information is not a rejection: the same lawyer may still accept.
    accepted = client.post(f"/api/cases/{case_id}/accept")
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["assigned_lawyer_id"] == lawyer.id


def test_fee_proposer_cannot_accept_or_decline_own_proposal(client, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    login(client_user)
    proposal_id = client.post(
        f"/api/cases/{case_id}/fees", json={"amount": "9000"}
    ).json()[0]["id"]
    own_accept = client.post(f"/api/cases/{case_id}/fees/{proposal_id}/accept")
    assert own_accept.status_code == 403
    assert own_accept.json()["error"]["code"] == "own_proposal"
    own_decline = client.post(f"/api/cases/{case_id}/fees/{proposal_id}/decline")
    assert own_decline.status_code == 403

    # The other party can still accept.
    login(lawyer)
    accepted = client.post(f"/api/cases/{case_id}/fees/{proposal_id}/accept")
    assert accepted.status_code == 200


def test_appointment_proposer_cannot_confirm_and_cannot_reconfirm(client, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    login(client_user)
    appointment_id = client.post(
        f"/api/cases/{case_id}/appointments",
        json={"scheduled_at": "2030-02-02T10:00:00+00:00", "mode": "video"},
    ).json()[0]["id"]
    own_confirm = client.post(f"/api/cases/{case_id}/appointments/{appointment_id}/confirm")
    assert own_confirm.status_code == 403
    assert own_confirm.json()["error"]["code"] == "own_proposal"

    login(lawyer)
    confirmed = client.post(f"/api/cases/{case_id}/appointments/{appointment_id}/confirm")
    assert confirmed.status_code == 200
    assert confirmed.json()[0]["status"] == "CONFIRMED"

    # Confirming again is an invalid transition (not PROPOSED any more).
    again = client.post(f"/api/cases/{case_id}/appointments/{appointment_id}/confirm")
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "appointment_not_proposed"


def test_workspace_endpoints_reject_strangers(client, login):
    client_user, lawyer, case_id = _assigned_case(client, login)
    stranger = _make_user("lawyer", "trans-stranger")

    login(stranger)
    assert client.get(f"/api/cases/{case_id}/fees").status_code == 404
    assert client.get(f"/api/cases/{case_id}/appointments").status_code == 404
    assert client.post(f"/api/cases/{case_id}/messages", json={"body": "hi"}).status_code == 404

    # The client cannot see another client's case workspace.
    other_client = _make_user("individual", "trans-other-client")
    login(other_client)
    assert client.get(f"/api/cases/{case_id}/fees").status_code == 404

"""Regression tests for cross-tenant document isolation (Phase 6B.1).

These lock down SEC-01 and SEC-02:

* content-hash deduplication is scoped to a company or to one user's personal
  workspace, never to the global document table;
* identical documents can exist for different users and different companies;
* joining a company never annexes or reassigns a user's personal documents;
* document, analysis and report reads stay inside the caller's tenant.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import settings
from app.core.database import SessionLocal
from app.core.security import create_access_token, hash_password
from app.models import Company, Document, User

SAMPLE_CONTRACT = (
    b"1. Indemnity\n"
    b"The Supplier shall indemnify the Customer for all losses without any cap.\n\n"
    b"2. Payment\n"
    b"Payment shall be due within ninety (90) days of a valid invoice.\n\n"
    b"3. Termination\n"
    b"Either party may terminate this Agreement for convenience.\n"
)

ALT_CONTRACT = (
    b"1. Confidentiality\n"
    b"Each party shall keep the other party's information confidential.\n\n"
    b"2. Governing Law\n"
    b"This Agreement is governed by the laws of the State of Delaware.\n"
)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_company(name: str) -> int:
    with SessionLocal() as db:
        company = Company(name=name)
        db.add(company)
        db.commit()
        db.refresh(company)
        return company.id


def _make_user(
    role: str,
    email: str,
    *,
    company_id: int | None = None,
    company_role: str | None = None,
    organization_name: str | None = None,
    password: str | None = None,
) -> tuple[int, dict[str, str]]:
    with SessionLocal() as db:
        user = User(
            email=email,
            username=email,
            full_name=email.split("@")[0].title(),
            organization_name=organization_name,
            role=role,
            company_id=company_id,
            company_role=company_role,
            hashed_password=hash_password(password) if password else None,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id

    token = create_access_token(
        user_id, secret=settings.secret_key, ttl_seconds=3600
    )
    return user_id, _auth(token)


def _upload(
    client: TestClient,
    headers: dict[str, str],
    *,
    content: bytes = SAMPLE_CONTRACT,
    filename: str = "contract.txt",
):
    return client.post(
        "/api/documents",
        headers=headers,
        files={"file": (filename, content, "text/plain")},
    )


def _document_count(**filters) -> int:
    with SessionLocal() as db:
        stmt = select(func.count()).select_from(Document)
        for column, value in filters.items():
            stmt = stmt.where(getattr(Document, column) == value)
        return int(db.scalar(stmt) or 0)


def test_same_user_duplicate_personal_document_is_rejected(client: TestClient):
    user_id, headers = _make_user("individual", "alice@example.com")

    first = _upload(client, headers, filename="alice-nda.txt")
    assert first.status_code == 201, first.text
    first_id = first.json()["id"]

    duplicate = _upload(client, headers, filename="alice-nda-copy.txt")
    assert duplicate.status_code == 409
    error = duplicate.json()["error"]
    assert error["code"] == "duplicate_document"
    assert error["details"]["document_id"] == first_id

    assert _document_count(user_id=user_id) == 1
    with SessionLocal() as db:
        document = db.get(Document, first_id)
        assert document.company_id is None


def test_different_users_can_upload_identical_personal_documents(client: TestClient):
    alice_id, alice_headers = _make_user("individual", "alice@example.com")
    bob_id, bob_headers = _make_user("individual", "bob@example.com")

    alice = _upload(client, alice_headers, filename="shared-template.txt")
    bob = _upload(client, bob_headers, filename="shared-template.txt")
    assert alice.status_code == 201, alice.text
    assert bob.status_code == 201, bob.text

    alice_doc = alice.json()
    bob_doc = bob.json()
    assert alice_doc["id"] != bob_doc["id"]

    # Each user only sees their own personal document.
    alice_list = client.get("/api/documents", headers=alice_headers).json()
    bob_list = client.get("/api/documents", headers=bob_headers).json()
    assert alice_list["total"] == 1
    assert bob_list["total"] == 1
    assert alice_list["items"][0]["id"] == alice_doc["id"]
    assert bob_list["items"][0]["id"] == bob_doc["id"]

    # Cross-user reads are hidden as not found, including analyses and reports.
    assert (
        client.get(f"/api/documents/{alice_doc['id']}", headers=bob_headers).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/documents/{alice_doc['id']}/report", headers=bob_headers
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/analyses/{alice_doc['analysis']['id']}", headers=bob_headers
        ).status_code
        == 404
    )

    with SessionLocal() as db:
        alice_row = db.get(Document, alice_doc["id"])
        bob_row = db.get(Document, bob_doc["id"])
        assert alice_row.user_id == alice_id
        assert bob_row.user_id == bob_id
        assert alice_row.company_id is None
        assert bob_row.company_id is None
        assert alice_row.content_hash == bob_row.content_hash


def test_two_companies_can_upload_identical_documents_without_cross_access(
    client: TestClient,
):
    company_a = _make_company("Alpha Holdings")
    company_b = _make_company("Beta Holdings")
    _, admin_a = _make_user(
        "company",
        "admin@alpha.example.com",
        company_id=company_a,
        company_role="COMPANY_ADMIN",
    )
    _, admin_b = _make_user(
        "company",
        "admin@beta.example.com",
        company_id=company_b,
        company_role="COMPANY_ADMIN",
    )

    alpha = _upload(client, admin_a, filename="standard-safe.txt")
    beta = _upload(client, admin_b, filename="standard-safe.txt")
    assert alpha.status_code == 201, alpha.text
    assert beta.status_code == 201, beta.text

    alpha_doc = alpha.json()
    beta_doc = beta.json()
    assert alpha_doc["id"] != beta_doc["id"]

    with SessionLocal() as db:
        alpha_row = db.get(Document, alpha_doc["id"])
        beta_row = db.get(Document, beta_doc["id"])
        assert alpha_row.company_id == company_a
        assert beta_row.company_id == company_b
        assert alpha_row.content_hash == beta_row.content_hash

    # Each company's audit workspace only lists its own document.
    alpha_reports = client.get("/api/company/audit-reports", headers=admin_a).json()
    beta_reports = client.get("/api/company/audit-reports", headers=admin_b).json()
    assert alpha_reports["total"] == 1
    assert beta_reports["total"] == 1
    assert alpha_reports["items"][0]["document_id"] == alpha_doc["id"]
    assert beta_reports["items"][0]["document_id"] == beta_doc["id"]

    # Company B cannot read Company A's document, analysis or report.
    assert (
        client.get(f"/api/documents/{alpha_doc['id']}", headers=admin_b).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/documents/{alpha_doc['id']}/report", headers=admin_b
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/analyses/{alpha_doc['analysis']['id']}", headers=admin_b
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/company/audit-reports/{alpha_doc['id']}", headers=admin_b
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/company/audit-reports/{alpha_doc['id']}/report", headers=admin_b
        ).status_code
        == 404
    )

    # Re-uploading inside Company B points at Company B's own copy, never at
    # Company A's document (no cross-tenant existence oracle).
    duplicate = _upload(client, admin_b, filename="standard-safe-copy.txt")
    assert duplicate.status_code == 409
    details = duplicate.json()["error"]["details"]
    assert details["document_id"] == beta_doc["id"]
    assert details["document_id"] != alpha_doc["id"]


def test_company_upload_does_not_join_existing_company_by_name(client: TestClient):
    existing_company = _make_company("Acme Legal")
    _, existing_admin = _make_user(
        "company",
        "admin@acme.example.com",
        company_id=existing_company,
        company_role="COMPANY_ADMIN",
    )
    new_user_id, new_headers = _make_user(
        "company",
        "new@acme.example.com",
        company_role="COMPANY_ADMIN",
        organization_name="Acme Legal",
    )

    uploaded = _upload(client, new_headers, filename="new-workspace.txt")
    assert uploaded.status_code == 201, uploaded.text
    uploaded_id = uploaded.json()["id"]

    with SessionLocal() as db:
        new_user = db.get(User, new_user_id)
        assert new_user.company_id is not None
        assert new_user.company_id != existing_company
        document = db.get(Document, uploaded_id)
        assert document.company_id == new_user.company_id

    # The pre-existing company with the same name gains nothing.
    existing_reports = client.get(
        "/api/company/audit-reports", headers=existing_admin
    ).json()
    assert existing_reports["total"] == 0

    new_reports = client.get("/api/company/audit-reports", headers=new_headers).json()
    assert new_reports["total"] == 1
    assert new_reports["items"][0]["document_id"] == uploaded_id


def test_personal_document_stays_private_after_user_joins_company(
    client: TestClient,
):
    password = "personal-pass-123"
    alice_id, alice_headers = _make_user(
        "individual", "alice@example.com", password=password
    )
    personal = _upload(client, alice_headers, filename="personal-divorce.txt")
    assert personal.status_code == 201, personal.text
    personal_id = personal.json()["id"]

    company_id = _make_company("Acme Legal")
    _, admin_headers = _make_user(
        "company",
        "admin@acme.example.com",
        company_id=company_id,
        company_role="COMPANY_ADMIN",
    )

    invitation = client.post(
        "/api/company/team/invitations",
        headers=admin_headers,
        json={"email": "alice@example.com", "company_role": "MEMBER"},
    )
    assert invitation.status_code == 201, invitation.text
    token = invitation.json()["development_invitation_token"]

    accepted = client.post(
        "/api/company/invitations/accept",
        json={"token": token, "password": password},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["user"]["company_id"] == company_id

    # Joining the company must not move or expose the personal document.
    with SessionLocal() as db:
        personal_row = db.get(Document, personal_id)
        assert personal_row.user_id == alice_id
        assert personal_row.company_id is None

    admin_reports = client.get("/api/company/audit-reports", headers=admin_headers)
    assert admin_reports.status_code == 200
    assert admin_reports.json()["total"] == 0

    assert (
        client.get(
            f"/api/documents/{personal_id}", headers=admin_headers
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/documents/{personal_id}/report", headers=admin_headers
        ).status_code
        == 404
    )

    # Alice still owns and can read her personal document after joining.
    assert (
        client.get(f"/api/documents/{personal_id}", headers=alice_headers).status_code
        == 200
    )

    # An identical company upload creates a separate company document and never
    # annexes Alice's personal copy.
    company_copy = _upload(client, admin_headers, filename="company-divorce.txt")
    assert company_copy.status_code == 201, company_copy.text
    company_doc_id = company_copy.json()["id"]
    assert company_doc_id != personal_id

    with SessionLocal() as db:
        assert db.get(Document, personal_id).company_id is None
        assert db.get(Document, company_doc_id).company_id == company_id

    admin_reports = client.get("/api/company/audit-reports", headers=admin_headers)
    assert admin_reports.json()["total"] == 1
    assert admin_reports.json()["items"][0]["document_id"] == company_doc_id


def test_leaving_company_revokes_company_document_access(client: TestClient):
    password = "leaving-company-pass-123"
    alice_id, alice_headers = _make_user(
        "individual", "alice@example.com", password=password
    )
    personal = _upload(client, alice_headers, filename="alice-personal.txt")
    assert personal.status_code == 201, personal.text
    personal_id = personal.json()["id"]

    company_id = _make_company("Departure Legal")
    _, admin_headers = _make_user(
        "company",
        "admin@departure.example.com",
        company_id=company_id,
        company_role="COMPANY_ADMIN",
    )
    invitation = client.post(
        "/api/company/team/invitations",
        headers=admin_headers,
        json={"email": "alice@example.com", "company_role": "MEMBER"},
    )
    assert invitation.status_code == 201, invitation.text
    accepted = client.post(
        "/api/company/invitations/accept",
        json={
            "token": invitation.json()["development_invitation_token"],
            "password": password,
        },
    )
    assert accepted.status_code == 200, accepted.text

    admin_doc = _upload(client, admin_headers, filename="admin-company.txt")
    assert admin_doc.status_code == 201, admin_doc.text
    alice_doc = _upload(
        client, alice_headers, filename="alice-company.txt", content=ALT_CONTRACT
    )
    assert alice_doc.status_code == 201, alice_doc.text
    alice_company_doc_id = alice_doc.json()["id"]
    with SessionLocal() as db:
        assert db.get(Document, alice_company_doc_id).company_id == company_id

    removed = client.delete(
        f"/api/company/team/members/{alice_id}", headers=admin_headers
    )
    assert removed.status_code == 204, removed.text

    # Company documents become invisible to the former member, including the
    # one she uploaded herself.
    assert (
        client.get(
            f"/api/documents/{alice_company_doc_id}", headers=alice_headers
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/documents/{admin_doc.json()['id']}", headers=alice_headers
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/documents/{alice_company_doc_id}", headers=alice_headers
        ).status_code
        == 404
    )

    # Her personal document survives and remains the only visible one.
    assert (
        client.get(f"/api/documents/{personal_id}", headers=alice_headers).status_code
        == 200
    )
    listed = client.get("/api/documents", headers=alice_headers).json()
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == personal_id
    stats = client.get("/api/stats/overview", headers=alice_headers).json()
    assert stats["total_documents"] == 1

    # The company workspace still sees both company documents.
    reports = client.get("/api/company/audit-reports", headers=admin_headers).json()
    assert reports["total"] == 2
    assert {item["document_id"] for item in reports["items"]} == {
        admin_doc.json()["id"],
        alice_company_doc_id,
    }


def test_delete_all_is_scoped_to_the_callers_tenant(client: TestClient):
    password = "delete-scope-pass-123"
    alice_id, alice_headers = _make_user(
        "individual", "alice@example.com", password=password
    )
    personal = _upload(client, alice_headers, filename="alice-personal.txt")
    assert personal.status_code == 201, personal.text
    personal_id = personal.json()["id"]

    company_id = _make_company("Scoped Deletions Ltd")
    _, admin_headers = _make_user(
        "company",
        "admin@scoped.example.com",
        company_id=company_id,
        company_role="COMPANY_ADMIN",
    )
    invitation = client.post(
        "/api/company/team/invitations",
        headers=admin_headers,
        json={"email": "alice@example.com", "company_role": "MEMBER"},
    )
    assert invitation.status_code == 201, invitation.text
    accepted = client.post(
        "/api/company/invitations/accept",
        json={
            "token": invitation.json()["development_invitation_token"],
            "password": password,
        },
    )
    assert accepted.status_code == 200, accepted.text

    company_doc = _upload(client, admin_headers, filename="company-doc.txt")
    assert company_doc.status_code == 201, company_doc.text
    company_doc_id = company_doc.json()["id"]

    # A regular member's bulk delete only removes their own personal documents,
    # never the company workspace they now belong to.
    deleted = client.delete("/api/documents", headers=alice_headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 1

    with SessionLocal() as db:
        assert db.get(Document, personal_id) is None
        company_row = db.get(Document, company_doc_id)
        assert company_row is not None
        assert company_row.company_id == company_id
        assert company_row.user_id != alice_id

    # A manager's bulk delete is scoped to the company workspace.
    deleted = client.delete("/api/documents", headers=admin_headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 1
    assert _document_count(company_id=company_id) == 0


def test_duplicate_upload_within_same_company_is_rejected(client: TestClient):
    company_id = _make_company("Gamma Works")
    _, admin_headers = _make_user(
        "company",
        "admin@gamma.example.com",
        company_id=company_id,
        company_role="COMPANY_ADMIN",
    )
    _, member_headers = _make_user(
        "company",
        "member@gamma.example.com",
        company_id=company_id,
        company_role="MEMBER",
    )

    first = _upload(client, admin_headers, filename="gamma-template.txt")
    assert first.status_code == 201, first.text
    first_id = first.json()["id"]

    duplicate = _upload(client, member_headers, filename="gamma-template.txt")
    assert duplicate.status_code == 409
    error = duplicate.json()["error"]
    assert error["code"] == "duplicate_document"
    assert error["details"]["document_id"] == first_id

    assert _document_count(company_id=company_id) == 1


def test_unauthorized_document_and_report_access_is_hidden(client: TestClient):
    _, owner_headers = _make_user("individual", "owner@example.com")
    _, stranger_headers = _make_user("individual", "stranger@example.com")

    owned = _upload(client, owner_headers, filename="owner-contract.txt")
    assert owned.status_code == 201, owned.text
    owned_doc = owned.json()

    assert (
        client.get(
            f"/api/documents/{owned_doc['id']}", headers=stranger_headers
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/documents/{owned_doc['id']}/report", headers=stranger_headers
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/analyses/{owned_doc['analysis']['id']}", headers=stranger_headers
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/documents/{owned_doc['id']}", headers=stranger_headers
        ).status_code
        == 404
    )

    company_a = _make_company("Delta Corp")
    company_b = _make_company("Epsilon Corp")
    _, admin_a = _make_user(
        "company",
        "admin@delta.example.com",
        company_id=company_a,
        company_role="COMPANY_ADMIN",
    )
    _, admin_b = _make_user(
        "company",
        "admin@epsilon.example.com",
        company_id=company_b,
        company_role="COMPANY_ADMIN",
    )

    company_doc = _upload(client, admin_a, filename="delta-secret.txt")
    assert company_doc.status_code == 201, company_doc.text
    company_doc_id = company_doc.json()["id"]

    assert (
        client.get(f"/api/documents/{company_doc_id}", headers=admin_b).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/documents/{company_doc_id}/report", headers=admin_b
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/company/audit-reports/{company_doc_id}", headers=admin_b
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/company/audit-reports/{company_doc_id}/report", headers=admin_b
        ).status_code
        == 404
    )

    # Individuals never gain access to company audit workspaces.
    assert (
        client.get("/api/company/audit-reports", headers=stranger_headers).status_code
        == 403
    )
    assert client.get("/api/company/audit-reports", headers=admin_b).json()["total"] == 0

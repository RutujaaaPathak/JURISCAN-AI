"""Corporate document ownership, legal-hold and retention regressions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_company(name: str, *, retention_days: int | None = None) -> int:
    with SessionLocal() as db:
        company = Company(name=name, retention_days=retention_days)
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
) -> tuple[int, dict[str, str]]:
    with SessionLocal() as db:
        user = User(
            email=email,
            username=email,
            full_name=email.split("@")[0].title(),
            role=role,
            company_id=company_id,
            company_role=company_role,
            hashed_password=hash_password("retention-test-pass-123"),
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


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def test_deleting_employee_account_retains_company_documents_and_encryption(
    client: TestClient,
):
    company_id = _make_company("Continuity Holdings")
    _, admin_headers = _make_user(
        "company",
        "admin@continuity.example.com",
        company_id=company_id,
        company_role="COMPANY_ADMIN",
    )
    employee_id, employee_headers = _make_user(
        "company",
        "employee@continuity.example.com",
        company_id=company_id,
        company_role="MEMBER",
    )

    uploaded = _upload(client, employee_headers, filename="employee-nda.txt")
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["id"]

    with SessionLocal() as db:
        document = db.get(Document, document_id)
        assert document is not None
        assert document.user_id == employee_id
        assert document.company_id == company_id
        assert document.encryption_version == 1
        stored_path = document.storage_path
        wrapped_dek = document.dek_wrapped
        content_hash = document.content_hash
    assert stored_path is not None
    assert Path(stored_path).exists()

    # This is the account-deletion path: the company record must survive and
    # only the uploader reference is nulled.
    with SessionLocal() as db:
        db.delete(db.get(User, employee_id))
        db.commit()

    with SessionLocal() as db:
        document = db.get(Document, document_id)
        assert document is not None
        assert document.user_id is None
        assert document.company_id == company_id
        assert document.dek_wrapped == wrapped_dek
        assert document.content_hash == content_hash
        assert document.storage_path == stored_path
        assert len(document.clauses) > 0
        assert len(document.analyses) > 0
    assert Path(stored_path).exists()

    # Another workspace administrator can still read and decrypt the document.
    detail = client.get(f"/api/documents/{document_id}", headers=admin_headers)
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert "indemnify" in payload["text_content"].lower()
    assert payload["clauses"]

    reports = client.get("/api/company/audit-reports", headers=admin_headers)
    assert reports.status_code == 200, reports.text
    assert document_id in {
        item["document_id"] for item in reports.json()["items"]
    }


def test_account_deletion_cannot_orphan_personal_documents(client: TestClient):
    user_id, headers = _make_user("individual", "orphan@example.com")
    uploaded = _upload(client, headers, filename="personal-nda.txt")
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["id"]

    with SessionLocal() as db:
        with pytest.raises(IntegrityError):
            db.delete(db.get(User, user_id))
            db.commit()
        db.rollback()

    with SessionLocal() as db:
        assert db.get(User, user_id) is not None
        document = db.get(Document, document_id)
        assert document is not None
        assert document.user_id == user_id


def test_company_deletion_is_restricted_while_documents_exist(client: TestClient):
    company_id = _make_company("Protected Company")
    _, admin_headers = _make_user(
        "company",
        "admin@protected.example.com",
        company_id=company_id,
        company_role="COMPANY_ADMIN",
    )
    uploaded = _upload(client, admin_headers, filename="protected-contract.txt")
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["id"]

    with SessionLocal() as db:
        with pytest.raises(IntegrityError):
            db.delete(db.get(Company, company_id))
            db.commit()
        db.rollback()

    with SessionLocal() as db:
        assert db.get(Company, company_id) is not None
        document = db.get(Document, document_id)
        assert document is not None
        assert document.company_id == company_id
        assert db.get(User, document.user_id).company_id == company_id


def test_only_company_admins_and_managers_can_delete_company_documents(
    client: TestClient,
):
    company_id = _make_company("Delete Authority Ltd")
    _, admin_headers = _make_user(
        "company",
        "admin@authority.example.com",
        company_id=company_id,
        company_role="COMPANY_ADMIN",
    )
    _, manager_headers = _make_user(
        "company",
        "manager@authority.example.com",
        company_id=company_id,
        company_role="MANAGER",
    )
    _, member_headers = _make_user(
        "company",
        "member@authority.example.com",
        company_id=company_id,
        company_role="MEMBER",
    )

    member_doc = _upload(client, member_headers, filename="member-upload.txt")
    assert member_doc.status_code == 201, member_doc.text
    member_doc_id = member_doc.json()["id"]

    denied = client.delete(
        f"/api/documents/{member_doc_id}", headers=member_headers
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["error"]["code"] == "document_delete_forbidden"

    with SessionLocal() as db:
        assert db.get(Document, member_doc_id) is not None

    admin_deleted = client.delete(
        f"/api/documents/{member_doc_id}", headers=admin_headers
    )
    assert admin_deleted.status_code == 204, admin_deleted.text

    manager_doc = _upload(
        client,
        member_headers,
        filename="manager-delete.txt",
        content=SAMPLE_CONTRACT + b"\n4. Audit\nAnnual audit required.\n",
    )
    assert manager_doc.status_code == 201, manager_doc.text
    manager_deleted = client.delete(
        f"/api/documents/{manager_doc.json()['id']}", headers=manager_headers
    )
    assert manager_deleted.status_code == 204, manager_deleted.text


def test_legal_hold_blocks_single_and_bulk_deletion(client: TestClient):
    company_id = _make_company("Legal Hold Corp")
    _, admin_headers = _make_user(
        "company",
        "admin@hold.example.com",
        company_id=company_id,
        company_role="COMPANY_ADMIN",
    )
    held = _upload(client, admin_headers, filename="held-contract.txt")
    assert held.status_code == 201, held.text
    held_id = held.json()["id"]
    other = _upload(
        client,
        admin_headers,
        filename="other-contract.txt",
        content=SAMPLE_CONTRACT + b"\n4. Audit\nAnnual audit required.\n",
    )
    assert other.status_code == 201, other.text
    other_id = other.json()["id"]

    with SessionLocal() as db:
        document = db.get(Document, held_id)
        document.legal_hold = True
        held_path = document.storage_path
        db.commit()

    single = client.delete(f"/api/documents/{held_id}", headers=admin_headers)
    assert single.status_code == 409, single.text
    assert single.json()["error"]["code"] == "legal_hold_active"

    bulk = client.delete("/api/documents", headers=admin_headers)
    assert bulk.status_code == 409, bulk.text
    assert bulk.json()["error"]["code"] == "legal_hold_active"

    with SessionLocal() as db:
        assert db.get(Document, held_id) is not None
        assert db.get(Document, other_id) is not None
    assert Path(held_path).exists()

    listed = client.get("/api/documents", headers=admin_headers).json()
    held_summary = next(
        item for item in listed["items"] if item["id"] == held_id
    )
    assert held_summary["legal_hold"] is True

    with SessionLocal() as db:
        db.get(Document, held_id).legal_hold = False
        db.commit()

    released = client.delete(f"/api/documents/{held_id}", headers=admin_headers)
    assert released.status_code == 204, released.text


def test_unexpired_retention_blocks_deletion_until_expiry(client: TestClient):
    company_id = _make_company("Retention Corp")
    _, admin_headers = _make_user(
        "company",
        "admin@retention.example.com",
        company_id=company_id,
        company_role="COMPANY_ADMIN",
    )
    retained = _upload(client, admin_headers, filename="retained-contract.txt")
    assert retained.status_code == 201, retained.text
    retained_id = retained.json()["id"]
    other = _upload(
        client,
        admin_headers,
        filename="expired-contract.txt",
        content=SAMPLE_CONTRACT + b"\n4. Audit\nAnnual audit required.\n",
    )
    assert other.status_code == 201, other.text
    other_id = other.json()["id"]

    with SessionLocal() as db:
        document = db.get(Document, retained_id)
        document.retention_until = datetime.now(timezone.utc) + timedelta(days=30)
        retained_path = document.storage_path
        db.commit()

    single = client.delete(
        f"/api/documents/{retained_id}", headers=admin_headers
    )
    assert single.status_code == 409, single.text
    error = single.json()["error"]
    assert error["code"] == "retention_active"
    assert error["details"]["document_id"] == retained_id

    bulk = client.delete("/api/documents", headers=admin_headers)
    assert bulk.status_code == 409, bulk.text
    assert bulk.json()["error"]["code"] == "retention_active"

    with SessionLocal() as db:
        assert db.get(Document, retained_id) is not None
        assert db.get(Document, other_id) is not None
    assert Path(retained_path).exists()

    with SessionLocal() as db:
        db.get(Document, retained_id).retention_until = (
            datetime.now(timezone.utc) - timedelta(days=1)
        )
        db.commit()

    expired = client.delete(
        f"/api/documents/{retained_id}", headers=admin_headers
    )
    assert expired.status_code == 204, expired.text

    remaining = client.delete("/api/documents", headers=admin_headers)
    assert remaining.status_code == 200, remaining.text
    assert remaining.json()["deleted"] == 1


def test_new_uploads_apply_company_and_system_retention_defaults(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "document_retention_days", 30)
    before = datetime.now(timezone.utc)

    _, personal_headers = _make_user("individual", "retention@example.com")
    personal = _upload(client, personal_headers, filename="personal-retention.txt")
    assert personal.status_code == 201, personal.text
    personal_until = _utc(personal.json()["retention_until"])
    assert timedelta(days=29, hours=23) < personal_until - before < timedelta(
        days=30, hours=1
    )

    company_id = _make_company("Ten Day Company", retention_days=10)
    _, company_headers = _make_user(
        "company",
        "admin@tenday.example.com",
        company_id=company_id,
        company_role="COMPANY_ADMIN",
    )
    company_doc = _upload(
        client, company_headers, filename="company-retention.txt"
    )
    assert company_doc.status_code == 201, company_doc.text
    company_until = _utc(company_doc.json()["retention_until"])
    assert timedelta(days=9, hours=23) < company_until - before < timedelta(
        days=10, hours=1
    )

    indefinite_company = _make_company("Indefinite Company", retention_days=0)
    _, indefinite_headers = _make_user(
        "company",
        "admin@indefinite.example.com",
        company_id=indefinite_company,
        company_role="COMPANY_ADMIN",
    )
    indefinite = _upload(
        client, indefinite_headers, filename="indefinite-retention.txt"
    )
    assert indefinite.status_code == 201, indefinite.text
    assert indefinite.json()["retention_until"] is None

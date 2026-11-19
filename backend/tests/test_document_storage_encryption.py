"""End-to-end coverage for encrypted document storage and decryption."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import settings
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models import Clause, Document, User
from app.services import processing as processing_module
from app.services.document_content import (
    clause_plaintext,
    document_dek_if_encrypted,
    document_file_bytes,
    document_plaintext,
)
from app.services.document_crypto import (
    DocumentEncryptionError,
    is_encrypted_text,
)
from app.services.storage import upload_dir

MARKER = "ENCRYPTED-MARKER-42"

CONTRACT = f"""1. Indemnity
The Supplier {MARKER} shall indemnify the Customer against all losses without cap.

2. Payment
Payment shall be due within thirty (30) days of a valid invoice.
"""


def _create_user(email: str = "encryption@example.com") -> tuple[int, str]:
    with SessionLocal() as db:
        user = User(
            email=email,
            username=email.split("@")[0],
            full_name="Encryption User",
            role="individual",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    token = create_access_token(
        user_id, secret=settings.secret_key, ttl_seconds=3600
    )
    return user_id, token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _upload(client, token: str | None = None, **data):
    headers = _auth(token) if token else None
    return client.post(
        "/api/documents",
        files={"file": ("encrypted-contract.txt", CONTRACT.encode("utf-8"), "text/plain")},
        data=data or None,
        headers=headers,
    )


def test_new_upload_is_encrypted_at_rest_and_decrypted_for_the_owner(client):
    _, token = _create_user()
    response = _upload(client, token, title="Encrypted Contract")
    assert response.status_code == 201, response.text
    document_id = response.json()["id"]

    with SessionLocal() as db:
        document = db.get(Document, document_id)
        assert document is not None
        assert document.encryption_version == 1
        assert document.encryption_key_id
        assert document.dek_wrapped
        assert is_encrypted_text(document.text_content)
        assert MARKER not in document.text_content
        assert document_plaintext(document).count(MARKER) == 1

        clauses = list(
            db.scalars(
                select(Clause)
                .where(Clause.document_id == document_id)
                .order_by(Clause.clause_number)
            ).all()
        )
        assert clauses
        for clause in clauses:
            assert is_encrypted_text(clause.text)
            assert MARKER not in clause.text
            if clause.normalized_text is not None:
                assert is_encrypted_text(clause.normalized_text)
        assert any(
            MARKER in (clause_plaintext(document, clause) or "")
            for clause in clauses
        )

        stored = Path(document.storage_path)
        envelope = stored.read_bytes()
        assert stored.suffix == ".jse"
        assert envelope.startswith(b"JSC1")
        assert MARKER.encode("utf-8") not in envelope
        assert document_file_bytes(document) == CONTRACT.encode("utf-8")

    detail = client.get(f"/api/documents/{document_id}", headers=_auth(token))
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert MARKER in body["text_content"]
    assert any(MARKER in clause["text"] for clause in body["clauses"])
    assert "storage_path" not in body


def test_encrypted_clause_text_is_used_for_pdf_reports(client):
    from io import BytesIO

    from pypdf import PdfReader

    _, token = _create_user("report-encryption@example.com")
    upload = _upload(client, token, title="Encrypted Report")
    assert upload.status_code == 201, upload.text

    report = client.get(
        f"/api/documents/{upload.json()['id']}/report", headers=_auth(token)
    )
    assert report.status_code == 200, report.text
    assert report.content.startswith(b"%PDF")

    reader = PdfReader(BytesIO(report.content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert MARKER in text


def test_tampered_text_fails_closed_without_partial_content(client):
    _, token = _create_user("tamper@example.com")
    response = _upload(client, token)
    assert response.status_code == 201, response.text
    document_id = response.json()["id"]

    with SessionLocal() as db:
        document = db.get(Document, document_id)
        envelope = document.text_content
        replacement = "A" if envelope[12] != "A" else "B"
        document.text_content = envelope[:12] + replacement + envelope[13:]
        db.commit()

    tampered = client.get(f"/api/documents/{document_id}", headers=_auth(token))
    assert tampered.status_code == 500
    body = tampered.json()
    assert body["error"]["code"] == "document_decryption_failed"
    assert MARKER not in tampered.text
    assert "JSE1" not in tampered.text


def test_tampered_stored_file_is_rejected(client):
    _, token = _create_user("file-tamper@example.com")
    response = _upload(client, token)
    assert response.status_code == 201, response.text
    document_id = response.json()["id"]

    with SessionLocal() as db:
        document = db.get(Document, document_id)
        stored = Path(document.storage_path)
        envelope = bytearray(stored.read_bytes())
        envelope[-1] ^= 0x01
        stored.write_bytes(envelope)
        with pytest.raises(DocumentEncryptionError):
            document_file_bytes(document)


def test_force_retry_replaces_file_and_rotates_the_document_key(client):
    _, token = _create_user("retry-encryption@example.com")
    first = _upload(client, token)
    assert first.status_code == 201, first.text
    document_id = first.json()["id"]

    with SessionLocal() as db:
        document = db.get(Document, document_id)
        first_path = Path(document.storage_path)
        first_wrapped = document.dek_wrapped
        assert first_path.is_file()

    second = _upload(client, token, force="true")
    assert second.status_code == 201, second.text
    assert second.json()["id"] == document_id

    with SessionLocal() as db:
        document = db.get(Document, document_id)
        second_path = Path(document.storage_path)
        assert document.encryption_version == 1
        assert document.dek_wrapped and document.dek_wrapped != first_wrapped
        assert second_path != first_path
        assert not first_path.exists()
        assert second_path.is_file()
        assert document_file_bytes(document) == CONTRACT.encode("utf-8")
        assert MARKER in document_plaintext(document)

    detail = client.get(f"/api/documents/{document_id}", headers=_auth(token))
    assert detail.status_code == 200, detail.text
    assert MARKER in detail.json()["text_content"]


def test_failed_processing_after_save_removes_the_encrypted_file(client, monkeypatch):
    before = set(upload_dir().iterdir())
    saved_paths: list[Path] = []
    real_save = processing_module.save_upload

    def tracked_save(*args, **kwargs):
        path = real_save(*args, **kwargs)
        saved_paths.append(Path(path))
        return path

    def fail_persist(*args, **kwargs):
        raise RuntimeError("simulated failure after the file was written")

    monkeypatch.setattr(processing_module, "save_upload", tracked_save)
    monkeypatch.setattr(processing_module, "persist_clauses", fail_persist)

    response = _upload(client)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "processing_failed"
    assert saved_paths
    assert all(not path.exists() for path in saved_paths)
    assert set(upload_dir().iterdir()) == before

    with SessionLocal() as db:
        document = db.scalar(select(Document))
        assert document is not None
        assert document.status == "FAILED"
        assert document.storage_path is None
        assert document.text_content is None


def test_unauthorized_users_get_404_without_ciphertext(client):
    owner_id, owner_token = _create_user("encrypted-owner@example.com")
    _, stranger_token = _create_user("encrypted-stranger@example.com")
    assert owner_id

    upload = _upload(client, owner_token)
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]

    with SessionLocal() as db:
        envelope = db.get(Document, document_id).text_content

    for headers in (None, _auth(stranger_token)):
        response = client.get(f"/api/documents/{document_id}", headers=headers)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "document_not_found"
        assert envelope not in response.text
        assert MARKER not in response.text


def test_version_zero_rows_keep_explicit_legacy_plaintext_reads(client):
    user_id, token = _create_user("legacy-plaintext@example.com")
    legacy_text = "1. Legacy\nThis row predates encryption and remains readable."

    with SessionLocal() as db:
        document = Document(
            user_id=user_id,
            title="Legacy Contract",
            filename="legacy.txt",
            file_type="txt",
            status="PROCESSED",
            text_content=legacy_text,
            encryption_version=0,
        )
        db.add(document)
        db.flush()
        db.add(
            Clause(
                document_id=document.id,
                clause_number=1,
                heading="1. Legacy",
                text=legacy_text,
                start_offset=0,
                end_offset=len(legacy_text),
                level=1,
            )
        )
        db.commit()
        document_id = document.id

    with SessionLocal() as db:
        document = db.get(Document, document_id)
        assert document_dek_if_encrypted(document) is None
        assert document_plaintext(document) == legacy_text
        assert clause_plaintext(document, document.clauses[0]) == legacy_text

    detail = client.get(f"/api/documents/{document_id}", headers=_auth(token))
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["text_content"] == legacy_text
    assert body["clauses"][0]["text"] == legacy_text

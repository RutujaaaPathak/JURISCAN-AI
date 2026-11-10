from datetime import datetime, timedelta, timezone

import pytest

from app.core.database import SessionLocal
from app.core.exceptions import ValidationFailed
from app.models import Document, User
from app.services import processing as processing_module
from app.services.extraction import validate_and_extract as real_validate_and_extract
from app.services.processing import (
    recover_stale_documents,
    recover_stale_documents_in_new_session,
    run_processing,
)


def _create_user(session, email: str) -> User:
    user = User(email=email, username=email.split("@")[0], full_name="Test User")
    session.add(user)
    session.flush()
    return user


def _create_document(
    session,
    user: User,
    *,
    updated_at: datetime,
    status: str = "PROCESSING",
) -> int:
    document = Document(
        user_id=user.id,
        title="Stale document",
        filename="stale.txt",
        file_type="txt",
        status=status,
        updated_at=updated_at,
    )
    session.add(document)
    session.commit()
    return document.id


def test_recover_stale_documents_marks_timed_out_processing_as_failed():
    stale = datetime.now(timezone.utc) - timedelta(hours=1)
    with SessionLocal() as session:
        user = _create_user(session, "stale@example.com")
        document_id = _create_document(session, user, updated_at=stale)

    with SessionLocal() as session:
        assert recover_stale_documents(session, stale_seconds=900) == 1

    with SessionLocal() as session:
        document = session.get(Document, document_id)
        assert document.status == "FAILED"
        assert document.error_message


def test_recover_stale_documents_leaves_recent_processing_untouched():
    with SessionLocal() as session:
        user = _create_user(session, "fresh@example.com")
        document_id = _create_document(
            session, user, updated_at=datetime.now(timezone.utc)
        )

    with SessionLocal() as session:
        assert recover_stale_documents(session, stale_seconds=900) == 0

    with SessionLocal() as session:
        assert session.get(Document, document_id).status == "PROCESSING"


def test_recover_stale_documents_never_overwrites_processed_rows():
    stale = datetime.now(timezone.utc) - timedelta(hours=1)
    with SessionLocal() as session:
        user = _create_user(session, "processed@example.com")
        document_id = _create_document(
            session, user, updated_at=stale, status="PROCESSED"
        )

    with SessionLocal() as session:
        assert recover_stale_documents(session, stale_seconds=900) == 0

    with SessionLocal() as session:
        assert session.get(Document, document_id).status == "PROCESSED"


def test_recover_stale_documents_in_new_session_recovers_stale_row():
    stale = datetime.now(timezone.utc) - timedelta(hours=1)
    with SessionLocal() as session:
        user = _create_user(session, "new-session@example.com")
        document_id = _create_document(session, user, updated_at=stale)

    assert recover_stale_documents_in_new_session() == 1

    with SessionLocal() as session:
        assert session.get(Document, document_id).status == "FAILED"


def test_late_worker_cannot_overwrite_recovered_failed_state(monkeypatch):
    text = (
        b"1. Indemnity\n"
        b"The Supplier shall indemnify the Customer for all losses.\n\n"
        b"2. Payment\n"
        b"Payment shall be due within thirty (30) days.\n"
    )
    with SessionLocal() as session:
        user = _create_user(session, "late-worker@example.com")
        document_id = _create_document(
            session,
            user,
            updated_at=datetime.now(timezone.utc),
        )

    def recover_during_extraction(data, filename, content_type, max_size_bytes):
        extracted = real_validate_and_extract(
            data, filename, content_type, max_size_bytes
        )
        with SessionLocal() as other:
            document = other.get(Document, document_id)
            document.status = "FAILED"
            document.error_message = "Recovered while OCR was running."
            other.commit()
        return extracted

    monkeypatch.setattr(
        processing_module,
        "validate_and_extract",
        recover_during_extraction,
    )

    with SessionLocal() as session:
        document = session.get(Document, document_id)
        with pytest.raises(ValidationFailed) as exc:
            run_processing(
                session,
                document,
                data=text,
                filename="late.txt",
                content_type="text/plain",
                title="Late worker",
                max_size_bytes=1024 * 1024,
            )
        assert exc.value.code == "processing_interrupted"

    with SessionLocal() as session:
        document = session.get(Document, document_id)
        assert document.status == "FAILED"
        assert "interrupted" in (document.error_message or "").lower()

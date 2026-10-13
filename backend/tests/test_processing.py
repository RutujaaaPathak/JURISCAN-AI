from datetime import datetime, timedelta, timezone

from app.core.database import SessionLocal
from app.models import Document, User
from app.services.processing import recover_stale_documents


def _create_user(session, email: str) -> User:
    user = User(email=email, username=email.split("@")[0], full_name="Test User")
    session.add(user)
    session.flush()
    return user


def _create_document(session, user: User, *, updated_at: datetime) -> int:
    document = Document(
        user_id=user.id,
        title="Stale document",
        filename="stale.txt",
        file_type="txt",
        status="PROCESSING",
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

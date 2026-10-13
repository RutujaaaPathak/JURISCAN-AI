from sqlalchemy.exc import IntegrityError

from app.core.database import Base, SessionLocal, engine
from app.models.document import Document
from app.models.user import User


def _new_user(session) -> User:
    user = User(
        email="audit@example.com",
        username="audit_user",
        full_name="Audit User",
    )
    session.add(user)
    session.flush()
    return user


def test_user_crud():
    session = SessionLocal()
    try:
        user = _new_user(session)
        assert user.id is not None

        fetched = session.query(User).filter_by(username="audit_user").one()
        assert fetched.email == "audit@example.com"

        session.delete(fetched)
        session.commit()
        assert session.query(User).filter_by(username="audit_user").count() == 0
    finally:
        session.close()


def test_document_relationship_cascade():
    session = SessionLocal()
    try:
        user = _new_user(session)
        doc = Document(
            user_id=user.id,
            title="NDA",
            filename="nda.pdf",
            file_type="pdf",
            status="PENDING",
        )
        session.add(doc)
        session.commit()
        assert doc.id is not None

        fresh = session.query(Document).filter_by(filename="nda.pdf").one()
        assert fresh.user.username == "audit_user"

        session.delete(fresh)
        session.commit()
        assert session.query(Document).filter_by(filename="nda.pdf").count() == 0
    finally:
        session.close()


def test_document_status_check_constraint():
    session = SessionLocal()
    try:
        user = _new_user(session)
        doc = Document(
            user_id=user.id,
            title="Bad",
            filename="bad.txt",
            file_type="txt",
            status="NOT_A_STATUS",
        )
        session.add(doc)
        try:
            session.commit()
            raise AssertionError("Check constraint not enforced")
        except IntegrityError:
            session.rollback()
    finally:
        session.close()


def test_get_db_dependency_yields_session():
    from sqlalchemy import text

    from app.core.database import get_db

    gen = get_db()
    session = next(gen)
    try:
        assert session is not None
        assert session.execute(text("SELECT 1")).scalar() == 1
    finally:
        gen.close()


def test_all_tables_registered():
    assert set(Base.metadata.tables.keys()) == {
        "users",
        "documents",
        "clauses",
        "analyses",
        "risk_findings",
    }
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import Base, engine, get_db
from app.models.analysis import Analysis
from app.models.document import Document
from app.models.risk_finding import RiskFinding
from app.models.user import User


def test_user_crud():
    with Session(engine) as db:
        user = User(email="test@example.com", username="testuser")
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.id is not None
        assert user.is_active is True
        assert user.created_at is not None
        assert user.updated_at is not None

        # Read
        fetched = db.get(User, user.id)
        assert fetched is not None
        assert fetched.username == "testuser"

        # Update
        user.username = "updateduser"
        db.commit()
        db.refresh(user)
        assert user.username == "updateduser"

        # Delete
        db.delete(user)
        db.commit()
        assert db.get(User, user.id) is None


def test_document_relationship_cascade():
    with Session(engine) as db:
        user = User(email="author@example.com", username="author")
        db.add(user)
        db.commit()

        doc = Document(
            user_id=user.id,
            title="NDA Agreement",
            filename="nda.pdf",
            file_type="pdf",
        )
        db.add(doc)
        db.commit()

        assert len(user.documents) == 1
        assert user.documents[0].title == "NDA Agreement"

        # Cascade delete
        db.delete(user)
        db.commit()
        assert db.get(Document, doc.id) is None


def test_document_status_check_constraint():
    with Session(engine) as db:
        user = User(email="u@example.com", username="u")
        db.add(user)
        db.commit()

        # In SQLite, CHECK constraints are supported when enabled.
        # Direct session writes with invalid status will fail validation.
        doc = Document(
            user_id=user.id,
            title="Bad",
            filename="bad.pdf",
            file_type="pdf",
            status="INVALID_STATUS",
        )
        db.add(doc)
        with pytest.raises(IntegrityError):
            db.commit()


def test_get_db_dependency_yields_session():
    # Verify the get_db generator yields a working session and cleans up.
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
        "lawyer_profiles",
        "cases",
        "case_documents",
        "case_decisions",
        "case_activities",
        "case_notes",
        "case_messages",
        "case_clarification_messages",
        "case_fee_proposals",
        "case_appointments",
        "calls",
        "user_settings",
    }

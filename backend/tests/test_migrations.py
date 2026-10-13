"""Tests for Alembic database migrations.

Covers:
- Full migration upgrade to head
- Downgrade to preceding revision (b7e2f1a9c3d4) and subsequent upgrade back to head
- Verification of clause hierarchy columns (label, level, parent_id)
- Verification of data preservation across migration upgrades
"""

import os
import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


@pytest.fixture
def migration_db():
    temp_dir = tempfile.mkdtemp()
    db_file = Path(temp_dir) / "test_migration.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    backend_dir = Path(__file__).resolve().parent.parent
    ini_path = backend_dir / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", db_url)

    yield cfg, db_url

    engine = create_engine(db_url)
    engine.dispose()
    try:
        if db_file.exists():
            db_file.unlink()
        Path(temp_dir).rmdir()
    except Exception:
        pass


def test_migration_upgrade_and_downgrade(migration_db):
    cfg, db_url = migration_db
    engine = create_engine(db_url)

    # 1. Upgrade from empty to head
    command.upgrade(cfg, "head")

    inspector = inspect(engine)
    columns = {col["name"]: col for col in inspector.get_columns("clauses")}
    assert "label" in columns
    assert "level" in columns
    assert "parent_id" in columns
    assert "start_offset" in columns
    assert "end_offset" in columns

    # 2. Downgrade to b7e2f1a9c3d4 (prior to clause hierarchy)
    command.downgrade(cfg, "b7e2f1a9c3d4")
    engine.dispose()
    engine = create_engine(db_url)
    inspector = inspect(engine)
    columns_down = {col["name"]: col for col in inspector.get_columns("clauses")}
    assert "label" not in columns_down
    assert "parent_id" not in columns_down

    # 3. Upgrade back to head
    command.upgrade(cfg, "head")
    engine.dispose()
    engine = create_engine(db_url)
    inspector = inspect(engine)
    columns_up = {col["name"]: col for col in inspector.get_columns("clauses")}
    assert "label" in columns_up
    assert "level" in columns_up
    assert "parent_id" in columns_up

    engine.dispose()


def test_migration_preserves_existing_data(migration_db):
    cfg, db_url = migration_db
    engine = create_engine(db_url)

    # 1. Upgrade up to b7e2f1a9c3d4 (prior to clause hierarchy)
    command.upgrade(cfg, "b7e2f1a9c3d4")

    # 2. Insert test user, document, and clause using pre-migration schema
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, username, is_active) "
                "VALUES (1, 'mig@example.com', 'miguser', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO documents (id, user_id, title, filename, file_type, status) "
                "VALUES (1, 1, 'Pre-migration Doc', 'doc.txt', 'txt', 'PROCESSED')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO clauses (id, document_id, clause_number, heading, text, start_offset, end_offset) "
                "VALUES (1, 1, 1, '1. Indemnity', 'Indemnity clause text', 0, 21)"
            )
        )

    # 3. Upgrade to head (runs c8d5e2f1a9b3)
    command.upgrade(cfg, "head")
    engine.dispose()
    engine = create_engine(db_url)

    # 4. Verify existing clause is preserved with default level 1 and null label/parent_id
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, clause_number, heading, text, level, label, parent_id FROM clauses WHERE id = 1")
        ).mappings().one()

        assert row["id"] == 1
        assert row["clause_number"] == 1
        assert row["heading"] == "1. Indemnity"
        assert row["text"] == "Indemnity clause text"
        assert row["level"] == 1
        assert row["label"] is None
        assert row["parent_id"] is None

    engine.dispose()

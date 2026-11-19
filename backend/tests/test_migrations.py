"""Tests for Alembic database migrations.

Covers:
- Full migration upgrade to head
- Downgrade to preceding revision (b7e2f1a9c3d4) and subsequent upgrade back to head
- Company workspace migration upgrade and downgrade
- Verification of clause hierarchy columns (label, level, parent_id)
- Verification of data preservation across migration upgrades
- Schema consistency check against Base.metadata (alembic check)
"""

import os
import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def migration_db():
    temp_dir = tempfile.mkdtemp()
    db_file = Path(temp_dir) / "test_migration.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    backend_dir = Path(__file__).resolve().parent.parent
    ini_path = backend_dir / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
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


def test_company_workspace_migration_upgrade_and_downgrade(migration_db):
    cfg, db_url = migration_db
    engine = create_engine(db_url)

    # 1. Upgrade to head
    command.upgrade(cfg, "head")

    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    assert "companies" in table_names
    assert "company_invitations" in table_names

    user_cols = {col["name"] for col in inspector.get_columns("users")}
    assert "company_id" in user_cols
    assert "company_role" in user_cols

    doc_cols = {col["name"] for col in inspector.get_columns("documents")}
    assert "company_id" in doc_cols

    # 2. Downgrade to prior revision (a4f7c2d9e1b8)
    command.downgrade(cfg, "a4f7c2d9e1b8")
    engine.dispose()
    engine = create_engine(db_url)
    inspector = inspect(engine)

    table_names_down = inspector.get_table_names()
    assert "companies" not in table_names_down
    assert "company_invitations" not in table_names_down

    user_cols_down = {col["name"] for col in inspector.get_columns("users")}
    assert "company_id" not in user_cols_down
    assert "company_role" not in user_cols_down

    doc_cols_down = {col["name"] for col in inspector.get_columns("documents")}
    assert "company_id" not in doc_cols_down

    # 3. Upgrade back to head
    command.upgrade(cfg, "head")
    engine.dispose()


def test_alembic_check_metadata_consistency(migration_db):
    cfg, _ = migration_db
    command.upgrade(cfg, "head")
    # Verify no model drift exists between Base.metadata and migrations
    command.check(cfg)


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


def _document_indexes(db_url: str) -> dict[str, dict]:
    engine = create_engine(db_url)
    try:
        return {ix["name"]: ix for ix in inspect(engine).get_indexes("documents")}
    finally:
        engine.dispose()


def test_content_hash_uniqueness_is_scoped_by_tenant(migration_db):
    cfg, db_url = migration_db

    command.upgrade(cfg, "head")

    indexes = _document_indexes(db_url)
    assert bool(indexes["ix_documents_content_hash"]["unique"]) is False
    assert bool(indexes["ix_documents_company_content_hash"]["unique"]) is True
    assert bool(indexes["ix_documents_user_personal_content_hash"]["unique"]) is True

    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, username, is_active) VALUES "
                "(1, 'a@example.com', 'a', 1), "
                "(2, 'b@example.com', 'b', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO companies (id, name) VALUES "
                "(1, 'Alpha'), (2, 'Beta')"
            )
        )
        # Identical content hashes are allowed across users and companies.
        conn.execute(
            text(
                "INSERT INTO documents "
                "(id, user_id, company_id, title, filename, file_type, status, content_hash) "
                "VALUES "
                "(1, 1, NULL, 'A personal', 'a.txt', 'txt', 'PROCESSED', 'shared-hash'), "
                "(2, 2, NULL, 'B personal', 'b.txt', 'txt', 'PROCESSED', 'shared-hash'), "
                "(3, 1, 1, 'A company', 'c.txt', 'txt', 'PROCESSED', 'shared-hash'), "
                "(4, 2, 2, 'B company', 'd.txt', 'txt', 'PROCESSED', 'shared-hash')"
            )
        )

    # Duplicates within the same personal workspace are still rejected.
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO documents "
                    "(id, user_id, company_id, title, filename, file_type, status, content_hash) "
                    "VALUES (5, 1, NULL, 'A personal copy', 'e.txt', 'txt', 'PROCESSED', 'shared-hash')"
                )
            )

    # Duplicates within the same company are still rejected.
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO documents "
                    "(id, user_id, company_id, title, filename, file_type, status, content_hash) "
                    "VALUES (5, 1, 1, 'A company copy', 'f.txt', 'txt', 'PROCESSED', 'shared-hash')"
                )
            )

    # Cross-tenant duplicates must be removed before a global unique index can
    # be restored, so clear them and verify the downgrade path.
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM documents"))
    engine.dispose()

    command.downgrade(cfg, "ea6ee676292e")

    indexes = _document_indexes(db_url)
    assert bool(indexes["ix_documents_content_hash"]["unique"]) is True
    assert "ix_documents_company_content_hash" not in indexes
    assert "ix_documents_user_personal_content_hash" not in indexes

    command.upgrade(cfg, "head")
    indexes = _document_indexes(db_url)
    assert bool(indexes["ix_documents_content_hash"]["unique"]) is False
    assert bool(indexes["ix_documents_company_content_hash"]["unique"]) is True


def test_migration_preserves_cross_tenant_duplicate_hashes(migration_db):
    cfg, db_url = migration_db

    command.upgrade(cfg, "ea6ee676292e")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        # Simulate a database whose legacy global unique index was removed or
        # bypassed before this migration runs.
        conn.execute(text("DROP INDEX ix_documents_content_hash"))
        conn.execute(
            text(
                "INSERT INTO users (id, email, username, is_active) VALUES "
                "(1, 'a@example.com', 'a', 1), "
                "(2, 'b@example.com', 'b', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO companies (id, name) VALUES "
                "(1, 'Alpha'), (2, 'Beta')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO documents "
                "(id, user_id, company_id, title, filename, file_type, status, content_hash) "
                "VALUES "
                "(1, 1, NULL, 'A personal', 'a.txt', 'txt', 'PROCESSED', 'shared-hash'), "
                "(2, 2, NULL, 'B personal', 'b.txt', 'txt', 'PROCESSED', 'shared-hash'), "
                "(3, 1, 1, 'A company', 'c.txt', 'txt', 'PROCESSED', 'shared-hash'), "
                "(4, 2, 2, 'B company', 'd.txt', 'txt', 'PROCESSED', 'shared-hash')"
            )
        )
    engine.dispose()

    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, user_id, company_id, content_hash FROM documents ORDER BY id")
        ).mappings().all()
    engine.dispose()

    assert len(rows) == 4
    assert {row["content_hash"] for row in rows} == {"shared-hash"}
    assert [row["company_id"] for row in rows] == [None, None, 1, 2]

    indexes = _document_indexes(db_url)
    assert bool(indexes["ix_documents_company_content_hash"]["unique"]) is True
    assert bool(indexes["ix_documents_user_personal_content_hash"]["unique"]) is True
    assert bool(indexes["ix_documents_content_hash"]["unique"]) is False


def test_migration_aborts_on_same_scope_duplicates(migration_db):
    cfg, db_url = migration_db

    command.upgrade(cfg, "ea6ee676292e")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("DROP INDEX ix_documents_content_hash"))
        conn.execute(
            text(
                "INSERT INTO users (id, email, username, is_active) "
                "VALUES (1, 'a@example.com', 'a', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO documents "
                "(id, user_id, company_id, title, filename, file_type, status, content_hash) "
                "VALUES "
                "(1, 1, NULL, 'A one', 'a.txt', 'txt', 'PROCESSED', 'duplicate-hash'), "
                "(2, 1, NULL, 'A two', 'b.txt', 'txt', 'PROCESSED', 'duplicate-hash')"
            )
        )
    engine.dispose()

    with pytest.raises(RuntimeError, match="duplicate content-hash"):
        command.upgrade(cfg, "head")

    # The migration aborts before changing the schema or touching the rows.
    engine = create_engine(db_url)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM documents")).scalar() == 2
    engine.dispose()

    indexes = _document_indexes(db_url)
    assert "ix_documents_company_content_hash" not in indexes
    assert "ix_documents_user_personal_content_hash" not in indexes


def test_token_version_migration_backfills_existing_users(migration_db):
    cfg, db_url = migration_db

    # 1. Upgrade to the revision immediately before token versioning.
    command.upgrade(cfg, "4a299ac7e3ed")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, username, is_active) VALUES "
                "(1, 'existing@example.com', 'existing', 1), "
                "(2, 'disabled@example.com', 'disabled', 0)"
            )
        )
    engine.dispose()

    # 2. Add token_version; existing active and disabled rows are backfilled.
    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    columns = {col["name"]: col for col in inspect(engine).get_columns("users")}
    assert "token_version" in columns
    assert columns["token_version"]["nullable"] is False
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, token_version FROM users ORDER BY id")
        ).mappings().all()
    engine.dispose()
    assert [row["token_version"] for row in rows] == [1, 1]

    # 3. Downgrade removes the column without touching user rows.
    command.downgrade(cfg, "4a299ac7e3ed")
    engine = create_engine(db_url)
    columns_down = {
        col["name"] for col in inspect(engine).get_columns("users")
    }
    assert "token_version" not in columns_down
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM users")).scalar() == 2
    engine.dispose()

    # 4. Re-upgrading safely restores the default for the existing users.
    command.upgrade(cfg, "head")
    engine = create_engine(db_url)
    with engine.connect() as conn:
        versions = conn.execute(
            text("SELECT token_version FROM users ORDER BY id")
        ).scalars().all()
    engine.dispose()
    assert versions == [1, 1]


def test_quality_intelligence_migration_upgrade_and_downgrade(migration_db):
    cfg, db_url = migration_db
    engine = create_engine(db_url)

    command.upgrade(cfg, "head")
    inspector = inspect(engine)
    clause_columns = {col["name"] for col in inspector.get_columns("clauses")}
    finding_columns = {
        col["name"] for col in inspector.get_columns("risk_findings")
    }

    assert {"normalized_text", "normalization_changes", "ocr_quality"} <= clause_columns
    assert {"requires_review", "review_reason", "ocr_confidence"} <= finding_columns

    engine.dispose()
    engine = create_engine(db_url)
    command.downgrade(cfg, "b7d9e1f3a5c6")
    inspector = inspect(engine)
    clause_columns = {col["name"] for col in inspector.get_columns("clauses")}
    finding_columns = {
        col["name"] for col in inspector.get_columns("risk_findings")
    }

    assert "normalized_text" not in clause_columns
    assert "ocr_quality" not in clause_columns
    assert "requires_review" not in finding_columns
    assert "ocr_confidence" not in finding_columns

    engine.dispose()
    engine = create_engine(db_url)
    command.upgrade(cfg, "head")
    inspector = inspect(engine)
    assert "requires_review" in {
        col["name"] for col in inspector.get_columns("risk_findings")
    }
    engine.dispose()


def test_document_encryption_metadata_migration_upgrade_and_downgrade(migration_db):
    cfg, db_url = migration_db

    command.upgrade(cfg, "f5a6b7c8d9e0")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, username, is_active) "
                "VALUES (1, 'encrypt@example.com', 'encrypt', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO documents (id, user_id, title, filename, file_type, status) "
                "VALUES (1, 1, 'Legacy Doc', 'legacy.txt', 'txt', 'PROCESSED')"
            )
        )
    engine.dispose()

    command.upgrade(cfg, "head")
    engine = create_engine(db_url)
    columns = {
        col["name"]: col for col in inspect(engine).get_columns("documents")
    }
    assert columns["encryption_version"]["nullable"] is False
    assert columns["encryption_key_id"]["nullable"] is True
    assert columns["dek_wrapped"]["nullable"] is True
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT encryption_version, encryption_key_id, dek_wrapped "
                "FROM documents WHERE id = 1"
            )
        ).mappings().one()
    engine.dispose()
    assert row["encryption_version"] == 0
    assert row["encryption_key_id"] is None
    assert row["dek_wrapped"] is None

    command.downgrade(cfg, "f5a6b7c8d9e0")
    engine = create_engine(db_url)
    columns_down = {
        col["name"] for col in inspect(engine).get_columns("documents")
    }
    assert "encryption_version" not in columns_down
    assert "encryption_key_id" not in columns_down
    assert "dek_wrapped" not in columns_down
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM documents")).scalar() == 1
    engine.dispose()

    command.upgrade(cfg, "head")
    engine = create_engine(db_url)
    columns_up = {col["name"] for col in inspect(engine).get_columns("documents")}
    engine.dispose()
    assert {"encryption_version", "encryption_key_id", "dek_wrapped"} <= columns_up

def test_document_ownership_retention_migration(migration_db):
    cfg, db_url = migration_db

    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    document_columns = {
        col["name"]: col for col in inspect(engine).get_columns("documents")
    }
    company_columns = {
        col["name"]: col for col in inspect(engine).get_columns("companies")
    }
    assert document_columns["user_id"]["nullable"] is True
    assert document_columns["legal_hold"]["nullable"] is False
    assert "retention_until" in document_columns
    assert "retention_days" in company_columns

    foreign_keys = {
        fk["constrained_columns"][0]: fk
        for fk in inspect(engine).get_foreign_keys("documents")
    }
    assert foreign_keys["user_id"]["options"].get("ondelete") == "SET NULL"
    assert foreign_keys["company_id"]["options"].get("ondelete") == "RESTRICT"

    checks = {
        check["name"]: check
        for check in inspect(engine).get_check_constraints("documents")
    }
    assert "ck_documents_owner_present" in checks

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, username, is_active) "
                "VALUES (1, 'owner@example.com', 'owner', 1)"
            )
        )
        conn.execute(
            text("INSERT INTO companies (id, name) VALUES (1, 'Retention Co')")
        )
        conn.execute(
            text(
                "INSERT INTO documents "
                "(id, user_id, company_id, title, filename, file_type, status) "
                "VALUES (1, NULL, 1, 'Company Doc', 'company.txt', 'txt', 'PROCESSED')"
            )
        )

    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO documents "
                    "(id, user_id, company_id, title, filename, file_type, status) "
                    "VALUES (2, NULL, NULL, 'Orphan', 'orphan.txt', 'txt', 'PROCESSED')"
                )
            )

    engine.dispose()

    # Downgrade cannot represent company-owned rows without an uploader.
    with pytest.raises(RuntimeError, match="Cannot downgrade"):
        command.downgrade(cfg, "d4e5f6a7b8c9")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("UPDATE documents SET user_id = 1 WHERE id = 1"))
    engine.dispose()

    command.downgrade(cfg, "d4e5f6a7b8c9")

    engine = create_engine(db_url)
    downgraded_columns = {
        col["name"] for col in inspect(engine).get_columns("documents")
    }
    assert "legal_hold" not in downgraded_columns
    assert "retention_until" not in downgraded_columns
    assert "retention_days" not in {
        col["name"] for col in inspect(engine).get_columns("companies")
    }
    downgraded_fks = {
        fk["constrained_columns"][0]: fk
        for fk in inspect(engine).get_foreign_keys("documents")
    }
    assert downgraded_fks["user_id"]["options"].get("ondelete") == "CASCADE"
    assert downgraded_fks["company_id"]["options"].get("ondelete") == "SET NULL"
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM documents")).scalar() == 1
    engine.dispose()

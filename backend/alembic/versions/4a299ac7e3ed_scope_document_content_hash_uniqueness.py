"""scope_document_content_hash_uniqueness

Revision ID: 4a299ac7e3ed
Revises: ea6ee676292e
Create Date: 2026-11-10 13:04:32.628661

Removes global content_hash uniqueness on documents and replaces it with:
1. A non-unique index on content_hash for fast lookups.
2. A partial unique index on (company_id, content_hash) for company documents.
3. A partial unique index on (user_id, content_hash) for personal documents
   (where company_id IS NULL).

Existing rows are inspected before any schema change. The previous global
unique index made cross-tenant duplicates impossible, so this migration never
needs to delete or rewrite a document. If same-scope duplicate groups exist
(for example because the old constraint was bypassed manually), the migration
aborts before dropping anything so an operator can resolve them without data
loss.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4a299ac7e3ed"
down_revision: Union[str, None] = "ea6ee676292e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_GLOBAL_INDEX = "ix_documents_content_hash"
_COMPANY_INDEX = "ix_documents_company_content_hash"
_PERSONAL_INDEX = "ix_documents_user_personal_content_hash"


def _report_existing_duplicates(bind) -> None:
    """Abort if duplicate groups would conflict with the scoped indexes.

    The legacy global unique index guaranteed that no content hash could appear
    twice, so this is a defensive check for databases whose constraint was
    bypassed or removed manually. Nothing is deleted or mutated here; the
    migration stops before any schema change so an operator can resolve the
    duplicates deliberately.
    """

    if bind is None or context.is_offline_mode():
        return

    personal_dupes = bind.execute(
        sa.text(
            """
            SELECT user_id, content_hash, COUNT(*) AS cnt
            FROM documents
            WHERE company_id IS NULL AND content_hash IS NOT NULL
            GROUP BY user_id, content_hash
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()

    company_dupes = bind.execute(
        sa.text(
            """
            SELECT company_id, content_hash, COUNT(*) AS cnt
            FROM documents
            WHERE company_id IS NOT NULL AND content_hash IS NOT NULL
            GROUP BY company_id, content_hash
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()

    if personal_dupes or company_dupes:
        raise RuntimeError(
            "Cannot add scoped content_hash unique indexes: found "
            f"{len(personal_dupes)} personal and {len(company_dupes)} company "
            "duplicate content-hash group(s). Resolve or rehash them without "
            "deleting documents, then rerun this migration."
        )


def _drop_global_content_hash_uniqueness(bind) -> None:
    """Drop the legacy global unique index or constraint if it exists.

    Older databases created a unique index named ``ix_documents_content_hash``;
    some deployments may instead expose a unique constraint named
    ``documents_content_hash_key``. Inspecting first keeps the migration safe on
    both shapes and tolerant of an index that was already removed manually.
    """

    if bind is None or context.is_offline_mode():
        op.drop_index(_GLOBAL_INDEX, table_name="documents")
        return

    inspector = sa.inspect(bind)

    # Drop unique constraints first: on PostgreSQL a constraint owns its
    # backing index, so dropping the index directly would fail.
    for constraint in inspector.get_unique_constraints("documents"):
        if constraint.get("column_names") == ["content_hash"]:
            op.drop_constraint(constraint["name"], "documents", type_="unique")

    # Re-inspect after constraint drops so a backing index that disappeared is
    # not dropped a second time.
    inspector = sa.inspect(bind)
    for index in inspector.get_indexes("documents"):
        if index.get("unique") and index.get("column_names") == ["content_hash"]:
            op.drop_index(index["name"], table_name="documents")


def upgrade() -> None:
    bind = op.get_bind()

    # Step 1: Inspect existing duplicate records before applying constraints.
    _report_existing_duplicates(bind)

    # Step 2: Remove the global unique index/constraint on content_hash.
    _drop_global_content_hash_uniqueness(bind)

    # Step 3: Keep a non-unique index for general content-hash lookups.
    op.create_index(
        _GLOBAL_INDEX,
        "documents",
        ["content_hash"],
        unique=False,
    )

    # Step 4: Add the scoped partial unique index for company documents.
    op.create_index(
        _COMPANY_INDEX,
        "documents",
        ["company_id", "content_hash"],
        unique=True,
        postgresql_where=sa.text("company_id IS NOT NULL AND content_hash IS NOT NULL"),
        sqlite_where=sa.text("company_id IS NOT NULL AND content_hash IS NOT NULL"),
    )

    # Step 5: Add the scoped partial unique index for personal documents.
    op.create_index(
        _PERSONAL_INDEX,
        "documents",
        ["user_id", "content_hash"],
        unique=True,
        postgresql_where=sa.text("company_id IS NULL AND content_hash IS NOT NULL"),
        sqlite_where=sa.text("company_id IS NULL AND content_hash IS NOT NULL"),
    )


def downgrade() -> None:
    bind = op.get_bind()

    # Restoring global uniqueness would fail (and could never preserve data) if
    # cross-tenant duplicates now exist. Detect that before dropping anything so
    # the downgrade fails cleanly with an actionable message.
    if bind is not None and not context.is_offline_mode():
        duplicate = bind.execute(
            sa.text(
                """
                SELECT content_hash
                FROM documents
                WHERE content_hash IS NOT NULL
                GROUP BY content_hash
                HAVING COUNT(*) > 1
                LIMIT 1
                """
            )
        ).fetchone()
        if duplicate is not None:
            raise RuntimeError(
                "Cannot restore the global unique content_hash index because "
                "documents from different tenants share a content hash. Resolve "
                "or rehash those documents before downgrading; no data was "
                "deleted."
            )

    # 1. Drop scoped partial unique indexes
    op.drop_index(_PERSONAL_INDEX, table_name="documents")
    op.drop_index(_COMPANY_INDEX, table_name="documents")

    # 2. Drop non-unique index on content_hash
    op.drop_index(_GLOBAL_INDEX, table_name="documents")

    # 3. Restore global unique index on content_hash
    op.create_index(
        _GLOBAL_INDEX,
        "documents",
        ["content_hash"],
        unique=True,
    )

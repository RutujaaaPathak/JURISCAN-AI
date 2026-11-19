"""add corporate document ownership and retention

Revision ID: e6b7c8d9f0a1
Revises: d4e5f6a7b8c9
Create Date: 2026-11-16 00:00:00.000000

Company documents must survive employee account deletion while personal
documents must never be left without an owner. This migration:

* makes ``documents.user_id`` nullable and switches the user FK to SET NULL,
* changes the company FK to RESTRICT so deleting a company cannot silently
  detach or remove its records,
* adds ``legal_hold`` and ``retention_until`` deletion guards, and
* adds a per-company ``retention_days`` policy override.

The owner-present CHECK constraint makes an accidental direct user deletion
fail rather than leaving a personal document orphaned. Downgrading aborts when
such company-owned rows (``user_id IS NULL``) exist, because the old schema
cannot represent them safely.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6b7c8d9f0a1"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FK_NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def _drop_foreign_key(batch_op, table_name: str, column: str, sqlite_name: str) -> None:
    """Drop a FK by its reflected name on PostgreSQL, or by convention on SQLite.

    The user FK predates explicit constraint naming on PostgreSQL and is
    unnamed on SQLite; batch mode names it using ``_FK_NAMING_CONVENTION`` while
    rebuilding the table.
    """

    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        for foreign_key in sa.inspect(bind).get_foreign_keys(table_name):
            if foreign_key.get("constrained_columns") == [column]:
                name = foreign_key.get("name")
                if name:
                    batch_op.drop_constraint(name, type_="foreignkey")
                    return
    batch_op.drop_constraint(sqlite_name, type_="foreignkey")


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("retention_days", sa.Integer(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column(
            "legal_hold",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "documents",
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
    )

    with op.batch_alter_table(
        "documents", naming_convention=_FK_NAMING_CONVENTION
    ) as batch_op:
        _drop_foreign_key(
            batch_op, "documents", "user_id", "fk_documents_user_id_users"
        )
        _drop_foreign_key(
            batch_op,
            "documents",
            "company_id",
            "fk_documents_company_id_companies",
        )
        batch_op.alter_column(
            "user_id", existing_type=sa.Integer(), nullable=True
        )
        batch_op.create_foreign_key(
            "fk_documents_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_documents_company_id_companies",
            "companies",
            ["company_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_check_constraint(
            "ck_documents_owner_present",
            "user_id IS NOT NULL OR company_id IS NOT NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind is not None:
        retained = bind.execute(
            sa.text(
                "SELECT COUNT(*) FROM documents WHERE user_id IS NULL"
            )
        ).scalar()
        if retained:
            raise RuntimeError(
                "Cannot downgrade: company-owned documents no longer have an "
                "uploader (user_id IS NULL). The previous schema would require "
                "deleting or reassigning those records. Export or migrate them "
                "before downgrading."
            )

    with op.batch_alter_table(
        "documents", naming_convention=_FK_NAMING_CONVENTION
    ) as batch_op:
        batch_op.drop_constraint("ck_documents_owner_present", type_="check")
        _drop_foreign_key(
            batch_op, "documents", "user_id", "fk_documents_user_id_users"
        )
        _drop_foreign_key(
            batch_op,
            "documents",
            "company_id",
            "fk_documents_company_id_companies",
        )
        batch_op.drop_column("retention_until")
        batch_op.drop_column("legal_hold")
        batch_op.alter_column(
            "user_id", existing_type=sa.Integer(), nullable=False
        )
        batch_op.create_foreign_key(
            "fk_documents_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_documents_company_id_companies",
            "companies",
            ["company_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.drop_column("companies", "retention_days")

"""add company workspace

Revision ID: a7c9e1b3d5f6
Revises: c4e7a1b2d3f4
Create Date: 2026-11-04

Adds the company workspace: companies, company membership columns on users,
company ownership on documents, and single-use team invitations. Existing
company-role accounts are backfilled into companies (grouped by organisation
name) and their documents are linked to the same company.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c9e1b3d5f6"
down_revision: str | None = "a4f7c2d9e1b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("name <> ''", name="ck_companies_name_not_empty"),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("company_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("company_role", sa.String(length=16), nullable=True))
        batch_op.create_foreign_key(
            "fk_users_company_id_companies",
            "companies",
            ["company_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_check_constraint(
            "ck_users_company_role",
            "company_role IS NULL OR company_role IN "
            "('COMPANY_ADMIN', 'MANAGER', 'MEMBER', 'VIEWER')",
        )

    op.create_index("ix_users_company_id", "users", ["company_id"], unique=False)

    with op.batch_alter_table("documents", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("company_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_documents_company_id_companies",
            "companies",
            ["company_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_index("ix_documents_company_id", "documents", ["company_id"], unique=False)

    op.create_table(
        "company_invitations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("company_role", sa.String(length=16), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("invited_by_user_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "email <> ''", name="ck_company_invitations_email_not_empty"
        ),
        sa.CheckConstraint(
            "company_role IN ('COMPANY_ADMIN', 'MANAGER', 'MEMBER', 'VIEWER')",
            name="ck_company_invitations_role",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'REVOKED', 'EXPIRED')",
            name="ck_company_invitations_status",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["accepted_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_company_invitations_company_id",
        "company_invitations",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        "ix_company_invitations_email",
        "company_invitations",
        ["email"],
        unique=False,
    )
    op.create_index(
        "ix_company_invitations_token_hash",
        "company_invitations",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_company_invitations_company_status",
        "company_invitations",
        ["company_id", "status"],
        unique=False,
    )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, email, full_name, organization_name "
            "FROM users WHERE role = 'company' AND company_id IS NULL"
        )
    ).mappings()

    companies_by_name: dict[str, int] = {}
    for row in rows:
        organization = (row["organization_name"] or "").strip()
        key = organization.lower()
        company_id = companies_by_name.get(key) if key else None
        if company_id is None:
            name = organization or (row["full_name"] or "").strip() or row["email"]
            result = bind.execute(
                sa.text(
                    "INSERT INTO companies (name, created_at, updated_at) "
                    "VALUES (:name, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"name": name},
            )
            company_id = int(result.lastrowid)
            if key:
                companies_by_name[key] = company_id

        bind.execute(
            sa.text(
                "UPDATE users SET company_id = :company_id, "
                "company_role = 'COMPANY_ADMIN' WHERE id = :user_id"
            ),
            {"company_id": company_id, "user_id": row["id"]},
        )
        bind.execute(
            sa.text(
                "UPDATE documents SET company_id = :company_id "
                "WHERE user_id = :user_id AND company_id IS NULL"
            ),
            {"company_id": company_id, "user_id": row["id"]},
        )


def downgrade() -> None:
    op.drop_index("ix_documents_company_id", table_name="documents")
    with op.batch_alter_table("documents", recreate="always") as batch_op:
        batch_op.drop_constraint(
            "fk_documents_company_id_companies", type_="foreignkey"
        )
        batch_op.drop_column("company_id")

    op.drop_index("ix_users_company_id", table_name="users")
    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_users_company_role", type_="check")
        batch_op.drop_constraint("fk_users_company_id_companies", type_="foreignkey")
        batch_op.drop_column("company_role")
        batch_op.drop_column("company_id")

    op.drop_index(
        "ix_company_invitations_company_status",
        table_name="company_invitations",
    )
    op.drop_index(
        "ix_company_invitations_token_hash",
        table_name="company_invitations",
    )
    op.drop_index(
        "ix_company_invitations_email",
        table_name="company_invitations",
    )
    op.drop_index(
        "ix_company_invitations_company_id",
        table_name="company_invitations",
    )
    op.drop_table("company_invitations")
    op.drop_table("companies")

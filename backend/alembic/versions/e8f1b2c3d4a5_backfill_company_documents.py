"""backfill company documents

Revision ID: e8f1b2c3d4a5
Revises: a7c9e1b3d5f6
Create Date: 2026-11-04

Backfills company document relationships:
1. Links existing documents uploaded by company members to their company.
2. Associates users matching company names to their company workspace.
3. Ensures existing analyzed contracts appear in company audit reports.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8f1b2c3d4a5"
down_revision: str | None = "a7c9e1b3d5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from alembic import context
    if context.is_offline_mode():
        return

    bind = op.get_bind()
    if bind is None:
        return

    # 1. Update any documents uploaded by users who already have a company_id
    bind.execute(
        sa.text(
            """
            UPDATE documents
            SET company_id = (
                SELECT u.company_id
                FROM users u
                WHERE u.id = documents.user_id
            )
            WHERE company_id IS NULL
              AND user_id IN (
                  SELECT id FROM users WHERE company_id IS NOT NULL
              )
            """
        )
    )

    # 2. Match users whose full_name or organization_name equals an existing company name
    companies = bind.execute(
        sa.text("SELECT id, name FROM companies")
    ).mappings().all()

    for comp in companies:
        comp_id = comp["id"]
        comp_name = comp["name"].strip()
        if not comp_name:
            continue

        # Find users matching this company name who don't have a company_id
        matched_users = bind.execute(
            sa.text(
                """
                SELECT id FROM users
                WHERE company_id IS NULL
                  AND (
                      LOWER(TRIM(COALESCE(organization_name, ''))) = LOWER(:name)
                      OR LOWER(TRIM(COALESCE(full_name, ''))) = LOWER(:name)
                  )
                """
            ),
            {"name": comp_name},
        ).scalars().all()

        for user_id in matched_users:
            bind.execute(
                sa.text(
                    """
                    UPDATE users
                    SET company_id = :comp_id,
                        company_role = 'COMPANY_ADMIN',
                        role = 'company'
                    WHERE id = :user_id
                    """
                ),
                {"comp_id": comp_id, "user_id": user_id},
            )
            bind.execute(
                sa.text(
                    """
                    UPDATE documents
                    SET company_id = :comp_id
                    WHERE user_id = :user_id AND company_id IS NULL
                    """
                ),
                {"comp_id": comp_id, "user_id": user_id},
            )


def downgrade() -> None:
    pass


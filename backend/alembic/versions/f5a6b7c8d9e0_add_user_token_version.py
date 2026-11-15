"""add user token version

Revision ID: f5a6b7c8d9e0
Revises: 4a299ac7e3ed
Create Date: 2026-11-15 00:00:00.000000

Adds a monotonic session generation to users. Existing rows are backfilled with
the safe default value ``1`` by the column server default, so active accounts
continue to work and newly issued tokens use the same initial version. Logout
and password changes increment the column to revoke every previously issued
token immediately.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, None] = "4a299ac7e3ed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")

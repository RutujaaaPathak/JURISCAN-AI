"""add document encryption metadata

Revision ID: d4e5f6a7b8c9
Revises: f5a6b7c8d9e0
Create Date: 2026-11-16 00:00:00.000000

Adds per-document envelope-encryption metadata. Existing rows keep the explicit
legacy plaintext marker (``encryption_version = 0``); new uploads write version
1 with a wrapped data-encryption key. No document content is moved here.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "encryption_version",
            sa.SmallInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "documents",
        sa.Column("encryption_key_id", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("dek_wrapped", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "dek_wrapped")
    op.drop_column("documents", "encryption_key_id")
    op.drop_column("documents", "encryption_version")

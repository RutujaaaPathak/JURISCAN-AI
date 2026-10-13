"""add extraction metadata

Revision ID: a1c4e9b7f2d0
Revises: 68bc2db9e48b
Create Date: 2026-10-13 02:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c4e9b7f2d0'
down_revision: Union[str, None] = '68bc2db9e48b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'documents',
        sa.Column('extracted_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'clauses',
        sa.Column('page_number', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('clauses', 'page_number')
    op.drop_column('documents', 'extracted_at')

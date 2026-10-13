"""add document error message

Revision ID: b7e2f1a9c3d4
Revises: a1c4e9b7f2d0
Create Date: 2026-10-13 03:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e2f1a9c3d4'
down_revision: Union[str, None] = 'a1c4e9b7f2d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'documents',
        sa.Column('error_message', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('documents', 'error_message')

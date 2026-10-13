"""add user organization name

Revision ID: b3d6f0a1c2e7
Revises: f3b5c7d9e1a2
Create Date: 2026-10-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3d6f0a1c2e7'
down_revision: Union[str, None] = 'f3b5c7d9e1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('organization_name', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'organization_name')

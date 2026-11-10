"""merge OCR provenance branch with company workspace branch

Revision ID: ea6ee676292e
Revises: c9e1a3b5d7f2, e8f1b2c3d4a5
Create Date: 2026-11-10 11:57:05.522932

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ea6ee676292e'
down_revision: Union[str, None] = ('c9e1a3b5d7f2', 'e8f1b2c3d4a5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

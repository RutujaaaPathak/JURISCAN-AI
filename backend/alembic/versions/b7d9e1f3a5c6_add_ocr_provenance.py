"""add OCR page provenance and quality metrics

Revision ID: b7d9e1f3a5c6
Revises: a4f7c2d9e1b8
Create Date: 2026-11-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d9e1f3a5c6'
down_revision: Union[str, None] = 'a4f7c2d9e1b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'documents',
        sa.Column('page_spans', sa.JSON(), nullable=True),
    )
    op.add_column(
        'documents',
        sa.Column('ocr_quality', sa.JSON(), nullable=True),
    )
    op.add_column(
        'documents',
        sa.Column('quality_warnings', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('documents', 'quality_warnings')
    op.drop_column('documents', 'ocr_quality')
    op.drop_column('documents', 'page_spans')

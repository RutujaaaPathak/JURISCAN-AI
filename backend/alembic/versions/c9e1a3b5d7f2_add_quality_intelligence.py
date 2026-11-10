"""add clause quality and finding review metadata

Revision ID: c9e1a3b5d7f2
Revises: b7d9e1f3a5c6
Create Date: 2026-11-05 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9e1a3b5d7f2'
down_revision: Union[str, None] = 'b7d9e1f3a5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'clauses',
        sa.Column('normalized_text', sa.Text(), nullable=True),
    )
    op.add_column(
        'clauses',
        sa.Column('normalization_changes', sa.JSON(), nullable=True),
    )
    op.add_column(
        'clauses',
        sa.Column('ocr_quality', sa.JSON(), nullable=True),
    )
    op.add_column(
        'risk_findings',
        sa.Column(
            'requires_review',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        'risk_findings',
        sa.Column('review_reason', sa.Text(), nullable=True),
    )
    op.add_column(
        'risk_findings',
        sa.Column('ocr_confidence', sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('risk_findings', 'ocr_confidence')
    op.drop_column('risk_findings', 'review_reason')
    op.drop_column('risk_findings', 'requires_review')
    op.drop_column('clauses', 'ocr_quality')
    op.drop_column('clauses', 'normalization_changes')
    op.drop_column('clauses', 'normalized_text')

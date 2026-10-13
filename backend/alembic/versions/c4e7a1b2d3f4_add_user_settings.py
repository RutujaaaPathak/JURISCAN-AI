"""add user settings

Revision ID: c4e7a1b2d3f4
Revises: b3d6f0a1c2e7
Create Date: 2026-10-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e7a1b2d3f4'
down_revision: Union[str, None] = 'b3d6f0a1c2e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NOW = sa.text('(CURRENT_TIMESTAMP)')


def upgrade() -> None:
    op.create_table(
        'user_settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('jurisdiction', sa.String(length=128), nullable=True),
        sa.Column('min_severity', sa.String(length=16), server_default='medium', nullable=False),
        sa.Column('analysis_model', sa.String(length=32), server_default='rules', nullable=False),
        sa.Column('auto_analyze', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('notify_email_digest', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('notify_high_risk', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('notify_weekly_report', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.CheckConstraint(
            "min_severity IN ('low', 'medium', 'high', 'critical')",
            name='ck_user_settings_min_severity',
        ),
        sa.CheckConstraint(
            "analysis_model IN ('rules', 'heuristic', 'legal-bert')",
            name='ck_user_settings_analysis_model',
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_user_settings_user_id'), 'user_settings', ['user_id'], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_user_settings_user_id'), table_name='user_settings')
    op.drop_table('user_settings')

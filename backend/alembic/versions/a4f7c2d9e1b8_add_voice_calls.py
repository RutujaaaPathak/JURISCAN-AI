"""add voice calls

Revision ID: a4f7c2d9e1b8
Revises: c4e7a1b2d3f4
Create Date: 2026-11-04 19:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4f7c2d9e1b8'
down_revision: Union[str, None] = 'c4e7a1b2d3f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NOW = sa.text('(CURRENT_TIMESTAMP)')


def upgrade() -> None:
    op.create_table(
        'calls',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('caller_id', sa.Integer(), nullable=False),
        sa.Column('receiver_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=16), server_default='RINGING', nullable=False),
        sa.Column('answered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.CheckConstraint(
            "status IN ('RINGING', 'ACCEPTED', 'REJECTED', 'MISSED', 'ENDED', 'FAILED')",
            name='ck_calls_status',
        ),
        sa.CheckConstraint(
            'caller_id <> receiver_id',
            name='ck_calls_caller_receiver_distinct',
        ),
        sa.CheckConstraint(
            'duration IS NULL OR duration >= 0',
            name='ck_calls_duration_non_negative',
        ),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['caller_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['receiver_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_calls_case_id'),
        'calls',
        ['case_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_calls_caller_id'),
        'calls',
        ['caller_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_calls_receiver_id'),
        'calls',
        ['receiver_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_calls_status'),
        'calls',
        ['status'],
        unique=False,
    )
    op.create_index(
        'ix_calls_active_case',
        'calls',
        ['case_id'],
        unique=True,
        postgresql_where=sa.text("status IN ('RINGING', 'ACCEPTED')"),
        sqlite_where=sa.text("status IN ('RINGING', 'ACCEPTED')"),
    )


def downgrade() -> None:
    op.drop_index('ix_calls_active_case', table_name='calls')
    op.drop_index(op.f('ix_calls_status'), table_name='calls')
    op.drop_index(op.f('ix_calls_receiver_id'), table_name='calls')
    op.drop_index(op.f('ix_calls_caller_id'), table_name='calls')
    op.drop_index(op.f('ix_calls_case_id'), table_name='calls')
    op.drop_table('calls')

"""add client-lawyer workspace (deadline, messages, fees, appointments)

Revision ID: e2a4b6c8d0f1
Revises: d1f3a7b9c2e4
Create Date: 2026-10-13 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2a4b6c8d0f1'
down_revision: Union[str, None] = 'd1f3a7b9c2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NOW = sa.text('(CURRENT_TIMESTAMP)')


def upgrade() -> None:
    with op.batch_alter_table('cases') as batch_op:
        batch_op.add_column(
            sa.Column('deadline', sa.DateTime(timezone=True), nullable=True)
        )

    op.create_table(
        'case_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('sender_user_id', sa.Integer(), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_case_messages_case_id'), 'case_messages', ['case_id'], unique=False)

    op.create_table(
        'case_fee_proposals',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('proposed_by_user_id', sa.Integer(), nullable=True),
        sa.Column('amount', sa.String(length=64), nullable=False),
        sa.Column('currency', sa.String(length=8), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.CheckConstraint(
            "status IN ('PROPOSED', 'ACCEPTED', 'DECLINED', 'SUPERSEDED')",
            name='ck_case_fee_proposals_status',
        ),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['proposed_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_case_fee_proposals_case_id'), 'case_fee_proposals', ['case_id'], unique=False
    )
    op.create_index(
        op.f('ix_case_fee_proposals_status'), 'case_fee_proposals', ['status'], unique=False
    )

    op.create_table(
        'case_appointments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('proposed_by_user_id', sa.Integer(), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('mode', sa.String(length=32), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.CheckConstraint(
            "status IN ('PROPOSED', 'CONFIRMED', 'CANCELLED')",
            name='ck_case_appointments_status',
        ),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['proposed_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_case_appointments_case_id'), 'case_appointments', ['case_id'], unique=False
    )
    op.create_index(
        op.f('ix_case_appointments_status'), 'case_appointments', ['status'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_case_appointments_status'), table_name='case_appointments')
    op.drop_index(op.f('ix_case_appointments_case_id'), table_name='case_appointments')
    op.drop_table('case_appointments')
    op.drop_index(op.f('ix_case_fee_proposals_status'), table_name='case_fee_proposals')
    op.drop_index(op.f('ix_case_fee_proposals_case_id'), table_name='case_fee_proposals')
    op.drop_table('case_fee_proposals')
    op.drop_index(op.f('ix_case_messages_case_id'), table_name='case_messages')
    op.drop_table('case_messages')

    with op.batch_alter_table('cases') as batch_op:
        batch_op.drop_column('deadline')

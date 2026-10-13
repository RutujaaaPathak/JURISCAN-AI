"""add pre-assignment case clarification threads

Revision ID: f3b5c7d9e1a2
Revises: e2a4b6c8d0f1
Create Date: 2026-10-13 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3b5c7d9e1a2'
down_revision: Union[str, None] = 'e2a4b6c8d0f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NOW = sa.text('(CURRENT_TIMESTAMP)')


def upgrade() -> None:
    op.create_table(
        'case_clarification_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('lawyer_id', sa.Integer(), nullable=False),
        sa.Column('sender_user_id', sa.Integer(), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lawyer_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_case_clarification_messages_case_id'),
        'case_clarification_messages',
        ['case_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_case_clarification_messages_lawyer_id'),
        'case_clarification_messages',
        ['lawyer_id'],
        unique=False,
    )
    op.create_index(
        'ix_case_clarifications_case_lawyer',
        'case_clarification_messages',
        ['case_id', 'lawyer_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_case_clarifications_case_lawyer', table_name='case_clarification_messages')
    op.drop_index(
        op.f('ix_case_clarification_messages_lawyer_id'),
        table_name='case_clarification_messages',
    )
    op.drop_index(
        op.f('ix_case_clarification_messages_case_id'),
        table_name='case_clarification_messages',
    )
    op.drop_table('case_clarification_messages')

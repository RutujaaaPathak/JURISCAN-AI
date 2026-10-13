"""add clause hierarchy

Revision ID: c8d5e2f1a9b3
Revises: b7e2f1a9c3d4
Create Date: 2026-10-13 15:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8d5e2f1a9b3'
down_revision: Union[str, None] = 'b7e2f1a9c3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('clauses') as batch_op:
        batch_op.add_column(
            sa.Column('label', sa.String(length=128), nullable=True)
        )
        batch_op.add_column(
            sa.Column('level', sa.Integer(), nullable=False, server_default='1')
        )
        batch_op.add_column(
            sa.Column('parent_id', sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            'fk_clauses_parent_id_clauses',
            'clauses',
            ['parent_id'],
            ['id'],
            ondelete='SET NULL',
        )
        batch_op.create_index(
            op.f('ix_clauses_parent_id'),
            ['parent_id'],
            unique=False,
        )
        batch_op.create_index(
            'ix_clauses_document_parent',
            ['document_id', 'parent_id'],
            unique=False,
        )
        batch_op.create_check_constraint(
            'ck_clauses_level_positive',
            'level >= 1',
        )


def downgrade() -> None:
    with op.batch_alter_table('clauses') as batch_op:
        batch_op.drop_constraint('ck_clauses_level_positive', type_='check')
        batch_op.drop_index('ix_clauses_document_parent')
        batch_op.drop_index(op.f('ix_clauses_parent_id'))
        batch_op.drop_constraint('fk_clauses_parent_id_clauses', type_='foreignkey')
        batch_op.drop_column('parent_id')
        batch_op.drop_column('level')
        batch_op.drop_column('label')

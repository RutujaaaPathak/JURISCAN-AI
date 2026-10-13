"""add lawyer and case domain

Revision ID: d1f3a7b9c2e4
Revises: c8d5e2f1a9b3
Create Date: 2026-10-13 16:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1f3a7b9c2e4'
down_revision: Union[str, None] = 'c8d5e2f1a9b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NOW = sa.text('(CURRENT_TIMESTAMP)')


def upgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(
            sa.Column(
                'role',
                sa.String(length=16),
                server_default='individual',
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            'ck_users_role',
            "role IN ('individual', 'company', 'lawyer', 'admin')",
        )

    op.create_table(
        'lawyer_profiles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('bar_registration_number', sa.String(length=128), nullable=True),
        sa.Column('jurisdiction', sa.String(length=128), nullable=True),
        sa.Column('years_experience', sa.Integer(), nullable=True),
        sa.Column('practice_areas', sa.JSON(), nullable=True),
        sa.Column('languages', sa.JSON(), nullable=True),
        sa.Column('location', sa.String(length=128), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('consultation_modes', sa.JSON(), nullable=True),
        sa.Column('fee_structure', sa.String(length=255), nullable=True),
        sa.Column('photo_url', sa.String(length=512), nullable=True),
        sa.Column('availability', sa.String(length=255), nullable=True),
        sa.Column('verification_status', sa.String(length=16), nullable=False),
        sa.Column('verification_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.CheckConstraint(
            "verification_status IN ('UNVERIFIED', 'PENDING', 'VERIFIED', 'REJECTED')",
            name='ck_lawyer_profiles_verification_status',
        ),
        sa.CheckConstraint(
            'years_experience IS NULL OR years_experience >= 0',
            name='ck_lawyer_profiles_experience_non_negative',
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_lawyer_profiles_user_id'), 'lawyer_profiles', ['user_id'], unique=True
    )

    op.create_table(
        'cases',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('posted_by_user_id', sa.Integer(), nullable=False),
        sa.Column('assigned_lawyer_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=32), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('jurisdiction', sa.String(length=128), nullable=True),
        sa.Column('urgency', sa.String(length=16), nullable=False),
        sa.Column('consultation_method', sa.String(length=32), nullable=True),
        sa.Column('budget', sa.String(length=128), nullable=True),
        sa.Column('contact_preference', sa.String(length=128), nullable=True),
        sa.Column('client_reference', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.CheckConstraint(
            "category IN ('property', 'family', 'employment', 'business', 'consumer', "
            "'cybercrime', 'criminal', 'immigration', 'intellectual_property', 'tax', 'other')",
            name='ck_cases_category',
        ),
        sa.CheckConstraint(
            "urgency IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name='ck_cases_urgency'
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'ASSIGNED', 'COMPLETED', 'CLOSED')", name='ck_cases_status'
        ),
        sa.ForeignKeyConstraint(['posted_by_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_lawyer_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_cases_posted_by_user_id'), 'cases', ['posted_by_user_id'], unique=False)
    op.create_index(op.f('ix_cases_assigned_lawyer_id'), 'cases', ['assigned_lawyer_id'], unique=False)
    op.create_index(op.f('ix_cases_category'), 'cases', ['category'], unique=False)
    op.create_index(op.f('ix_cases_urgency'), 'cases', ['urgency'], unique=False)
    op.create_index(op.f('ix_cases_status'), 'cases', ['status'], unique=False)

    op.create_table(
        'case_documents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('shared_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shared_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('case_id', 'document_id', name='uq_case_documents_case_document'),
    )
    op.create_index(op.f('ix_case_documents_case_id'), 'case_documents', ['case_id'], unique=False)
    op.create_index(op.f('ix_case_documents_document_id'), 'case_documents', ['document_id'], unique=False)

    op.create_table(
        'case_decisions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('lawyer_id', sa.Integer(), nullable=False),
        sa.Column('decision', sa.String(length=16), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.CheckConstraint(
            "decision IN ('ACCEPT', 'REJECT', 'REQUEST_INFO')",
            name='ck_case_decisions_decision',
        ),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lawyer_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'case_id', 'lawyer_id', 'decision', name='uq_case_decisions_case_lawyer_decision'
        ),
    )
    op.create_index(op.f('ix_case_decisions_case_id'), 'case_decisions', ['case_id'], unique=False)
    op.create_index(op.f('ix_case_decisions_lawyer_id'), 'case_decisions', ['lawyer_id'], unique=False)

    op.create_table(
        'case_activities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=32), nullable=False),
        sa.Column('detail', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_case_activities_case_id'), 'case_activities', ['case_id'], unique=False)

    op.create_table(
        'case_notes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('author_user_id', sa.Integer(), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_case_notes_case_id'), 'case_notes', ['case_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_case_notes_case_id'), table_name='case_notes')
    op.drop_table('case_notes')
    op.drop_index(op.f('ix_case_activities_case_id'), table_name='case_activities')
    op.drop_table('case_activities')
    op.drop_index(op.f('ix_case_decisions_lawyer_id'), table_name='case_decisions')
    op.drop_index(op.f('ix_case_decisions_case_id'), table_name='case_decisions')
    op.drop_table('case_decisions')
    op.drop_index(op.f('ix_case_documents_document_id'), table_name='case_documents')
    op.drop_index(op.f('ix_case_documents_case_id'), table_name='case_documents')
    op.drop_table('case_documents')
    op.drop_index(op.f('ix_cases_status'), table_name='cases')
    op.drop_index(op.f('ix_cases_urgency'), table_name='cases')
    op.drop_index(op.f('ix_cases_category'), table_name='cases')
    op.drop_index(op.f('ix_cases_assigned_lawyer_id'), table_name='cases')
    op.drop_index(op.f('ix_cases_posted_by_user_id'), table_name='cases')
    op.drop_table('cases')
    op.drop_index(op.f('ix_lawyer_profiles_user_id'), table_name='lawyer_profiles')
    op.drop_table('lawyer_profiles')

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_constraint('ck_users_role', type_='check')
        batch_op.drop_column('role')

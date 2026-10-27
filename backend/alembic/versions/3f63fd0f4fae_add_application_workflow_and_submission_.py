"""add application workflow and submission attempts

Revision ID: 3f63fd0f4fae
Revises: 2692bda4ba04
Create Date: 2026-10-27 12:09:30.354328

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f63fd0f4fae'
down_revision: Union[str, Sequence[str], None] = '2692bda4ba04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema adding submission attempts and application workflow fields."""
    # 1. Create submission_attempts table
    op.create_table(
        'submission_attempts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('application_id', sa.String(length=36), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('adapter_identifier', sa.String(length=100), nullable=False),
        sa.Column('selected_resume_version_id', sa.String(length=36), nullable=False),
        sa.Column('uploaded_artifact_sha256', sa.String(length=64), nullable=False),
        sa.Column('outcome', sa.String(length=50), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmation_reference', sa.String(length=255), nullable=True),
        sa.Column('confirmation_payload', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('sanitized_diagnostics', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('reconciliation_metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['selected_resume_version_id'], ['resume_versions.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_submission_attempts_application_id'), 'submission_attempts', ['application_id'], unique=False)
    op.create_index(op.f('ix_submission_attempts_outcome'), 'submission_attempts', ['outcome'], unique=False)
    op.create_index(op.f('ix_submission_attempts_selected_resume_version_id'), 'submission_attempts', ['selected_resume_version_id'], unique=False)

    # 2. Add approval gate & resume checksum columns to applications
    op.add_column('applications', sa.Column('selected_resume_sha256', sa.String(length=64), nullable=True))
    op.add_column('applications', sa.Column('approval_fingerprint', sa.String(length=64), nullable=True))
    op.add_column('applications', sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('applications', sa.Column('approval_metadata', sa.JSON(), nullable=False, server_default='{}'))
    op.create_index(op.f('ix_applications_approval_fingerprint'), 'applications', ['approval_fingerprint'], unique=False)

    # 3. Unique index on (candidate_id, job_id) for idempotent duplicate prevention
    op.create_index('uq_candidate_job_application', 'applications', ['candidate_id', 'job_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_candidate_job_application', table_name='applications')
    op.drop_index(op.f('ix_applications_approval_fingerprint'), table_name='applications')
    op.drop_column('applications', 'approval_metadata')
    op.drop_column('applications', 'approved_at')
    op.drop_column('applications', 'approval_fingerprint')
    op.drop_column('applications', 'selected_resume_sha256')
    op.drop_index(op.f('ix_submission_attempts_selected_resume_version_id'), table_name='submission_attempts')
    op.drop_index(op.f('ix_submission_attempts_outcome'), table_name='submission_attempts')
    op.drop_index(op.f('ix_submission_attempts_application_id'), table_name='submission_attempts')
    op.drop_table('submission_attempts')

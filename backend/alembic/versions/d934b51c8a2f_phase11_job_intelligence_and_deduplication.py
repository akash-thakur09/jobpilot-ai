"""phase11 job intelligence and deduplication

Revision ID: d934b51c8a2f
Revises: c821a4f02b9e
Create Date: 2026-10-28 15:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd934b51c8a2f'
down_revision: Union[str, Sequence[str], None] = 'c821a4f02b9e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create job_duplicate_clusters table first
    op.create_table(
        'job_duplicate_clusters',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('canonical_job_id', sa.String(length=36), nullable=True),
        sa.Column('cluster_status', sa.String(length=50), nullable=False, server_default='DETECTED'),
        sa.Column('confidence', sa.String(length=50), nullable=False, server_default='POSSIBLE_DUPLICATE'),
        sa.Column('confidence_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('match_reasons', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['canonical_job_id'], ['jobs.id'], ondelete='SET NULL')
    )
    op.create_index(op.f('ix_job_duplicate_clusters_canonical_job_id'), 'job_duplicate_clusters', ['canonical_job_id'], unique=False)
    op.create_index(op.f('ix_job_duplicate_clusters_cluster_status'), 'job_duplicate_clusters', ['cluster_status'], unique=False)

    # 2. Add columns to jobs table
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')))
        batch_op.add_column(sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')))
        batch_op.add_column(sa.Column('freshness_status', sa.String(length=50), nullable=False, server_default='ACTIVE'))
        batch_op.add_column(sa.Column('freshness_reason', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('duplicate_cluster_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_jobs_freshness_status'), ['freshness_status'], unique=False)
        batch_op.create_index(batch_op.f('ix_jobs_duplicate_cluster_id'), ['duplicate_cluster_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_jobs_duplicate_cluster_id',
            'job_duplicate_clusters',
            ['duplicate_cluster_id'],
            ['id'],
            ondelete='SET NULL'
        )

    # 3. Create job_feedbacks table
    op.create_table(
        'job_feedbacks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('candidate_id', sa.String(length=36), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('feedback_type', sa.String(length=50), nullable=False, server_default='RELEVANT'),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('structured_details', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidate_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('candidate_id', 'job_id', name='uq_candidate_job_feedback')
    )
    op.create_index(op.f('ix_job_feedbacks_candidate_id'), 'job_feedbacks', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_job_feedbacks_job_id'), 'job_feedbacks', ['job_id'], unique=False)
    op.create_index(op.f('ix_job_feedbacks_feedback_type'), 'job_feedbacks', ['feedback_type'], unique=False)


def downgrade() -> None:
    # 1. Drop job_feedbacks table
    op.drop_index(op.f('ix_job_feedbacks_feedback_type'), table_name='job_feedbacks')
    op.drop_index(op.f('ix_job_feedbacks_job_id'), table_name='job_feedbacks')
    op.drop_index(op.f('ix_job_feedbacks_candidate_id'), table_name='job_feedbacks')
    op.drop_table('job_feedbacks')

    # 2. Revert jobs table additions
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_constraint('fk_jobs_duplicate_cluster_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_jobs_duplicate_cluster_id'))
        batch_op.drop_index(batch_op.f('ix_jobs_freshness_status'))
        batch_op.drop_column('duplicate_cluster_id')
        batch_op.drop_column('last_verified_at')
        batch_op.drop_column('freshness_reason')
        batch_op.drop_column('freshness_status')
        batch_op.drop_column('last_seen_at')
        batch_op.drop_column('first_seen_at')
        batch_op.drop_column('posted_at')

    # 3. Drop job_duplicate_clusters table
    op.drop_index(op.f('ix_job_duplicate_clusters_cluster_status'), table_name='job_duplicate_clusters')
    op.drop_index(op.f('ix_job_duplicate_clusters_canonical_job_id'), table_name='job_duplicate_clusters')
    op.drop_table('job_duplicate_clusters')

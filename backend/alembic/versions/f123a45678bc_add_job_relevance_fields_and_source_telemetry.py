"""add_job_relevance_fields_and_source_telemetry

Revision ID: f123a45678bc
Revises: e145f6789abc
Create Date: 2026-11-02 16:22:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f123a45678bc'
down_revision: Union[str, Sequence[str], None] = 'e145f6789abc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add relevance fields to jobs table
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('relevance_score', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('relevance_classification', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('relevance_metadata', sa.JSON(), nullable=True))
        batch_op.create_index(batch_op.f('ix_jobs_relevance_score'), ['relevance_score'], unique=False)
        batch_op.create_index(batch_op.f('ix_jobs_relevance_classification'), ['relevance_classification'], unique=False)

    # 2. Add jobs_relevant_count to job_sources table
    with op.batch_alter_table('job_sources', schema=None) as batch_op:
        batch_op.add_column(sa.Column('jobs_relevant_count', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('job_sources', schema=None) as batch_op:
        batch_op.drop_column('jobs_relevant_count')

    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_jobs_relevance_classification'))
        batch_op.drop_index(batch_op.f('ix_jobs_relevance_score'))
        batch_op.drop_column('relevance_metadata')
        batch_op.drop_column('relevance_classification')
        batch_op.drop_column('relevance_score')


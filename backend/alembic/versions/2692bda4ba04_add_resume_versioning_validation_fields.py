"""add resume versioning validation fields

Revision ID: 2692bda4ba04
Revises: 667e479abab5
Create Date: 2026-10-26 16:01:49.856660

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2692bda4ba04'
down_revision: Union[str, Sequence[str], None] = '667e479abab5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema adding versioning columns."""
    op.add_column('resume_versions', sa.Column('match_score_id', sa.String(length=36), nullable=True))
    op.add_column('resume_versions', sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('resume_versions', sa.Column('is_submission_ready', sa.Boolean(), nullable=False, server_default='1'))
    op.add_column('resume_versions', sa.Column('factual_validation_result', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('resume_versions', sa.Column('keyword_coverage_result', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('resume_versions', sa.Column('job_fingerprint', sa.String(length=64), nullable=True))
    op.add_column('resume_versions', sa.Column('tailoring_policy_version', sa.String(length=50), nullable=False, server_default='1.0.0'))
    op.create_index(op.f('ix_resume_versions_match_score_id'), 'resume_versions', ['match_score_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_resume_versions_match_score_id'), table_name='resume_versions')
    op.drop_column('resume_versions', 'tailoring_policy_version')
    op.drop_column('resume_versions', 'job_fingerprint')
    op.drop_column('resume_versions', 'keyword_coverage_result')
    op.drop_column('resume_versions', 'factual_validation_result')
    op.drop_column('resume_versions', 'is_submission_ready')
    op.drop_column('resume_versions', 'version_number')
    op.drop_column('resume_versions', 'match_score_id')

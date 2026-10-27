"""add search preferences and source config

Revision ID: 5e29f8a31c4d
Revises: 4b81cf738a92
Create Date: 2026-10-27 18:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e29f8a31c4d'
down_revision: Union[str, Sequence[str], None] = '4b81cf738a92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add search and notification preferences to candidate_profiles; add config and health to job_sources."""
    with op.batch_alter_table('candidate_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('search_preferences', sa.JSON(), nullable=False, server_default='{}'))
        batch_op.add_column(sa.Column('notification_preferences', sa.JSON(), nullable=False, server_default='{}'))

    with op.batch_alter_table('job_sources', schema=None) as batch_op:
        batch_op.add_column(sa.Column('config_json', sa.JSON(), nullable=False, server_default='{}'))
        batch_op.add_column(sa.Column('last_status', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('last_error_summary', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('jobs_discovered_count', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Revert search preferences and source config fields."""
    with op.batch_alter_table('job_sources', schema=None) as batch_op:
        batch_op.drop_column('jobs_discovered_count')
        batch_op.drop_column('last_error_summary')
        batch_op.drop_column('last_status')
        batch_op.drop_column('config_json')

    with op.batch_alter_table('candidate_profiles', schema=None) as batch_op:
        batch_op.drop_column('notification_preferences')
        batch_op.drop_column('search_preferences')

"""phase12_add_job_discovered_at_and_canonical_url_indexes

Revision ID: e145f6789abc
Revises: d934b51c8a2f
Create Date: 2026-10-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e145f6789abc'
down_revision: Union[str, None] = 'd934b51c8a2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Safely create indexes if they do not exist
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_jobs_canonical_url'), ['canonical_url'], unique=False)
        batch_op.create_index(batch_op.f('ix_jobs_discovered_at'), ['discovered_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_jobs_discovered_at'))
        batch_op.drop_index(batch_op.f('ix_jobs_canonical_url'))

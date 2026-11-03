"""add source_type and integration_status to job_sources

Revision ID: d823fa19b2e4
Revises: c14fd127ea45
Create Date: 2026-11-03 12:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd823fa19b2e4'
down_revision: Union[str, Sequence[str], None] = 'c14fd127ea45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('job_sources', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('source_type', sa.String(length=50), nullable=False, server_default='job_board')
        )
        batch_op.add_column(
            sa.Column('integration_status', sa.String(length=50), nullable=False, server_default='AVAILABLE')
        )


def downgrade() -> None:
    with op.batch_alter_table('job_sources', schema=None) as batch_op:
        batch_op.drop_column('integration_status')
        batch_op.drop_column('source_type')


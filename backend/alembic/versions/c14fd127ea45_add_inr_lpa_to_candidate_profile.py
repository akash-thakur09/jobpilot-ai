"""add inr lpa to candidate profile

Revision ID: c14fd127ea45
Revises: f123a45678bc
Create Date: 2026-11-02 18:36:48.438289

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c14fd127ea45'
down_revision: Union[str, Sequence[str], None] = 'f123a45678bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('candidate_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('target_package_min_lpa', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('target_package_max_lpa', sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('candidate_profiles', schema=None) as batch_op:
        batch_op.drop_column('target_package_max_lpa')
        batch_op.drop_column('target_package_min_lpa')

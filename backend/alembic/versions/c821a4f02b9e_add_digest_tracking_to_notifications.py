"""add digest tracking to notifications

Revision ID: c821a4f02b9e
Revises: 5e29f8a31c4d
Create Date: 2026-10-28 11:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c821a4f02b9e'
down_revision: Union[str, Sequence[str], None] = '5e29f8a31c4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add digest_id and digested_at columns to notifications for robust digest tracking and idempotency."""
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.add_column(sa.Column('digest_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('digested_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(batch_op.f('ix_notifications_digest_id'), ['digest_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_notifications_digested_at'), ['digested_at'], unique=False)
        batch_op.create_foreign_key(
            'fk_notifications_digest_id',
            'notifications',
            ['digest_id'],
            ['id'],
            ondelete='SET NULL'
        )


def downgrade() -> None:
    """Revert digest tracking columns from notifications."""
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_constraint('fk_notifications_digest_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_notifications_digested_at'))
        batch_op.drop_index(batch_op.f('ix_notifications_digest_id'))
        batch_op.drop_column('digested_at')
        batch_op.drop_column('digest_id')

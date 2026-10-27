"""add notification enhancements and dedup

Revision ID: 4b81cf738a92
Revises: 3f63fd0f4fae
Create Date: 2026-10-27 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b81cf738a92'
down_revision: Union[str, Sequence[str], None] = '3f63fd0f4fae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade notifications schema with type, read/dismissed flags, references, and dedup_key."""
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.add_column(sa.Column('notification_type', sa.String(length=50), nullable=False, server_default='NEW_MATCH'))
        batch_op.add_column(sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('is_dismissed', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('job_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('application_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('run_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('dedup_key', sa.String(length=255), nullable=True))

        batch_op.create_index(batch_op.f('ix_notifications_notification_type'), ['notification_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_notifications_is_read'), ['is_read'], unique=False)
        batch_op.create_index(batch_op.f('ix_notifications_is_dismissed'), ['is_dismissed'], unique=False)
        batch_op.create_index(batch_op.f('ix_notifications_job_id'), ['job_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_notifications_application_id'), ['application_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_notifications_run_id'), ['run_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_notifications_dedup_key'), ['dedup_key'], unique=True)

        batch_op.create_foreign_key('fk_notifications_job_id', 'jobs', ['job_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_notifications_application_id', 'applications', ['application_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_notifications_run_id', 'automation_runs', ['run_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade notifications schema."""
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_constraint('fk_notifications_run_id', type_='foreignkey')
        batch_op.drop_constraint('fk_notifications_application_id', type_='foreignkey')
        batch_op.drop_constraint('fk_notifications_job_id', type_='foreignkey')

        batch_op.drop_index(batch_op.f('ix_notifications_dedup_key'))
        batch_op.drop_index(batch_op.f('ix_notifications_run_id'))
        batch_op.drop_index(batch_op.f('ix_notifications_application_id'))
        batch_op.drop_index(batch_op.f('ix_notifications_job_id'))
        batch_op.drop_index(batch_op.f('ix_notifications_is_dismissed'))
        batch_op.drop_index(batch_op.f('ix_notifications_is_read'))
        batch_op.drop_index(batch_op.f('ix_notifications_notification_type'))

        batch_op.drop_column('dedup_key')
        batch_op.drop_column('run_id')
        batch_op.drop_column('application_id')
        batch_op.drop_column('job_id')
        batch_op.drop_column('is_dismissed')
        batch_op.drop_column('is_read')
        batch_op.drop_column('notification_type')

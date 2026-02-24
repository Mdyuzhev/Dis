"""add camera_discrepancy_events table

Revision ID: 6cef01729455
Revises: 28949206c996
Create Date: 2026-01-23 12:28:06.859387

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6cef01729455'
down_revision: Union[str, Sequence[str], None] = '28949206c996'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        'camera_discrepancy_events',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('sn', sa.String(), nullable=False),
        sa.Column('uid', sa.String()),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('old_account_email', sa.String()),
        sa.Column('new_account_email', sa.String()),
        sa.Column('is_notified', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index('idx_discrepancy_sn', 'camera_discrepancy_events', ['sn'])
    op.create_index('idx_discrepancy_type', 'camera_discrepancy_events', ['type'])
    op.create_index('idx_discrepancy_detected_at', 'camera_discrepancy_events', ['detected_at'])
    op.create_index('idx_discrepancy_notified', 'camera_discrepancy_events', ['is_notified'])


def downgrade():
    op.drop_index('idx_discrepancy_notified')
    op.drop_index('idx_discrepancy_detected_at')
    op.drop_index('idx_discrepancy_type')
    op.drop_index('idx_discrepancy_sn')
    op.drop_table('camera_discrepancy_events')

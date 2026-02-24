"""add testit_events table

Revision ID: 61f940cb7af9
Revises: 3672b0fda377
Create Date: 2026-02-09 13:16:02.113103

"""

from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '61f940cb7af9'
down_revision: Union[str, Sequence[str], None] = '3672b0fda377'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'testit_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=32), nullable=False),
        sa.Column('work_item_id', sa.String(length=64), nullable=False),
        sa.Column('work_item_type', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=512), nullable=False),
        sa.Column('author', sa.String(length=128), nullable=False),
        sa.Column('project_name', sa.String(length=256), nullable=False),
        sa.Column('section_id', sa.String(length=64), nullable=True),
        sa.Column('section_name', sa.String(length=256), nullable=True),
        sa.Column('url', sa.String(length=1024), nullable=False),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_testit_events_work_item_id', 'work_item_id'),
        sa.Index('ix_testit_events_author', 'author'),
        sa.Index('ix_testit_events_created_at', 'created_at'),
        sa.Index('ix_testit_events_event_type', 'event_type')
    )


def downgrade() -> None:
    op.drop_table('testit_events')

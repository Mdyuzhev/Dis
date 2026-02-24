"""remove_stats_time_from_config

Revision ID: cf15f72052d0
Revises: fda5f18a6e56
Create Date: 2026-02-10 14:39:34.847160

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cf15f72052d0'
down_revision: Union[str, Sequence[str], None] = 'fda5f18a6e56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('testit_config', 'stats_time')

    # Удаляем избыточные поля из scheduled_tasks
    op.drop_column('scheduled_tasks', 'execute_at_hour')
    op.drop_column('scheduled_tasks', 'execute_at_minute')


def downgrade() -> None:
    # Вернём обратно
    op.add_column('testit_config', sa.Column('stats_time', sa.String(16), nullable=False, default='19:00'))
    op.add_column('scheduled_tasks', sa.Column('execute_at_hour', sa.Integer(), nullable=False))
    op.add_column('scheduled_tasks', sa.Column('execute_at_minute', sa.Integer(), nullable=False))

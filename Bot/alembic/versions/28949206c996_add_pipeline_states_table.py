"""add pipeline_states table

Revision ID: 28949206c996
Revises: ca3852ccd27e
Create Date: 2026-01-13 16:41:07.203937

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '28949206c996'
down_revision: Union[str, Sequence[str], None] = 'ca3852ccd27e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Создаём таблицу pipeline_states"""
    op.create_table(
        'pipeline_states',
        sa.Column('pipeline_id', sa.BigInteger(), nullable=False),
        sa.Column('project_id', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('ref', sa.Text(), nullable=True),
        sa.Column('web_url', sa.Text(), nullable=True),
        sa.Column('author_name', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),

        sa.Column('stand', sa.Text(), nullable=True),
        sa.Column('schedule_id', sa.Integer(), nullable=True),
        sa.Column('is_notified_start', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('is_completed', sa.Boolean(), nullable=True, server_default='false'),

        sa.Column('allure_report_url', sa.Text(), nullable=True),
        sa.Column('tests_passed', sa.Integer(), nullable=True),
        sa.Column('tests_failed', sa.Integer(), nullable=True),
        sa.Column('duration_sec', sa.Integer(), nullable=True),

        sa.PrimaryKeyConstraint('pipeline_id')
    )

    # Индекс: быстро искать по проекту и времени
    op.create_index(
        'idx_pipeline_states_project_created',
        'pipeline_states',
        ['project_id', 'created_at'],
        unique=False
    )


def downgrade() -> None:
    """Удаляем таблицу и индекс"""
    op.drop_index('idx_pipeline_states_project_created', table_name='pipeline_states')
    op.drop_table('pipeline_states')
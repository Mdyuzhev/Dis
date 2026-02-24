"""create_testit_tables

Revision ID: 979c205c619c
Revises: 61f940cb7af9
Create Date: 2026-02-10 09:54:11.650140

"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '979c205c619c'
down_revision: Union[str, Sequence[str], None] = '61f940cb7af9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Таблица участников
    op.create_table(
        'testit_participants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('author', sa.String(128), nullable=False, unique=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('include_updated', sa.Boolean(), default=True, nullable=False),
        sa.Column('include_deleted', sa.Boolean(), default=False, nullable=False),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_testit_participants_author', 'author'),
        sa.Index('ix_testit_participants_is_active', 'is_active')
    )

    # Конфигурация Test IT
    op.create_table(
        'testit_config',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('scoring_period', sa.String(32), nullable=False, default='daily'),
        sa.Column('stats_time', sa.String(16), nullable=False, default='19:00'),
        sa.Column('created_weight', sa.Float(), default=1.0),
        sa.Column('updated_weight', sa.Float(), default=0.1),
        sa.Column('deleted_weight', sa.Float(), default=0.05),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.PrimaryKeyConstraint('id')
    )

    # Задачи с расписанием
    op.create_table(
        'scheduled_tasks',
        sa.Column('name', sa.String(64), nullable=False, primary_key=True),
        sa.Column('schedule_type', sa.String(32), nullable=False),
        sa.Column('interval_days', sa.Integer(), nullable=False),
        sa.Column('execute_at_hour', sa.Integer(), nullable=False),
        sa.Column('execute_at_minute', sa.Integer(), nullable=False),
        sa.Column('last_execute_at', sa.DateTime()),
        sa.Column('next_execute_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.PrimaryKeyConstraint('name')
    )

    # Вставка конфигурации
    op.execute("""
        INSERT INTO testit_config (
            id, scoring_period, stats_time,
            created_weight, updated_weight, deleted_weight
        ) VALUES (
            1, 'daily', '19:00',
            1.0, 0.1, 0.05
        );
    """)

    # Вставка задачи
    op.execute("""
        INSERT INTO scheduled_tasks (
            name, schedule_type, interval_days,
            execute_at_hour, execute_at_minute, next_execute_at
        ) VALUES (
            'send_daily_testit_stats', 'daily', 1,
            19, 0,
            CURRENT_TIMESTAMP + INTERVAL '1 day'
        )
        ON CONFLICT (name) DO NOTHING;
    """)

    op.execute("""
        INSERT INTO testit_participants (author, is_active, include_updated, include_deleted)
        SELECT DISTINCT author, true, true, false
        FROM testit_events
        WHERE author NOT IN (SELECT author FROM testit_participants)
        ON CONFLICT (author) DO NOTHING;
    """)

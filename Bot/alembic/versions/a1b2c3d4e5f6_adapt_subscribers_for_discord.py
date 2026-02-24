"""Адаптация таблицы subscribers под Discord

- chat_id → channel_id
- thread_message_id → thread_id
- source_type: private/group/group_thread → dm/channel/thread
- Добавлен столбец guild_id
- Обновлены уникальные индексы

Revision ID: a1b2c3d4e5f6
Revises: db99d26300b5
Create Date: 2026-02-24
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'db99d26300b5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Переименование столбцов
    op.alter_column('subscribers', 'chat_id', new_column_name='channel_id')
    op.alter_column('subscribers', 'thread_message_id', new_column_name='thread_id')

    # Добавление guild_id
    op.add_column('subscribers', sa.Column('guild_id', sa.BigInteger(), nullable=True))

    # Обновление source_type значений
    op.execute("UPDATE subscribers SET source_type = 'dm' WHERE source_type = 'private'")
    op.execute("UPDATE subscribers SET source_type = 'channel' WHERE source_type = 'group'")
    op.execute("UPDATE subscribers SET source_type = 'thread' WHERE source_type = 'group_thread'")

    # Удаление старых индексов
    op.drop_index('unique_subscription_group_thread_idx', table_name='subscribers')
    op.drop_index('unique_subscription_private_idx', table_name='subscribers')

    # Создание новых индексов
    op.create_index(
        'unique_subscription_channel_thread_idx',
        'subscribers',
        ['project_id', 'notification_type', sa.text('COALESCE(channel_id, 0)'),
         sa.text('COALESCE(thread_id, 0)'), 'source_type'],
        unique=True,
        postgresql_where=sa.text("source_type IN ('channel', 'thread')")
    )
    op.create_index(
        'unique_subscription_dm_idx',
        'subscribers',
        ['user_id', 'project_id', 'notification_type', sa.text('COALESCE(channel_id, 0)'),
         sa.text('COALESCE(thread_id, 0)'), 'source_type'],
        unique=True,
        postgresql_where=sa.text("source_type = 'dm'")
    )
    op.create_index('idx_guild_id', 'subscribers', ['guild_id'])


def downgrade() -> None:
    # Удаление новых индексов
    op.drop_index('idx_guild_id', table_name='subscribers')
    op.drop_index('unique_subscription_dm_idx', table_name='subscribers')
    op.drop_index('unique_subscription_channel_thread_idx', table_name='subscribers')

    # Восстановление старых индексов
    op.create_index(
        'unique_subscription_group_thread_idx',
        'subscribers',
        ['project_id', 'notification_type', sa.text('COALESCE(chat_id, 0)'),
         sa.text('COALESCE(thread_message_id, 0)'), 'source_type'],
        unique=True,
        postgresql_where=sa.text("source_type IN ('group', 'group_thread')")
    )
    op.create_index(
        'unique_subscription_private_idx',
        'subscribers',
        ['user_id', 'project_id', 'notification_type', sa.text('COALESCE(chat_id, 0)'),
         sa.text('COALESCE(thread_message_id, 0)'), 'source_type'],
        unique=True,
        postgresql_where=sa.text("source_type = 'private'")
    )

    # Откат source_type
    op.execute("UPDATE subscribers SET source_type = 'group_thread' WHERE source_type = 'thread'")
    op.execute("UPDATE subscribers SET source_type = 'group' WHERE source_type = 'channel'")
    op.execute("UPDATE subscribers SET source_type = 'private' WHERE source_type = 'dm'")

    # Удаление guild_id
    op.drop_column('subscribers', 'guild_id')

    # Откат переименования столбцов
    op.alter_column('subscribers', 'thread_id', new_column_name='thread_message_id')
    op.alter_column('subscribers', 'channel_id', new_column_name='chat_id')

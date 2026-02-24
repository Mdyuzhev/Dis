"""add_updated_at_trigger.py

Revision ID: 4b44dfe1bb00
Revises: 4cb18705452d
Create Date: 2026-02-10 17:31:42.537443

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b44dfe1bb00'
down_revision: Union[str, Sequence[str], None] = '4cb18705452d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Создаём функцию-триггер
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW() AT TIME ZONE 'utc';
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Добавляем триггер на таблицу scheduled_tasks
    op.execute("""
        DROP TRIGGER IF EXISTS trigger_update_scheduled_tasks_updated_at ON scheduled_tasks;

        CREATE TRIGGER trigger_update_scheduled_tasks_updated_at
            BEFORE UPDATE ON scheduled_tasks
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade():
    # Удаляем триггер и функцию
    op.execute("DROP TRIGGER IF EXISTS trigger_update_scheduled_tasks_updated_at ON scheduled_tasks;")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")
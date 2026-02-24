"""set include_updated=true and fix initial scheduled_task

Revision ID: fda5f18a6e56
Revises: 979c205c619c
Create Date: 2026-02-10 11:55:15.210920

"""
from datetime import datetime, timedelta
from typing import Sequence, Union

import pytz
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'fda5f18a6e56'
down_revision: Union[str, Sequence[str], None] = '979c205c619c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE testit_participants
        SET include_deleted = true
        WHERE include_deleted = false OR include_deleted IS NULL;
    """)

    op.alter_column(
        'testit_participants',
        'include_deleted',
        server_default='true'
    )

    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER update_testit_participants_updated_at
        BEFORE UPDATE ON testit_participants
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)

    msk_tz = pytz.timezone('Europe/Moscow')
    now_msk = datetime.now(msk_tz)

    if now_msk.hour >= 19:
        next_msk = now_msk.replace(hour=19, minute=0, second=0, microsecond=0) + timedelta(days=1)
    else:
        next_msk = now_msk.replace(hour=19, minute=0, second=0, microsecond=0)

    next_utc = next_msk.astimezone(pytz.utc)

    op.execute(f"""
        INSERT INTO scheduled_tasks (
            name, schedule_type, interval_days,
            execute_at_hour, execute_at_minute, next_execute_at
        ) VALUES (
            'send_daily_testit_stats', 'daily', 1,
            19, 0, '{next_utc.strftime('%Y-%m-%d %H:%M:%S')}'
        )
        ON CONFLICT (name) DO UPDATE SET
            next_execute_at = EXCLUDED.next_execute_at;
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS update_testit_participants_updated_at ON testit_participants;")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")

    op.alter_column(
        'testit_participants',
        'include_deleted',
        server_default=None
    )

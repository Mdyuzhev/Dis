"""alter_scheduled_tasks_tz.py

Revision ID: 4cb18705452d
Revises: cf15f72052d0
Create Date: 2026-02-10 16:57:59.818801

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4cb18705452d'
down_revision: Union[str, Sequence[str], None] = 'cf15f72052d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("""
        ALTER TABLE scheduled_tasks 
        ALTER COLUMN next_execute_at TYPE timestamptz 
        USING next_execute_at AT TIME ZONE 'UTC'
    """)
    op.execute("""
        ALTER TABLE scheduled_tasks 
        ALTER COLUMN last_execute_at TYPE timestamptz 
        USING last_execute_at AT TIME ZONE 'UTC'
    """)

def downgrade():
    op.execute("""
        ALTER TABLE scheduled_tasks 
        ALTER COLUMN next_execute_at TYPE timestamp 
        USING next_execute_at AT TIME ZONE 'UTC'
    """)
    op.execute("""
        ALTER TABLE scheduled_tasks 
        ALTER COLUMN last_execute_at TYPE timestamp 
        USING last_execute_at AT TIME ZONE 'UTC'
    """)

"""convert testit_events.created_at to timestamptz

Revision ID: db99d26300b5
Revises: 4b44dfe1bb00
Create Date: 2026-02-11 13:23:50.024668

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'db99d26300b5'
down_revision: Union[str, Sequence[str], None] = '4b44dfe1bb00'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'testit_events',
        'created_at',
        type_=postgresql.TIMESTAMP(timezone=True),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
        existing_type=postgresql.TIMESTAMP(timezone=False),
        existing_nullable=True,  # или False — смотри по модели
    )

def downgrade() -> None:
    op.alter_column(
        'testit_events',
        'created_at',
        type_=postgresql.TIMESTAMP(timezone=False),
        postgresql_using='created_at AT TIME ZONE \'UTC\'',
        existing_type=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )

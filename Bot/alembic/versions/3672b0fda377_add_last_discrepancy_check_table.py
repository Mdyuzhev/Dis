"""add last_discrepancy_check table

Revision ID: 3672b0fda377
Revises: 6cef01729455
Create Date: 2026-01-23 12:41:07.829274

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3672b0fda377'
down_revision: Union[str, Sequence[str], None] = '6cef01729455'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        'last_discrepancy_check',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('last_id', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), onupdate=sa.text("CURRENT_TIMESTAMP"))
    )

def downgrade():
    op.drop_table('last_discrepancy_check')

"""rename api_football_id to highlightly_id

Revision ID: a2b3c4d5e6f7
Revises: 41f1015e0930
Create Date: 2026-04-12 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = '41f1015e0930'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'matches', 'api_football_id',
        new_column_name='highlightly_id',
        existing_type=sa.Integer(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'matches', 'highlightly_id',
        new_column_name='api_football_id',
        existing_type=sa.Integer(),
        existing_nullable=True,
    )

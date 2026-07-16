"""multi-league support: League model + league_id on teams/matches/long_term_predictions

NOTE: The corresponding schema changes were already applied manually to the
shadow database via docs/multi_league_migration.sql. This revision only records
the alembic state and is meant to be applied with `alembic stamp head`; it does
NOT re-run any DDL (running `alembic upgrade head` would be a no-op anyway).

Revision ID: h2i3j4k5l6m7
Revises: g2h3i4j5k6l7
Create Date: 2026-07-15 15:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h2i3j4k5l6m7'
down_revision: Union[str, None] = 'g2h3i4j5k6l7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Schema already applied manually via docs/multi_league_migration.sql.
    # Record state with: alembic stamp h2i3j4k5l6m7
    pass


def downgrade() -> None:
    pass

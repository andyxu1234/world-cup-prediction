"""add cn_name to players table

球员中文名落在 players 表；中文名集中维护在 cn_mapping(category='player', key=英文球员名)，
由 box-score 同步时自动写回 Player.cn_name。

Revision ID: n6o7p8q9r0s1
Revises: m5n6o7p8q9r0
Create Date: 2026-07-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'n6o7p8q9r0s1'
down_revision: Union[str, None] = 'm5n6o7p8q9r0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column("cn_name", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("players", "cn_name")

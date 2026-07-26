"""fix match_odds.bookmaker_id FK target column

p1q2r3s4t5u6 误将外键指向 bookmakers(id)（自增主键 1..10），
但 match_odds.bookmaker_id 实际存的是 Highlightly 博彩公司 ID（如 319=bet365），
对应 bookmakers.highlightly_bookmaker_id。导致插入赔率时外键冲突 (1452)。

本迁移：先删除错误的 fk_match_odds_bookmaker，再按正确目标列重建。
down_revision = p1q2r3s4t5u6。

Revision ID: q2r3s4t5u6v7
Revises: p1q2r3s4t5u6
Create Date: 2026-07-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'q2r3s4t5u6v7'
down_revision: Union[str, None] = 'p1q2r3s4t5u6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("fk_match_odds_bookmaker", "match_odds", type_="foreignkey")
    op.create_foreign_key(
        "fk_match_odds_bookmaker",
        "match_odds",
        "bookmakers",
        ["bookmaker_id"],
        ["highlightly_bookmaker_id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_match_odds_bookmaker", "match_odds", type_="foreignkey")
    op.create_foreign_key(
        "fk_match_odds_bookmaker",
        "match_odds",
        "bookmakers",
        ["bookmaker_id"],
        ["id"],
    )

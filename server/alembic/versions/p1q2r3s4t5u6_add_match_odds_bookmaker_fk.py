"""add FK from match_odds.bookmaker_id to bookmakers.id

odds.py 中 Bookmaker.odds / MatchOdd.bookmaker 两个 relationship 互相引用，
但 MatchOdd.bookmaker_id 在模型层缺少 ForeignKey 声明，导致 SQLAlchemy 在启动时
无法推导连接条件而报错。本迁移在数据库层补上该外键约束，使 schema 与模型一致。

upgrade() 幂等：因 match_odds 当前为空表、不会产生孤儿行，重复执行风险低；
且 alembic 版本控制保证 upgrade 不会重复跑。

Revision ID: p1q2r3s4t5u6
Revises: o7p8q9r0s1t2
Create Date: 2026-07-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'p1q2r3s4t5u6'
down_revision: Union[str, None] = 'o7p8q9r0s1t2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_match_odds_bookmaker",
        "match_odds",
        "bookmakers",
        ["bookmaker_id"],
        ["highlightly_bookmaker_id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_match_odds_bookmaker", "match_odds", type_="foreignkey")

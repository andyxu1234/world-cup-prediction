"""add polymarket_events table

存储从 Polymarket Gamma API 拉取的赛事（按 '主 vs 客' 分组），
每行可关联本地 matches.id（match_id），用于后续 Polymarket 市场与本地比赛的对接。

升级幂等：表不存在才创建；外键列先建独立索引再建外键（MySQL 要求）。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "s5t6u7v8w9x0"
down_revision: Union[str, None] = "r4s5t6u7v8w9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "polymarket_events" not in tables:
        op.create_table(
            "polymarket_events",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("slug", sa.String(length=255), nullable=False, comment="Polymarket 事件 slug（唯一）"),
            sa.Column("series_id", sa.String(length=50), nullable=False, comment="Polymarket series_id"),
            sa.Column("series_name", sa.String(length=100), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=False, comment="解析后的 主 vs 客 标题"),
            sa.Column("home_team_raw", sa.String(length=150), nullable=True, comment="Polymarket 原始主队名"),
            sa.Column("away_team_raw", sa.String(length=150), nullable=True, comment="Polymarket 原始客队名"),
            sa.Column("home_team_id", sa.Integer(), nullable=True, comment="关联本地球队"),
            sa.Column("away_team_id", sa.Integer(), nullable=True, comment="关联本地球队"),
            sa.Column("start_time", sa.DateTime(), nullable=True, comment="Polymarket 开赛时间(UTC)"),
            sa.Column("match_id", sa.Integer(), nullable=True, comment="关联本地比赛（匹配后回填）"),
            sa.Column("market_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("raw_data", sa.JSON(), nullable=True, comment="Polymarket 原始 match-group 负载"),
            sa.Column("last_synced_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug", name="uk_polymarket_slug"),
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
            comment="Polymarket 赛事表（按 主vs客 分组，可关联本地 matches）",
        )
        # 外键列建独立索引（MySQL 外键需索引支撑）
        op.create_index("ix_pe_match_id", "polymarket_events", ["match_id"])
        op.create_index("ix_pe_home_team_id", "polymarket_events", ["home_team_id"])
        op.create_index("ix_pe_away_team_id", "polymarket_events", ["away_team_id"])
        op.create_index("ix_pe_series_id", "polymarket_events", ["series_id"])
        # 外键
        op.create_foreign_key(
            "fk_pe_match", "polymarket_events", "matches",
            ["match_id"], ["id"], ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_pe_home", "polymarket_events", "teams",
            ["home_team_id"], ["id"], ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_pe_away", "polymarket_events", "teams",
            ["away_team_id"], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "polymarket_events" in tables:
        op.drop_table("polymarket_events")

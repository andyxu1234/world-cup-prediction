"""rebuild polymarket tables: events + markets 两表拆分

需求变更（2026-07-23）：
- 只拉五大联赛+欧冠+欧联、未来7天、胜负平（moneyline 3-way）市场；
- polymarket_events（赛事）与 polymarket_markets（胜负平三条腿）分表；
- events 保留联赛信息/主客队名/开球时间，match_id 供后续匹配本地比赛。

旧 polymarket_events 为试验数据，直接 drop 重建。
升级幂等：先判断表是否存在再操作（MySQL DDL 非事务，中途失败可重跑）。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "t6u7v8w9x0y1"
down_revision: Union[str, None] = "s5t6u7v8w9x0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # 1) 删除依赖旧 events 表的 markets 表（若存在）与旧 events 表
    if "polymarket_markets" in tables:
        op.drop_table("polymarket_markets")
    if "polymarket_events" in tables:
        op.drop_table("polymarket_events")

    # 2) 新 polymarket_events（一行 = 一场比赛）
    op.create_table(
        "polymarket_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pm_event_id", sa.String(length=32), nullable=True, comment="Polymarket 事件 id"),
        sa.Column("slug", sa.String(length=255), nullable=False, comment="Polymarket 事件 slug（唯一）"),
        sa.Column("title", sa.String(length=255), nullable=False, comment="主 vs 客 标题"),
        sa.Column("series_id", sa.String(length=50), nullable=False, comment="Polymarket 联赛 series_id"),
        sa.Column("series_name", sa.String(length=100), nullable=True, comment="联赛名"),
        sa.Column("home_team_raw", sa.String(length=150), nullable=True, comment="Polymarket 主队名"),
        sa.Column("away_team_raw", sa.String(length=150), nullable=True, comment="Polymarket 客队名"),
        sa.Column("game_start_time", sa.DateTime(), nullable=True, comment="开球时间(UTC)"),
        sa.Column("match_id", sa.Integer(), nullable=True, comment="关联本地比赛（后续匹配回填）"),
        sa.Column("market_count", sa.Integer(), nullable=False, server_default=sa.text("0"), comment="胜负平腿数(<=3)"),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uk_pm_event_slug"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        comment="Polymarket 赛事表（未来7天、五大联赛+欧冠+欧联）",
    )
    # 外键列建独立索引（MySQL 外键需索引支撑，避免复用唯一索引）
    op.create_index("ix_pm_event_match_id", "polymarket_events", ["match_id"])
    op.create_index("ix_pm_event_series_id", "polymarket_events", ["series_id"])
    op.create_index("ix_pm_event_start", "polymarket_events", ["game_start_time"])
    op.create_foreign_key(
        "fk_pm_event_match", "polymarket_events", "matches",
        ["match_id"], ["id"], ondelete="SET NULL",
    )

    # 3) polymarket_markets（一行 = 一条腿：home/draw/away）
    op.create_table(
        "polymarket_markets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False, comment="关联 polymarket_events.id"),
        sa.Column("pm_market_id", sa.String(length=32), nullable=False, comment="Polymarket 市场 id（唯一）"),
        sa.Column("condition_id", sa.String(length=80), nullable=True, comment="CLOB conditionId"),
        sa.Column("question", sa.String(length=255), nullable=True, comment="市场问题原文"),
        sa.Column("outcome", sa.String(length=10), nullable=False, comment="home / draw / away"),
        sa.Column("outcome_team", sa.String(length=150), nullable=True, comment="该腿对应队名（draw 为 NULL）"),
        sa.Column("price", sa.Float(), nullable=True, comment="Yes 最新价 = 隐含概率(0~1)"),
        sa.Column("volume", sa.Float(), nullable=True, comment="累计成交量(USD)"),
        sa.Column("liquidity", sa.Float(), nullable=True, comment="当前流动性(USD)"),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pm_market_id", name="uk_pm_market_id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        comment="Polymarket 胜负平市场表（每场比赛最多3条腿）",
    )
    op.create_index("ix_pm_market_event_id", "polymarket_markets", ["event_id"])
    op.create_foreign_key(
        "fk_pm_market_event", "polymarket_markets", "polymarket_events",
        ["event_id"], ["id"], ondelete="CASCADE",
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "polymarket_markets" in tables:
        op.drop_table("polymarket_markets")
    if "polymarket_events" in tables:
        op.drop_table("polymarket_events")

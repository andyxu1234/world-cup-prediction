"""add odds tables: bookmakers + match_odds (prematch odds support)

新建两张表支持赛前赔率存储：
- bookmakers：博彩公司字典（种子写入 10 家高价值盘口，is_active=True）
- match_odds：赔率明细（比赛 → 博彩公司 → 市场 → 选项 → odd 数值）

upgrade() 幂等：表不存在才创建，种子用 INSERT IGNORE 可重复执行，
因此 `alembic upgrade head` 可安全重复运行。

Revision ID: o7p8q9r0s1t2
Revises: n6o7p8q9r0s1
Create Date: 2026-07-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'o7p8q9r0s1t2'
down_revision: Union[str, None] = 'n6o7p8q9r0s1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 保留的 10 家博彩公司（highlightly_bookmaker_id, name）
# 原则：1 家 sharp 锚(Pinnacle) + 高流水主流盘口
BOOKMAKER_SEED = [
    (4, "Pinnacle"),
    (319, "bet365"),
    (11, "Marathonbet"),
    (3, "1xBet"),
    (10, "Betwinner"),
    (66, "SBOBET"),
    (23, "Unibet"),
    (55, "William Hill"),
    (17, "Betway"),
    (9, "Bwin"),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # Step 1: bookmakers 表
    if "bookmakers" not in tables:
        op.create_table(
            "bookmakers",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("highlightly_bookmaker_id", sa.Integer(), nullable=False, comment="Highlightly 博彩公司 ID"),
            sa.Column("name", sa.String(length=100), nullable=False, comment="博彩公司名称"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true(), comment="是否参与赔率拉取"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("highlightly_bookmaker_id", name="uk_bookmaker_hl"),
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
            comment="博彩公司字典表",
        )

    # Step 2: match_odds 表
    if "match_odds" not in tables:
        op.create_table(
            "match_odds",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("match_id", sa.Integer(), nullable=False, comment="关联比赛"),
            sa.Column("bookmaker_id", sa.Integer(), nullable=False, comment="Highlightly bookmakerId（冗余）"),
            sa.Column("bookmaker_name", sa.String(length=100), nullable=False, comment="博彩公司名称"),
            sa.Column("odds_type", sa.Enum("prematch", "live", name="odds_type"), nullable=False, comment="prematch / live"),
            sa.Column("market", sa.String(length=80), nullable=False, comment="市场，如 Full Time Result / Asian Handicap +0.25/-0.25"),
            sa.Column("value", sa.String(length=50), nullable=False, comment="选项，如 Home / Over / 2 : 0"),
            sa.Column("odd", sa.Float(), nullable=False, comment="赔率数值"),
            sa.Column("snapshot_date", sa.Date(), nullable=False, comment="快照日期（每日一个赔率点，用于走势）"),
            sa.Column("fetched_at", sa.DateTime(), server_default=sa.func.now(), comment="抓取时间（精确时刻）"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("match_id", "bookmaker_id", "odds_type", "market", "value", "snapshot_date", name="uk_match_odds"),
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
            comment="比赛赔率明细表（追加式每日快照）",
        )
        # 外键（matches 表已存在）
        op.create_foreign_key("fk_match_odds_match", "match_odds", "matches", ["match_id"], ["id"])
        # snapshot_date 单列索引（走势查询按日期排序）
        op.create_index("ix_match_odds_snapshot_date", "match_odds", ["snapshot_date"])

    # Step 3: 种子博彩公司（幂等）
    for hl_id, name in BOOKMAKER_SEED:
        bind.execute(
            sa.text(
                "INSERT IGNORE INTO bookmakers "
                "(highlightly_bookmaker_id, name, is_active) "
                "VALUES (:hl, :name, 1)"
            ),
            {"hl": hl_id, "name": name},
        )


def downgrade() -> None:
    # 仅删除新建的表（不动其他表）
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "match_odds" in tables:
        op.drop_table("match_odds")
    if "bookmakers" in tables:
        op.drop_table("bookmakers")

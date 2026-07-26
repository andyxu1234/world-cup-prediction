"""multi-league support: League model + league_id on teams/matches/long_term_predictions

原本该 revision 的 DDL 是手动通过 docs/multi_league_migration.sql 应用到影子库的，
upgrade() 为空壳（pass）。但部署到新环境时容易遗漏手动 SQL，导致 leagues 表 /
matches.league_id 等缺失而报错。

现将 upgrade() 改为「幂等自建」：
- 表/列不存在才创建（CREATE TABLE IF NOT EXISTS、检查 information_schema）
- 种子数据用 INSERT IGNORE，可重复执行
- 回填用 WHERE league_id IS NULL，可重复执行

这样 `alembic upgrade head` 即可一次性补齐，无需再手动跑 SQL。

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


LEAGUE_SEED = [
    ('World Cup', '世界杯', 'https://highlightly.net/soccer/images/leagues/1635.png', 1635, 2026, 'cup', 'World', False, 0),
    ('Premier League', '英超', 'https://highlightly.net/soccer/images/leagues/33973.png', 33973, 2026, 'league', 'England', True, 1),
    ('Ligue 1', '法甲', 'https://highlightly.net/soccer/images/leagues/52695.png', 52695, 2026, 'league', 'France', True, 2),
    ('Bundesliga', '德甲', 'https://highlightly.net/soccer/images/leagues/67162.png', 67162, 2026, 'league', 'Germany', True, 3),
    ('Serie A', '意甲', 'https://highlightly.net/soccer/images/leagues/115669.png', 115669, 2026, 'league', 'Italy', True, 4),
    ('La Liga', '西甲', 'https://highlightly.net/soccer/images/leagues/119924.png', 119924, 2026, 'league', 'Spain', True, 5),
    ('UEFA Champions League', '欧冠', 'https://highlightly.net/soccer/images/leagues/2486.png', 2486, 2026, 'cup', 'Europe', True, 6),
    ('UEFA Europa League', '欧联', 'https://highlightly.net/soccer/images/leagues/3337.png', 3337, 2026, 'cup', 'Europe', True, 7),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # Step 1: leagues 表（不存在才建）
    if "leagues" not in tables:
        op.create_table(
            "leagues",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False, comment="英文名"),
            sa.Column("cn_name", sa.String(length=50), nullable=False, comment="中文名"),
            sa.Column("logo", sa.String(length=500), nullable=True, comment="联赛 logo URL"),
            sa.Column("highlightly_league_id", sa.Integer(), nullable=False, comment="Highlightly 对应的 league_id"),
            sa.Column("season", sa.Integer(), nullable=False, comment="当前赛季年份"),
            sa.Column("type", sa.Enum("league", "cup", name="league_type"), nullable=False, comment="联赛 or 杯赛"),
            sa.Column("country", sa.String(length=50), nullable=True, comment="国家/地区"),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true(), comment="是否启用同步"),
            sa.Column("sort_order", sa.Integer(), nullable=True, server_default=sa.text("0"), comment="前端展示排序"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("highlightly_league_id", "season", name="uk_highlightly"),
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
            comment="联赛表",
        )

    # 种子数据（幂等：已存在则跳过）
    for name, cn, logo, hl_id, season, typ, country, active, order in LEAGUE_SEED:
        bind.execute(
            sa.text(
                "INSERT IGNORE INTO leagues "
                "(name, cn_name, logo, highlightly_league_id, season, type, country, is_active, sort_order, created_at) "
                "VALUES (:name, :cn, :logo, :hl, :season, :typ, :country, :active, :order, NOW())"
            ),
            {
                "name": name, "cn": cn, "logo": logo, "hl": hl_id, "season": season,
                "typ": typ, "country": country, "active": active, "order": order,
            },
        )

    # Step 2~5: 给各表加 league_id（不存在才加）+ 回填
    def ensure_league_id(table: str) -> None:
        cols = {c["name"] for c in inspector.get_columns(table)}
        if "league_id" not in cols:
            op.add_column(table, sa.Column("league_id", sa.Integer(), nullable=True, comment="所属联赛 ID"))
            fks = {fk.get("name") for fk in inspector.get_foreign_keys(table)}
            if f"fk_{table}_league" not in fks:
                op.create_foreign_key(f"fk_{table}_league", table, "leagues", ["league_id"], ["id"])
        # 回填：所有现有行归到世界杯
        bind.execute(
            sa.text(
                f"UPDATE {table} SET league_id = (SELECT id FROM leagues WHERE cn_name='世界杯' LIMIT 1) "
                f"WHERE league_id IS NULL"
            )
        )

    ensure_league_id("teams")
    ensure_league_id("matches")
    ensure_league_id("long_term_predictions")


def downgrade() -> None:
    pass

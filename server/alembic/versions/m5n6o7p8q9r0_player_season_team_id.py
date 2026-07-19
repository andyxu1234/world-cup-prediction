"""add team_id to player_season_stats and backfill primary team

team_id 存的是 Highlightly 球队 id（与 match_player_stats.team_id 一致），
需 JOIN teams.highlightly_team_id 才能取到 cn_name，因此本表不建指向 teams.id 的外键。

Revision ID: m5n6o7p8q9r0
Revises: l4m5n6o7p8q9
Create Date: 2026-07-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'm5n6o7p8q9r0'
down_revision: Union[str, None] = 'l4m5n6o7p8q9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("player_season_stats")}
    fk_names = {fk["name"] for fk in insp.get_foreign_keys("player_season_stats")}

    # 清理半应用状态（上次迁移失败可能已建了列 / FK），保证可重跑
    if "fk_player_season_team" in fk_names:
        op.drop_constraint("fk_player_season_team", "player_season_stats", type_="foreignkey")
    if "team_id" in cols:
        op.drop_column("player_season_stats", "team_id")

    # 1. 新增 team_id 列（普通整数，存 Highlightly 球队 id，不建外键）
    op.add_column(
        "player_season_stats",
        sa.Column("team_id", sa.Integer(), nullable=True),
    )

    # 2. 回填：取该球员在本联赛出场场次（distinct match）最多的 team_id 作为主力球队
    bind.execute(
        sa.text(
            """
            UPDATE player_season_stats pss
            SET team_id = (
                SELECT mps.team_id
                FROM match_player_stats mps
                WHERE mps.league_id = pss.league_id
                  AND mps.player_id = pss.player_id
                  AND mps.team_id IS NOT NULL
                GROUP BY mps.team_id
                ORDER BY COUNT(DISTINCT mps.match_id) DESC
                LIMIT 1
            )
            WHERE pss.team_id IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_column("player_season_stats", "team_id")

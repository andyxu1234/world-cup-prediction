"""add snapshot_hour to match_odds for intraday odds movement

把 match_odds 的颗粒度从「每日一个赔率点」细化到「每小时一个赔率点」，
支持更频繁的赔率同步（如每 6 小时一次 → 每天 4 个走势点；每小时一次 → 24 个）。

- 新增列 snapshot_hour (INT, 0-23, NOT NULL, 默认 0)
- 重建唯一索引 uk_match_odds，加入 snapshot_hour：
  (match_id, bookmaker_id, odds_type, market, value, snapshot_date, snapshot_hour)
  同一小时桶内多次拉取 → upsert 覆盖（幂等）；跨小时桶 → 追加走势点。

注意：MySQL 下 match_odds.match_id → matches.id 的外键会复用 uk_match_odds
（因其首列为 match_id）作为支撑索引，因此 drop 该唯一索引前必须先建一个
独立索引 ix_match_odds_match_id 支撑外键，重建后再删掉独立索引。

本迁移为幂等写法，可安全重复执行（应对 DDL 非事务导致的半残状态）。

Revision ID: r4s5t6u7v8w9
Revises: q2r3s4t5u6v7
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'r4s5t6u7v8w9'
down_revision: Union[str, None] = 'q2r3s4t5u6v7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UK_NAME = "uk_match_odds"
UK_COLS = ["match_id", "bookmaker_id", "odds_type", "market", "value", "snapshot_date", "snapshot_hour"]
FK_IDX = "ix_match_odds_match_id"
SNAP_IDX = "ix_match_odds_snapshot"


def upgrade() -> None:
    bind = op.get_bind()

    # 1) 幂等：仅当列不存在时新增（应对半残状态：列已加但索引未重建）
    existing_cols = {r[0] for r in bind.execute(sa.text("SHOW COLUMNS FROM match_odds")).fetchall()}
    if "snapshot_hour" not in existing_cols:
        op.add_column(
            "match_odds",
            sa.Column(
                "snapshot_hour",
                sa.Integer(),
                nullable=False,
                server_default="0",
                comment="快照小时桶(0-23)，每小时一个赔率点，用于日内走势",
            ),
        )

    # 2) 收集当前索引情况
    idx_rows = bind.execute(sa.text("SHOW INDEX FROM match_odds")).fetchall()
    idx_names = {r[2] for r in idx_rows}
    uk_cols = {r[4] for r in idx_rows if r[2] == UK_NAME}

    # 3) 仅当唯一索引尚未包含 snapshot_hour 时重建（含 snapshot_hour 说明已完成）
    if "snapshot_hour" not in uk_cols:
        # 3a) 先建独立索引支撑 match_id 外键，避免 drop 唯一索引时外键无索引可用
        created_fk_idx = False
        if FK_IDX not in idx_names:
            op.create_index(FK_IDX, "match_odds", ["match_id"])
            created_fk_idx = True

        # 3b) 重建唯一索引（含 snapshot_hour）
        op.drop_constraint(UK_NAME, "match_odds", type_="unique")
        op.create_unique_constraint(UK_NAME, "match_odds", UK_COLS)

        # 3c) 新唯一索引仍以 match_id 为前缀，外键可继续复用，删掉临时独立索引保持整洁
        if created_fk_idx and FK_IDX in {r[2] for r in bind.execute(sa.text("SHOW INDEX FROM match_odds")).fetchall()}:
            op.drop_index(FK_IDX, "match_odds")

    # 4) 复合索引 (snapshot_date, snapshot_hour)
    if SNAP_IDX not in idx_names:
        op.create_index(SNAP_IDX, "match_odds", ["snapshot_date", "snapshot_hour"])


def downgrade() -> None:
    bind = op.get_bind()

    if SNAP_IDX in {r[2] for r in bind.execute(sa.text("SHOW INDEX FROM match_odds")).fetchall()}:
        op.drop_index(SNAP_IDX, "match_odds")

    idx_rows = bind.execute(sa.text("SHOW INDEX FROM match_odds")).fetchall()
    idx_names = {r[2] for r in idx_rows}
    uk_cols = {r[4] for r in idx_rows if r[2] == UK_NAME}

    # 只有当唯一索引含 snapshot_hour 时才需要回退成旧 6 列
    if "snapshot_hour" in uk_cols:
        created_fk_idx = False
        if FK_IDX not in idx_names:
            op.create_index(FK_IDX, "match_odds", ["match_id"])
            created_fk_idx = True
        op.drop_constraint(UK_NAME, "match_odds", type_="unique")
        op.create_unique_constraint(
            UK_NAME, "match_odds",
            ["match_id", "bookmaker_id", "odds_type", "market", "value", "snapshot_date"],
        )
        if created_fk_idx and FK_IDX in {r[2] for r in bind.execute(sa.text("SHOW INDEX FROM match_odds")).fetchall()}:
            op.drop_index(FK_IDX, "match_odds")

    existing_cols = {r[0] for r in bind.execute(sa.text("SHOW COLUMNS FROM match_odds")).fetchall()}
    if "snapshot_hour" in existing_cols:
        op.drop_column("match_odds", "snapshot_hour")

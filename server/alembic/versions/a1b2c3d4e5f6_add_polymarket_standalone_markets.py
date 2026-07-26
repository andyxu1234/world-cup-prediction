"""add polymarket_standalone_markets table

Revision ID: a1b2c3d4e5f6
Revises: v8w9x0y1z2a3
Create Date: 2026-07-24 20:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "v8w9x0y1z2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "polymarket_standalone_markets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(255), nullable=False, comment="市场 slug（唯一标识）"),
        sa.Column("condition_id", sa.String(80), nullable=True, comment="CLOB conditionId"),
        sa.Column("question", sa.Text(), nullable=True, comment="市场问题"),
        sa.Column("yes_token_id", sa.String(80), nullable=True, comment="Yes 侧 CLOB token ID"),
        sa.Column("no_token_id", sa.String(80), nullable=True, comment="No 侧 CLOB token ID"),
        sa.Column("yes_price", sa.Float(), nullable=True, comment="Yes 价格 (0-1)"),
        sa.Column("no_price", sa.Float(), nullable=True, comment="No 价格 (0-1)"),
        sa.Column("volume", sa.Float(), nullable=True, comment="累计成交量 (USD)"),
        sa.Column("liquidity", sa.Float(), nullable=True, comment="当前流动性 (USD)"),
        sa.Column("min_order_size", sa.Float(), nullable=True, comment="最小下单量"),
        sa.Column("category", sa.String(200), nullable=True, comment="市场类别"),
        sa.Column("event_slug", sa.String(255), nullable=True, comment="事件 slug"),
        sa.Column("end_date", sa.String(50), nullable=True, comment="结束日期"),
        sa.Column("end_ts", sa.Float(), nullable=True, comment="结束时间戳"),
        sa.Column("is_eligible", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="是否符合 NO farming 条件"),
        sa.Column("no_entry_price", sa.Float(), nullable=True, comment="NO 入场价格"),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True, comment="最后检查时间"),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True, comment="最后同步时间"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_polymarket_standalone_slug", "polymarket_standalone_markets", ["slug"])
    op.create_index("ix_polymarket_standalone_end_ts", "polymarket_standalone_markets", ["end_ts"])
    op.create_index("ix_polymarket_standalone_category", "polymarket_standalone_markets", ["category"])
    op.create_index("ix_polymarket_standalone_is_eligible", "polymarket_standalone_markets", ["is_eligible"])


def downgrade() -> None:
    op.drop_index("ix_polymarket_standalone_is_eligible", table_name="polymarket_standalone_markets")
    op.drop_index("ix_polymarket_standalone_category", table_name="polymarket_standalone_markets")
    op.drop_index("ix_polymarket_standalone_end_ts", table_name="polymarket_standalone_markets")
    op.drop_index("ix_polymarket_standalone_slug", table_name="polymarket_standalone_markets")
    op.drop_table("polymarket_standalone_markets")

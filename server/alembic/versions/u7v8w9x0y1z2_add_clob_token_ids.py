"""add clob_token_id_yes/no to polymarket_markets

两列分别存 moneyline 腿市场 Yes / No 两侧的 CLOB token id，
供后续下单/持仓追踪使用。幂等：已存在则跳过（规避 MySQL DDL 非事务半残）。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "u7v8w9x0y1z2"
down_revision = "t6u7v8w9x0y1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("polymarket_markets")}

    if "clob_token_id_yes" not in cols:
        op.add_column(
            "polymarket_markets",
            sa.Column(
                "clob_token_id_yes",
                sa.String(length=80),
                nullable=True,
                comment="CLOB token id (Yes 侧，下单用)",
            ),
        )
    if "clob_token_id_no" not in cols:
        op.add_column(
            "polymarket_markets",
            sa.Column(
                "clob_token_id_no",
                sa.String(length=80),
                nullable=True,
                comment="CLOB token id (No 侧)",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("polymarket_markets")}

    if "clob_token_id_no" in cols:
        op.drop_column("polymarket_markets", "clob_token_id_no")
    if "clob_token_id_yes" in cols:
        op.drop_column("polymarket_markets", "clob_token_id_yes")

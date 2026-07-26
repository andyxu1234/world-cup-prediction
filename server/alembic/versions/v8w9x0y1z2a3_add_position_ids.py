"""add position_id_yes/no to polymarket_markets

两列分别存 moneyline 腿市场 Yes / No 两侧的 CTF positionId（查持仓用）。
注意与 clob_token_id 不同：negRisk 市场下 positionId != clobTokenId。
幂等：已存在则跳过（规避 MySQL DDL 非事务半残）。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "v8w9x0y1z2a3"
down_revision = "u7v8w9x0y1z2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("polymarket_markets")}

    if "position_id_yes" not in cols:
        op.add_column(
            "polymarket_markets",
            sa.Column(
                "position_id_yes",
                sa.String(length=80),
                nullable=True,
                comment="CTF positionId (Yes 侧，查持仓用)",
            ),
        )
    if "position_id_no" not in cols:
        op.add_column(
            "polymarket_markets",
            sa.Column(
                "position_id_no",
                sa.String(length=80),
                nullable=True,
                comment="CTF positionId (No 侧，查持仓用)",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("polymarket_markets")}

    if "position_id_no" in cols:
        op.drop_column("polymarket_markets", "position_id_no")
    if "position_id_yes" in cols:
        op.drop_column("polymarket_markets", "position_id_yes")

"""add round_translations table and seed data

Revision ID: i1j2k3l4m5n6
Revises: h2i3j4k5l6m7
Create Date: 2026-07-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'i1j2k3l4m5n6'
down_revision: Union[str, None] = 'h2i3j4k5l6m7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 初始轮次映射种子数据（round_key, cn_pattern, is_series）
SEED = [
    ('Group Stage', '小组赛第{n}轮', True),
    ('Regular Season', '常规赛第{n}轮', True),
    ('1st Qualifying Round', '资格赛第1轮', False),
    ('2nd Qualifying Round', '资格赛第2轮', False),
    ('3rd Qualifying Round', '资格赛第3轮', False),
    ('Play-off Round', '附加赛', False),
    ('Round of 32', '三十二强赛', False),
    ('Round of 16', '十六强赛', False),
    ('Quarter-finals', '四分之一决赛', False),
    ('Semi-finals', '半决赛', False),
    ('3rd Place Final', '季军赛', False),
    ('Final', '决赛', False),
]


def upgrade() -> None:
    op.create_table(
        'round_translations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('round_key', sa.String(length=64), nullable=False),
        sa.Column('cn_pattern', sa.String(length=128), nullable=False),
        sa.Column('is_series', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('round_key', name='uk_round_key'),
    )
    op.create_index('ix_round_translations_round_key', 'round_translations', ['round_key'])

    # 种子数据（幂等：已存在则跳过）
    bind = op.get_bind()
    for round_key, cn_pattern, is_series in SEED:
        bind.execute(
            sa.text(
                "INSERT IGNORE INTO round_translations (round_key, cn_pattern, is_series, created_at, updated_at) "
                "VALUES (:rk, :cp, :is, NOW(), NOW())"
            ),
            {"rk": round_key, "cp": cn_pattern, "is": is_series},
        )


def downgrade() -> None:
    op.drop_index('ix_round_translations_round_key', table_name='round_translations')
    op.drop_table('round_translations')

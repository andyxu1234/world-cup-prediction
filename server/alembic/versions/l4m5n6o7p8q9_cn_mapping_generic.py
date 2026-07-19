"""rename round_translations to generic cn_mapping and seed positions

Revision ID: l4m5n6o7p8q9
Revises: k3l4m5n6o7p8
Create Date: 2026-07-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'l4m5n6o7p8q9'
down_revision: Union[str, None] = 'k3l4m5n6o7p8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 新增类别的种子数据（category, key, cn_value, is_series）
POSITION_SEED = [
    ('position', 'Goalkeeper', '守门员', False),
    ('position', 'Defender', '后卫', False),
    ('position', 'Centre-Back', '中后卫', False),
    ('position', 'Left-Back', '左后卫', False),
    ('position', 'Right-Back', '右后卫', False),
    ('position', 'Full-Back', '边后卫', False),
    ('position', 'Wing-Back', '翼卫', False),
    ('position', 'Midfielder', '中场', False),
    ('position', 'Defensive Midfield', '防守型中场', False),
    ('position', 'Central Midfield', '中前卫', False),
    ('position', 'Attacking Midfield', '攻击型中场', False),
    ('position', 'Left Midfield', '左中场', False),
    ('position', 'Right Midfield', '右中场', False),
    ('position', 'Forward', '前锋', False),
    ('position', 'Centre-Forward', '中锋', False),
    ('position', 'Striker', '中锋', False),
    ('position', 'Second Striker', '影子前锋', False),
    ('position', 'Winger', '边锋', False),
    ('position', 'Left Winger', '左边锋', False),
    ('position', 'Right Winger', '右边锋', False),
    ('position', 'Attacker', '前锋', False),
]


def upgrade() -> None:
    # 1. 重命名表
    op.rename_table('round_translations', 'cn_mapping')

    # 2. 先删除旧的 round_key 唯一约束与索引（避免修改列名时冲突）
    op.drop_constraint('uk_round_key', 'cn_mapping', type_='unique')
    op.drop_index('ix_round_translations_round_key', table_name='cn_mapping')

    # 3. 重命名列，使其通用化
    op.alter_column(
        'cn_mapping', 'round_key',
        new_column_name='key', existing_type=sa.String(length=64), nullable=False,
    )
    op.alter_column(
        'cn_mapping', 'cn_pattern',
        new_column_name='cn_value', existing_type=sa.String(length=128), nullable=False,
    )

    # 4. 新增 category 列，默认 'round'（旧数据自动归为 round）
    op.add_column(
        'cn_mapping',
        sa.Column('category', sa.String(length=32), nullable=False, server_default='round'),
    )

    # 5. 建立 (category, key) 唯一约束与索引
    op.create_unique_constraint('uk_cn_mapping_category_key', 'cn_mapping', ['category', 'key'])
    op.create_index('ix_cn_mapping_category_key', 'cn_mapping', ['category', 'key'])

    # 6. 种子：球员位置翻译（幂等）
    bind = op.get_bind()
    for category, key, cn_value, is_series in POSITION_SEED:
        bind.execute(
            sa.text(
                "INSERT IGNORE INTO cn_mapping "
                "(category, `key`, cn_value, is_series, created_at, updated_at) "
                "VALUES (:cat, :k, :v, :is, NOW(), NOW())"
            ),
            {"cat": category, "k": key, "v": cn_value, "is": is_series},
        )


def downgrade() -> None:
    # 1. 删除新增的种子数据（仅删除 position 类别，保留 round）
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM cn_mapping WHERE category = 'position'"))

    # 2. 还原唯一约束与索引
    op.drop_index('ix_cn_mapping_category_key', table_name='cn_mapping')
    op.drop_constraint('uk_cn_mapping_category_key', 'cn_mapping', type_='unique')
    op.create_index('ix_round_translations_round_key', 'cn_mapping', ['key'])
    op.create_unique_constraint('uk_round_key', 'cn_mapping', ['key'])

    # 3. 删除 category 列
    op.drop_column('cn_mapping', 'category')

    # 4. 还原列名
    op.alter_column(
        'cn_mapping', 'key',
        new_column_name='round_key', existing_type=sa.String(length=64), nullable=False,
    )
    op.alter_column(
        'cn_mapping', 'cn_value',
        new_column_name='cn_pattern', existing_type=sa.String(length=128), nullable=False,
    )

    # 5. 还原表名
    op.rename_table('cn_mapping', 'round_translations')

"""add cn_name to teams

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-13 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('teams', sa.Column('cn_name', sa.String(50), nullable=True))

    # 填充中文队名（与 Highlightly name 对应）
    op.execute("""
        UPDATE teams SET cn_name = CASE name
            WHEN 'Canada' THEN '加拿大'
            WHEN 'Mexico' THEN '墨西哥'
            WHEN 'USA' THEN '美国'
            WHEN 'England' THEN '英格兰'
            WHEN 'France' THEN '法国'
            WHEN 'Croatia' THEN '克罗地亚'
            WHEN 'Portugal' THEN '葡萄牙'
            WHEN 'Norway' THEN '挪威'
            WHEN 'Germany' THEN '德国'
            WHEN 'Netherlands' THEN '荷兰'
            WHEN 'Austria' THEN '奥地利'
            WHEN 'Belgium' THEN '比利时'
            WHEN 'Scotland' THEN '苏格兰'
            WHEN 'Spain' THEN '西班牙'
            WHEN 'Sweden' THEN '瑞典'
            WHEN 'Turkey' THEN '土耳其'
            WHEN 'Bosnia and Herzegovina' THEN '波黑'
            WHEN 'Bosnia & Herzegovina' THEN '波黑'
            WHEN 'Czechia' THEN '捷克'
            WHEN 'Czech Republic' THEN '捷克'
            WHEN 'Switzerland' THEN '瑞士'
            WHEN 'Argentina' THEN '阿根廷'
            WHEN 'Brazil' THEN '巴西'
            WHEN 'Ecuador' THEN '厄瓜多尔'
            WHEN 'Uruguay' THEN '乌拉圭'
            WHEN 'Colombia' THEN '哥伦比亚'
            WHEN 'Paraguay' THEN '巴拉圭'
            WHEN 'Japan' THEN '日本'
            WHEN 'South Korea' THEN '韩国'
            WHEN 'Korea Republic' THEN '韩国'
            WHEN 'Iran' THEN '伊朗'
            WHEN 'IR Iran' THEN '伊朗'
            WHEN 'Saudi Arabia' THEN '沙特阿拉伯'
            WHEN 'Qatar' THEN '卡塔尔'
            WHEN 'Iraq' THEN '伊拉克'
            WHEN 'Jordan' THEN '约旦'
            WHEN 'Australia' THEN '澳大利亚'
            WHEN 'Uzbekistan' THEN '乌兹别克斯坦'
            WHEN 'Morocco' THEN '摩洛哥'
            WHEN 'Tunisia' THEN '突尼斯'
            WHEN 'Egypt' THEN '埃及'
            WHEN 'Algeria' THEN '阿尔及利亚'
            WHEN 'Ghana' THEN '加纳'
            WHEN 'Cape Verde' THEN '佛得角'
            WHEN 'South Africa' THEN '南非'
            WHEN 'Ivory Coast' THEN '科特迪瓦'
            WHEN "Côte d'Ivoire" THEN '科特迪瓦'
            WHEN 'DR Congo' THEN '刚果(金)'
            WHEN 'Congo DR' THEN '刚果(金)'
            WHEN 'Senegal' THEN '塞内加尔'
            WHEN 'Curacao' THEN '库拉索'
            WHEN 'Curaçao' THEN '库拉索'
            WHEN 'Haiti' THEN '海地'
            WHEN 'Panama' THEN '巴拿马'
            WHEN 'New Zealand' THEN '新西兰'
            ELSE NULL
        END
    """)


def downgrade() -> None:
    op.drop_column('teams', 'cn_name')

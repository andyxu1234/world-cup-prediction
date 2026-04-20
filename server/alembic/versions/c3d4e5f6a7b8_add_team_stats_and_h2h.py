"""add team stats and h2h tables

Revision ID: c3d4e5f6a7b8
Revises: a2b3c4d5e6f7
Create Date: 2026-04-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 添加 teams 表新字段
    op.add_column('teams', sa.Column('highlightly_team_id', sa.Integer(), nullable=True))
    op.add_column('teams', sa.Column('season_stats', sa.JSON(), nullable=True))
    op.add_column('teams', sa.Column('recent_form', sa.JSON(), nullable=True))
    op.create_unique_constraint('uq_teams_highlightly_team_id', 'teams', ['highlightly_team_id'])

    # 创建 head_to_head 表
    op.create_table('head_to_head',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('team_one_id', sa.Integer(), nullable=False),
        sa.Column('team_two_id', sa.Integer(), nullable=False),
        sa.Column('matches', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['team_one_id'], ['teams.id'], ),
        sa.ForeignKeyConstraint(['team_two_id'], ['teams.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_one_id', 'team_two_id', name='uk_h2h_teams')
    )


def downgrade() -> None:
    op.drop_table('head_to_head')
    op.drop_constraint('uq_teams_highlightly_team_id', 'teams', type_='unique')
    op.drop_column('teams', 'recent_form')
    op.drop_column('teams', 'season_stats')
    op.drop_column('teams', 'highlightly_team_id')

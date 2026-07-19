"""add match_player_stats table for player rankings

Revision ID: j2k3l4m5n6o7
Revises: i1j2k3l4m5n6
Create Date: 2026-07-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'j2k3l4m5n6o7'
down_revision: Union[str, None] = 'i1j2k3l4m5n6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'match_player_stats',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('match_id', sa.Integer(), nullable=False),
        sa.Column('league_id', sa.Integer(), nullable=False),
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('player_name', sa.String(length=120), nullable=False),
        sa.Column('player_logo', sa.String(length=500), nullable=True),
        sa.Column('team_id', sa.Integer(), nullable=True),
        sa.Column('team_name', sa.String(length=120), nullable=True),
        sa.Column('team_logo', sa.String(length=500), nullable=True),
        sa.Column('position', sa.String(length=30), nullable=True),
        sa.Column('shirt_number', sa.Integer(), nullable=True),
        sa.Column('is_captain', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_substitute', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('minutes_played', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('goals', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('assists', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('yellow_cards', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('red_cards', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('second_yellow', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('shots_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('shots_on_target', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('shots_off_target', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('match_id', 'player_id', name='uk_match_player'),
    )
    op.create_index('ix_match_player_stats_league_id', 'match_player_stats', ['league_id'])
    op.create_index('ix_match_player_stats_player_id', 'match_player_stats', ['player_id'])


def downgrade() -> None:
    op.drop_index('ix_match_player_stats_player_id', table_name='match_player_stats')
    op.drop_index('ix_match_player_stats_league_id', table_name='match_player_stats')
    op.drop_table('match_player_stats')

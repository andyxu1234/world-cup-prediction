"""add data detail tables: league_standings, players, player_season_stats

Revision ID: k3l4m5n6o7p8
Revises: j2k3l4m5n6o7
Create Date: 2026-07-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'k3l4m5n6o7p8'
down_revision: Union[str, None] = 'j2k3l4m5n6o7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'league_standings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('league_id', sa.Integer(), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('group_name', sa.String(length=60), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=True),
        sa.Column('highlightly_team_id', sa.Integer(), nullable=True),
        sa.Column('team_name', sa.String(length=120), nullable=True),
        sa.Column('team_logo', sa.String(length=500), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('played', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('won', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('draw', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('lost', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('goals_for', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('goals_against', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('goal_diff', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('points', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('home_won', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('home_draw', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('home_lost', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('home_gf', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('home_ga', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('away_won', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('away_draw', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('away_lost', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('away_gf', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('away_ga', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('fetched_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['league_id'], ['leagues.id'], ),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('league_id', 'season', 'group_name', 'highlightly_team_id', name='uk_league_standing'),
    )
    op.create_index('ix_league_standings_league_id', 'league_standings', ['league_id'])
    op.create_index('ix_league_standings_team_id', 'league_standings', ['team_id'])

    op.create_table(
        'players',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('full_name', sa.String(length=120), nullable=True),
        sa.Column('logo', sa.String(length=500), nullable=True),
        sa.Column('position_main', sa.String(length=60), nullable=True),
        sa.Column('position_secondary', sa.String(length=120), nullable=True),
        sa.Column('height', sa.String(length=20), nullable=True),
        sa.Column('citizenship', sa.String(length=60), nullable=True),
        sa.Column('birth_date', sa.String(length=40), nullable=True),
        sa.Column('club', sa.String(length=120), nullable=True),
        sa.Column('fetched_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'player_season_stats',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('league_id', sa.Integer(), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('player_name', sa.String(length=120), nullable=False),
        sa.Column('player_logo', sa.String(length=500), nullable=True),
        sa.Column('team_name', sa.String(length=120), nullable=True),
        sa.Column('team_logo', sa.String(length=500), nullable=True),
        sa.Column('position', sa.String(length=30), nullable=True),
        sa.Column('games_played', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('minutes_played', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('goals', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('assists', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('yellow_cards', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('red_cards', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('second_yellow', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('shots_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('shots_on_target', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('fetched_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['player_id'], ['players.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('league_id', 'season', 'player_id', name='uk_player_season'),
    )
    op.create_index('ix_player_season_stats_league_id', 'player_season_stats', ['league_id'])
    op.create_index('ix_player_season_stats_player_id', 'player_season_stats', ['player_id'])


def downgrade() -> None:
    op.drop_index('ix_player_season_stats_player_id', table_name='player_season_stats')
    op.drop_index('ix_player_season_stats_league_id', table_name='player_season_stats')
    op.drop_table('player_season_stats')
    op.drop_table('players')
    op.drop_index('ix_league_standings_team_id', table_name='league_standings')
    op.drop_index('ix_league_standings_league_id', table_name='league_standings')
    op.drop_table('league_standings')

"""add alt_score and short_summary to prediction_summaries

Revision ID: f1g2h3i4j5k6
Revises: e1f2g3h4i5j6
Create Date: 2026-04-14 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f1g2h3i4j5k6'
down_revision: Union[str, None] = 'e1f2g3h4i5j6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('prediction_summaries', sa.Column('score_alt_home', sa.Integer(), nullable=True))
    op.add_column('prediction_summaries', sa.Column('score_alt_away', sa.Integer(), nullable=True))
    op.add_column('prediction_summaries', sa.Column('short_summary', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('prediction_summaries', 'short_summary')
    op.drop_column('prediction_summaries', 'score_alt_away')
    op.drop_column('prediction_summaries', 'score_alt_home')

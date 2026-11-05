"""add api_usage column to extractions

Revision ID: d4e9b2f7c831
Revises: c3d8f1a9b2e4
Create Date: 2026-11-05 12:00:00.000000

Dedicated billing/cost column, separate from confidence (extraction quality)
and raw_data (item output). Nullable — existing rows and cached extractions
are unaffected; the column populates on the next fresh extraction run.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd4e9b2f7c831'
down_revision: Union[str, None] = 'c3d8f1a9b2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('extractions', sa.Column('api_usage', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('extractions', 'api_usage')

"""add finish_status/door_style_status field provenance columns

Revision ID: c3d8f1a9b2e4
Revises: aa52e7a827e8
Create Date: 2026-11-04 01:00:00.000000

Purely additive, nullable columns — existing rows are unaffected.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d8f1a9b2e4'
down_revision: Union[str, None] = 'aa52e7a827e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('canonical_line_items', sa.Column('finish_status', sa.String(), nullable=True))
    op.add_column('canonical_line_items', sa.Column('door_style_status', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('canonical_line_items', 'door_style_status')
    op.drop_column('canonical_line_items', 'finish_status')

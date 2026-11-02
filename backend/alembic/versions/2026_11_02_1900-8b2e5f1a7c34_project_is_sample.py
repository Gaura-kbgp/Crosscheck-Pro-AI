"""project_is_sample

Revision ID: 8b2e5f1a7c34
Revises: 4f8a1c6d9e23
Create Date: 2026-11-02 19:00:00.000000+00:00

Testing review P2-1: every new account should see a pre-checked sample
project so the first screen after signup is never empty. Purely additive,
non-null with a default so existing rows are unaffected.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b2e5f1a7c34'
down_revision: Union[str, None] = '4f8a1c6d9e23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('is_sample', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('projects', 'is_sample')

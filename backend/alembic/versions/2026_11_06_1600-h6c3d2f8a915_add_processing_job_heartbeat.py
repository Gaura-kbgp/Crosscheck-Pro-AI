"""Add last_heartbeat_at to processing_jobs

Revision ID: h6c3d2f8a915
Revises: f3a1d9e2b847
Create Date: 2026-11-06 16:00:00.000000+00:00

Adds last_heartbeat_at (nullable TIMESTAMP WITH TIME ZONE) to processing_jobs.
The running pipeline updates this column every 30 s. Startup recovery uses it to
distinguish jobs abandoned by a dead server process (stale heartbeat) from jobs
belonging to another currently running instance (fresh heartbeat).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'h6c3d2f8a915'
down_revision: Union[str, None] = 'f3a1d9e2b847'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'processing_jobs',
        sa.Column('last_heartbeat_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('processing_jobs', 'last_heartbeat_at')

"""Drop unique constraint on processing_jobs.project_id

Revision ID: f3a1d9e2b847
Revises: e7a3c9d1f8b2
Create Date: 2026-11-06 15:00:00.000000+00:00

The original migration (bcea0ad4e0af) created processing_jobs with a
UniqueConstraint on project_id, restricting each project to exactly one job
row. This prevents Rescan after a COMPLETED or FAILED run. Multiple sequential
jobs per project are correct behaviour; active-job deduplication is enforced in
application code (start_processing checks for non-terminal jobs before inserting).
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f3a1d9e2b847'
down_revision: Union[str, None] = 'e7a3c9d1f8b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the unique constraint if it exists (may have been removed manually on some instances).
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'processing_jobs'
                  AND constraint_name = 'processing_jobs_project_id_key'
                  AND constraint_type = 'UNIQUE'
            ) THEN
                ALTER TABLE processing_jobs DROP CONSTRAINT processing_jobs_project_id_key;
            END IF;
        END$$;
    """)


def downgrade() -> None:
    op.create_unique_constraint('processing_jobs_project_id_key', 'processing_jobs', ['project_id'])

"""add OUT_OF_SCOPE match group status

Revision ID: aa52e7a827e8
Revises: 8b2e5f1a7c34
Create Date: 2026-11-04 00:01:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'aa52e7a827e8'
down_revision = '8b2e5f1a7c34'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Postgres requires ADD VALUE to run outside a transaction block.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE matchgroupstatus ADD VALUE IF NOT EXISTS 'OUT_OF_SCOPE'")


def downgrade() -> None:
    # Postgres cannot drop a single enum value; no-op. A project with an
    # OUT_OF_SCOPE match group cannot be rolled back further without a
    # manual data migration (recompute via CrossCheckService.process_project).
    pass

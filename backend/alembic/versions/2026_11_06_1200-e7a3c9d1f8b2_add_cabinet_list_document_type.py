"""add CABINET_LIST document type, rename order_item_id -> cabinet_list_item_id

Revision ID: e7a3c9d1f8b2
Revises: d4e9b2f7c831
Create Date: 2026-11-06 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7a3c9d1f8b2'
down_revision = 'd4e9b2f7c831'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add CABINET_LIST to documenttype enum — must be outside a transaction block.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'CABINET_LIST'")

    # 2. Rename match_groups.order_item_id -> cabinet_list_item_id.
    op.alter_column("match_groups", "order_item_id", new_column_name="cabinet_list_item_id")

    # 3. Rename the FK constraint (auto-named by SQLAlchemy Phase 5 migration).
    op.execute(
        "ALTER TABLE match_groups RENAME CONSTRAINT "
        "match_groups_order_item_id_fkey TO match_groups_cabinet_list_item_id_fkey"
    )


def downgrade() -> None:
    # Reverse column and constraint rename.
    op.execute(
        "ALTER TABLE match_groups RENAME CONSTRAINT "
        "match_groups_cabinet_list_item_id_fkey TO match_groups_order_item_id_fkey"
    )
    op.alter_column("match_groups", "cabinet_list_item_id", new_column_name="order_item_id")
    # Postgres cannot drop an enum value — CABINET_LIST enum downgrade is a no-op.

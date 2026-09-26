"""manufacturer_settings_management

Revision ID: 8a2d4f6b9c17
Revises: 3f7c9b2e6a41
Create Date: 2026-09-25 11:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8a2d4f6b9c17'
down_revision: Union[str, None] = '3f7c9b2e6a41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('manufacturers', sa.Column('is_global', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('manufacturers', sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))
    op.add_column('manufacturers', sa.Column('updated_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))

    op.add_column('manufacturer_code_dictionary', sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))
    op.add_column('manufacturer_code_dictionary', sa.Column('updated_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))

    # Prevent duplicate manufacturer+code entries (Step 1 §5 validation
    # requirement); safe to add — no existing duplicates in current data.
    op.create_unique_constraint(
        'uq_manufacturer_code_normalized', 'manufacturer_code_dictionary',
        ['manufacturer_id', 'normalized_code'],
    )

    # Mark any pre-existing manufacturer with organization_id IS NULL as
    # global, for consistency with the new explicit flag.
    op.execute("UPDATE manufacturers SET is_global = true WHERE organization_id IS NULL")


def downgrade() -> None:
    op.drop_constraint('uq_manufacturer_code_normalized', 'manufacturer_code_dictionary', type_='unique')
    op.drop_column('manufacturer_code_dictionary', 'updated_by')
    op.drop_column('manufacturer_code_dictionary', 'created_by')
    op.drop_column('manufacturers', 'updated_by')
    op.drop_column('manufacturers', 'created_by')
    op.drop_column('manufacturers', 'is_global')

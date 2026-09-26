"""cabinet_code_intelligence

Revision ID: 3f7c9b2e6a41
Revises: 789b11c83021
Create Date: 2026-09-25 10:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '3f7c9b2e6a41'
down_revision: Union[str, None] = '789b11c83021'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Manufacturer identity — global by default (organization_id NULL); a
    # manufacturer entry belongs to a tenant only when explicitly scoped.
    op.create_table(
        'manufacturers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Manufacturer SKU/code catalog. category reuses the existing itemcategory
    # enum type (already created by canonical_line_items.item_category) rather
    # than creating a duplicate type.
    op.create_table(
        'manufacturer_code_dictionary',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('manufacturer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('manufacturers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('normalized_code', sa.String(), nullable=False),
        sa.Column('category', postgresql.ENUM(name='itemcategory', create_type=False), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('alias_group', sa.String(), nullable=True),
        sa.Column('is_primary_alias', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('effective_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('effective_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_document_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('source_version', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_manufacturer_code_dictionary_manufacturer_id', 'manufacturer_code_dictionary', ['manufacturer_id'])
    op.create_index('ix_manufacturer_code_dictionary_normalized_code', 'manufacturer_code_dictionary', ['normalized_code'])
    op.create_index('ix_manufacturer_code_dictionary_alias_group', 'manufacturer_code_dictionary', ['alias_group'])

    # Nullable so every existing project is unaffected and falls through to
    # the existing generic ItemClassifier unchanged (backward compatibility).
    op.add_column('projects', sa.Column('manufacturer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('manufacturers.id', ondelete='SET NULL'), nullable=True))

    # Additive: full CabinetCodeDecision audit trail, alongside (never
    # replacing) the existing item_category/category_confidence columns.
    op.add_column('canonical_line_items', sa.Column('cabinet_classification', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('canonical_line_items', 'cabinet_classification')
    op.drop_column('projects', 'manufacturer_id')
    op.drop_index('ix_manufacturer_code_dictionary_alias_group', table_name='manufacturer_code_dictionary')
    op.drop_index('ix_manufacturer_code_dictionary_normalized_code', table_name='manufacturer_code_dictionary')
    op.drop_index('ix_manufacturer_code_dictionary_manufacturer_id', table_name='manufacturer_code_dictionary')
    op.drop_table('manufacturer_code_dictionary')
    op.drop_table('manufacturers')

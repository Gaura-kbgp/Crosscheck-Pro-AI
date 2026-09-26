"""step3_performance_indexes

Revision ID: 3a7b5f9e2c81
Revises: 9c4f7e2a1d63
Create Date: 2026-09-25 14:00:00.000000+00:00

Step 3 production-readiness audit: several foreign-key columns introduced by
Cabinet Code Intelligence / Manufacturer Settings / Spec Book work had no
explicit index (Postgres does not auto-index FK columns), and
CanonicalLineItem.normalized_sku — a natural SKU lookup/join key — had none
either. All additions here are purely additive (CREATE INDEX), safe on
existing data, and reversible.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '3a7b5f9e2c81'
down_revision: Union[str, None] = '9c4f7e2a1d63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_manufacturers_organization_id', 'manufacturers', ['organization_id'])
    op.create_index('ix_manufacturer_spec_books_organization_id', 'manufacturer_spec_books', ['organization_id'])
    op.create_index('ix_nkba_reference_documents_organization_id', 'nkba_reference_documents', ['organization_id'])
    op.create_index('ix_projects_manufacturer_id', 'projects', ['manufacturer_id'])
    op.create_index('ix_canonical_line_items_normalized_sku', 'canonical_line_items', ['normalized_sku'])


def downgrade() -> None:
    op.drop_index('ix_canonical_line_items_normalized_sku', table_name='canonical_line_items')
    op.drop_index('ix_projects_manufacturer_id', table_name='projects')
    op.drop_index('ix_nkba_reference_documents_organization_id', table_name='nkba_reference_documents')
    op.drop_index('ix_manufacturer_spec_books_organization_id', table_name='manufacturer_spec_books')
    op.drop_index('ix_manufacturers_organization_id', table_name='manufacturers')

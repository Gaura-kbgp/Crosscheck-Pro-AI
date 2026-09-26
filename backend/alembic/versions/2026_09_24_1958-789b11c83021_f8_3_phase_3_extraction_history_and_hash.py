"""f8_3_phase_3_extraction_history_and_hash

Revision ID: 789b11c83021
Revises: a1f9e2b3c4d5
Create Date: 2026-09-24 19:58:33.917977+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '789b11c83021'
down_revision: Union[str, None] = 'a1f9e2b3c4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Document identity for extraction idempotency (§22)
    op.add_column('documents', sa.Column('document_hash', sa.String(), nullable=True))

    # Extraction becomes one-row-per-attempt instead of 1:1 with Document, so
    # reprocessing never destroys prior extraction evidence (§27).
    op.drop_constraint('extractions_document_id_key', 'extractions', type_='unique')
    op.create_index('ix_extractions_document_id', 'extractions', ['document_id'])
    op.add_column('extractions', sa.Column('attempt', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('extractions', sa.Column('is_latest', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('extractions', sa.Column('extraction_version', sa.String(), nullable=True))
    op.add_column('extractions', sa.Column('document_hash', sa.String(), nullable=True))

def downgrade() -> None:
    op.drop_column('extractions', 'document_hash')
    op.drop_column('extractions', 'extraction_version')
    op.drop_column('extractions', 'is_latest')
    op.drop_column('extractions', 'attempt')
    op.drop_index('ix_extractions_document_id', table_name='extractions')
    op.create_unique_constraint('extractions_document_id_key', 'extractions', ['document_id'])
    op.drop_column('documents', 'document_hash')

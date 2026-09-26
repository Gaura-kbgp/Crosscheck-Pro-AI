"""nkba_reference_documents

Revision ID: 9c4f7e2a1d63
Revises: 6d3e8f1a4b52
Create Date: 2026-09-25 13:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9c4f7e2a1d63'
down_revision: Union[str, None] = '6d3e8f1a4b52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'nkba_reference_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True),
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('original_filename', sa.String(), nullable=False),
        sa.Column('storage_path', sa.String(), nullable=False, unique=True),
        sa.Column('mime_type', sa.String(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('nkba_reference_documents')

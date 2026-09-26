"""manufacturer_spec_books

Revision ID: 6d3e8f1a4b52
Revises: 8a2d4f6b9c17
Create Date: 2026-09-25 12:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '6d3e8f1a4b52'
down_revision: Union[str, None] = '8a2d4f6b9c17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE specbookstatus AS ENUM ('UPLOADED', 'EXTRACTING', 'EXTRACTED', 'FAILED');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE specbookrowstatus AS ENUM ('PENDING', 'APPROVED', 'REJECTED');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    specbookstatus = postgresql.ENUM('UPLOADED', 'EXTRACTING', 'EXTRACTED', 'FAILED', name='specbookstatus', create_type=False)
    specbookrowstatus = postgresql.ENUM('PENDING', 'APPROVED', 'REJECTED', name='specbookrowstatus', create_type=False)

    op.create_table(
        'manufacturer_spec_books',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('manufacturer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('manufacturers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('original_filename', sa.String(), nullable=False),
        sa.Column('storage_path', sa.String(), nullable=False, unique=True),
        sa.Column('mime_type', sa.String(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('status', specbookstatus, nullable=False, server_default='UPLOADED'),
        sa.Column('source_version', sa.String(), nullable=True),
        sa.Column('error', sa.JSON(), nullable=True),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_manufacturer_spec_books_manufacturer_id', 'manufacturer_spec_books', ['manufacturer_id'])

    op.create_table(
        'manufacturer_spec_book_rows',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('spec_book_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('manufacturer_spec_books.id', ondelete='CASCADE'), nullable=False),
        sa.Column('manufacturer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('manufacturers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('raw_code', sa.String(), nullable=False),
        sa.Column('normalized_code', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('category', postgresql.ENUM(name='itemcategory', create_type=False), nullable=False, server_default='UNKNOWN'),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('source_text', sa.String(), nullable=True),
        sa.Column('status', specbookrowstatus, nullable=False, server_default='PENDING'),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_manufacturer_spec_book_rows_spec_book_id', 'manufacturer_spec_book_rows', ['spec_book_id'])
    op.create_index('ix_manufacturer_spec_book_rows_manufacturer_id', 'manufacturer_spec_book_rows', ['manufacturer_id'])
    op.create_index('ix_manufacturer_spec_book_rows_normalized_code', 'manufacturer_spec_book_rows', ['normalized_code'])


def downgrade() -> None:
    op.drop_index('ix_manufacturer_spec_book_rows_normalized_code', table_name='manufacturer_spec_book_rows')
    op.drop_index('ix_manufacturer_spec_book_rows_manufacturer_id', table_name='manufacturer_spec_book_rows')
    op.drop_index('ix_manufacturer_spec_book_rows_spec_book_id', table_name='manufacturer_spec_book_rows')
    op.drop_table('manufacturer_spec_book_rows')
    op.drop_index('ix_manufacturer_spec_books_manufacturer_id', table_name='manufacturer_spec_books')
    op.drop_table('manufacturer_spec_books')
    op.execute("DROP TYPE specbookrowstatus")
    op.execute("DROP TYPE specbookstatus")

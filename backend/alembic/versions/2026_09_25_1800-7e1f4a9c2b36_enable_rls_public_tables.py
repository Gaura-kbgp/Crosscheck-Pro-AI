"""enable_rls_public_tables

Revision ID: 7e1f4a9c2b36
Revises: 3a7b5f9e2c81
Create Date: 2026-09-25 18:00:00.000000+00:00

Security fix: Supabase's linter flags any public-schema table without Row
Level Security (RLS) enabled, because Supabase auto-exposes every public
table through its PostgREST API to the anon/authenticated roles unless RLS
blocks it. This backend connects as the `postgres` role, which has
BYPASSRLS=true, so enabling RLS here has zero effect on this application's
own behavior. No policies are added: nothing in this codebase uses the
Supabase anon/authenticated PostgREST path (the frontend talks only to this
FastAPI backend), so default-deny (RLS enabled, no policies) is the correct
posture and fully closes the exposure the advisory warns about.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '7e1f4a9c2b36'
down_revision: Union[str, None] = '3a7b5f9e2c81'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = [
    'alembic_version',
    'audit_logs',
    'canonical_line_items',
    'discrepancies',
    'documents',
    'extractions',
    'human_reviews',
    'manufacturer_code_dictionary',
    'manufacturer_spec_book_rows',
    'manufacturer_spec_books',
    'manufacturers',
    'match_groups',
    'nkba_reference_documents',
    'organizations',
    'processing_jobs',
    'projects',
    'reports',
    'users',
]


def upgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY;')


def downgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE public."{table}" DISABLE ROW LEVEL SECURITY;')

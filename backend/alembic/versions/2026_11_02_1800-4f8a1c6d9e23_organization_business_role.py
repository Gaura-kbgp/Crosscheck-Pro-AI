"""organization_business_role

Revision ID: 4f8a1c6d9e23
Revises: 7e1f4a9c2b36
Create Date: 2026-11-02 18:00:00.000000+00:00

Testing review P1-4: signup currently has no way to capture which side of
the cabinet-order workflow the signing-up organization represents (Designer
/ Dealer / Manufacturer). Adds a nullable, purely additive column — existing
organizations are unaffected and simply have no business_role until set.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '4f8a1c6d9e23'
down_revision: Union[str, None] = '7e1f4a9c2b36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE businessrole AS ENUM ('DESIGNER', 'DEALER', 'MANUFACTURER');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    businessrole = postgresql.ENUM('DESIGNER', 'DEALER', 'MANUFACTURER', name='businessrole', create_type=False)
    op.add_column('organizations', sa.Column('business_role', businessrole, nullable=True))


def downgrade() -> None:
    op.drop_column('organizations', 'business_role')
    op.execute("DROP TYPE IF EXISTS businessrole;")

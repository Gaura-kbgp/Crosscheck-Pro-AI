"""auth_custom_fields

Revision ID: a1f9e2b3c4d5
Revises: e9b41a87c123
Create Date: 2026-09-17 08:30:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f9e2b3c4d5'
down_revision: Union[str, None] = 'e9b41a87c123'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new auth columns to users table
    op.add_column('users', sa.Column('full_name', sa.String(), nullable=True))
    op.add_column('users', sa.Column('password_hash', sa.String(), nullable=True))
    op.add_column('users', sa.Column('is_verified', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('users', sa.Column('verification_token', sa.String(), nullable=True))
    op.add_column('users', sa.Column('verification_token_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('reset_token', sa.String(), nullable=True))
    op.add_column('users', sa.Column('reset_token_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('google_id', sa.String(), nullable=True))

    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=False)
    op.create_index(op.f('ix_users_verification_token'), 'users', ['verification_token'], unique=False)
    op.create_index(op.f('ix_users_reset_token'), 'users', ['reset_token'], unique=False)
    op.create_index(op.f('ix_users_google_id'), 'users', ['google_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_google_id'), table_name='users')
    op.drop_index(op.f('ix_users_reset_token'), table_name='users')
    op.drop_index(op.f('ix_users_verification_token'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')

    op.drop_column('users', 'google_id')
    op.drop_column('users', 'reset_token_expires_at')
    op.drop_column('users', 'reset_token')
    op.drop_column('users', 'verification_token_expires_at')
    op.drop_column('users', 'verification_token')
    op.drop_column('users', 'is_verified')
    op.drop_column('users', 'password_hash')
    op.drop_column('users', 'full_name')

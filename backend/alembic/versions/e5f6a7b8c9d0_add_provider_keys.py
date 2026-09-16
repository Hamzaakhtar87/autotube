"""add provider_keys table (Phase 2 BYOK vault)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-16
"""
from alembic import op
import sqlalchemy as sa

revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None

PROVIDERS = ('anthropic', 'openai', 'groq', 'gemini', 'kling', 'veo', 'seedance')


def upgrade() -> None:
    op.create_table(
        'provider_keys',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('ciphertext', sa.Text(), nullable=False),
        sa.Column('key_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('last_tested_at', sa.DateTime(timezone=True)),
        sa.Column('last_test_status', sa.String()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('user_id', 'provider', name='uq_provider_keys_user_provider'),
        sa.CheckConstraint("provider in (%s)" % ", ".join(f"'{p}'" for p in PROVIDERS),
                           name='provider_keys_provider'),
    )
    op.create_index('ix_provider_keys_user_id', 'provider_keys', ['user_id'])

    # Ciphertext is private even though it can't be opened without the runner's
    # key: RLS on with NO policies, and no grants, so the public anon key gets
    # nothing through PostgREST. Reads/writes happen only via the API's
    # Postgres connection and the runner's.
    if op.get_bind().dialect.name == 'postgresql':
        op.execute("ALTER TABLE provider_keys ENABLE ROW LEVEL SECURITY")
        op.execute("REVOKE ALL ON provider_keys FROM anon, authenticated")
        op.execute("NOTIFY pgrst, 'reload schema'")


def downgrade() -> None:
    op.drop_index('ix_provider_keys_user_id', table_name='provider_keys')
    op.drop_table('provider_keys')

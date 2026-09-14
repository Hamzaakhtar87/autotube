"""add niche_profiles table (Phase 1)

Revision ID: d4e5f6a7b8c9
Revises: c1d2e3f4a5b6
Create Date: 2026-09-14
"""
from alembic import op
import sqlalchemy as sa

revision = 'd4e5f6a7b8c9'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None

HOOK_STYLES = (
    'cold_open_question', 'direct_question_pattern_interrupt', 'problem_then_promise',
    'challenge_statement', 'establishing_context', 'numbered_promise',
)


def upgrade() -> None:
    op.create_table(
        'niche_profiles',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('script_system_prompt', sa.Text(), nullable=False),
        sa.Column('hook_style', sa.String(), nullable=False),
        sa.Column('pacing', sa.JSON(), nullable=False),
        sa.Column('visual_prompt_modifiers', sa.Text(), nullable=False),
        sa.Column('voice_tone', sa.String(), nullable=False),
        sa.Column('music_mood', sa.String(), nullable=False),
        sa.Column('caption_style', sa.String(), nullable=False),
        sa.Column('aspect_default', sa.String(), nullable=False),
        sa.Column('needs_tts', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        sa.CheckConstraint("id ~ '^[a-z][a-z0-9_]*$'", name='niche_profiles_id_snake_case'),
        sa.CheckConstraint("aspect_default in ('9:16', '16:9')", name='niche_profiles_aspect_default'),
        sa.CheckConstraint("hook_style in (%s)" % ", ".join(f"'{h}'" for h in HOOK_STYLES),
                           name='niche_profiles_hook_style'),
    )

    # Profiles are public data (the create-job UI lists them). Reads for anon +
    # authenticated via PostgREST; writes only via the service role / migrations.
    if op.get_bind().dialect.name == 'postgresql':
        op.execute("ALTER TABLE niche_profiles ENABLE ROW LEVEL SECURITY")
        op.execute("CREATE POLICY niche_profiles_public_read ON niche_profiles FOR SELECT TO anon, authenticated USING (true)")
        op.execute("GRANT SELECT ON niche_profiles TO anon, authenticated")
        op.execute("NOTIFY pgrst, 'reload schema'")


def downgrade() -> None:
    op.drop_table('niche_profiles')

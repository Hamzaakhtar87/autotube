"""drop celery_task_id from jobs (Celery/Redis removed; jobs run on GitHub Actions)

Revision ID: c1d2e3f4a5b6
Revises: 3ac5d651a231
Create Date: 2026-09-14
"""
from alembic import op
import sqlalchemy as sa

revision = 'c1d2e3f4a5b6'
down_revision = '3ac5d651a231'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('jobs', 'celery_task_id')


def downgrade() -> None:
    op.add_column('jobs', sa.Column('celery_task_id', sa.String(), nullable=True))

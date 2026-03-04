"""add celery_task_id

Revision ID: add_celery_task_id_rev
Revises: initial_rev
Create Date: 2024-01-27 12:38:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_celery_task_id_rev'
down_revision: Union[str, None] = 'initial_rev'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('celery_task_id', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'celery_task_id')

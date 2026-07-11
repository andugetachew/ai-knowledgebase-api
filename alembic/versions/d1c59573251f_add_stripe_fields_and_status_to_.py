"""add storage_key to documents

Revision ID: d1c59573251f
Revises: f277f1a007dc
Create Date: 2026-07-11 03:46:59.507593

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd1c59573251f'
down_revision: Union[str, None] = 'f277f1a007dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('storage_key', sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'storage_key')
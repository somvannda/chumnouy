"""tickets.sentiment

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("sentiment", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("tickets", "sentiment")

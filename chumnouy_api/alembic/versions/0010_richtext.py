"""messages: rich text (body_format)

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ticket_messages",
        sa.Column("body_format", sa.String(length=10), nullable=False, server_default="text"),
    )


def downgrade() -> None:
    op.drop_column("ticket_messages", "body_format")

"""attachments: kind (image | file)

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ticket_attachments",
        sa.Column("kind", sa.String(length=10), nullable=False, server_default="image"),
    )


def downgrade() -> None:
    op.drop_column("ticket_attachments", "kind")

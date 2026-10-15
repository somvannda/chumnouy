"""presence: ticket_presence

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ticket_presence",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("ticket_id", "user_id", name="uq_ticket_presence"),
    )
    op.create_index("ix_ticket_presence_ticket_id", "ticket_presence", ["ticket_id"])
    op.create_index("ix_ticket_presence_user_id", "ticket_presence", ["user_id"])


def downgrade() -> None:
    op.drop_table("ticket_presence")

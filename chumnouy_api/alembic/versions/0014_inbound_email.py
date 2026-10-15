"""inbound: ticket_messages.email_message_id

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ticket_messages", sa.Column("email_message_id", sa.String(length=255), nullable=True)
    )
    op.create_index("ix_ticket_messages_email_message_id", "ticket_messages", ["email_message_id"])


def downgrade() -> None:
    op.drop_index("ix_ticket_messages_email_message_id", table_name="ticket_messages")
    op.drop_column("ticket_messages", "email_message_id")

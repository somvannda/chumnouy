"""sla: tickets.first_response_due_at / resolution_due_at / sla_breached_at

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("first_response_due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tickets", sa.Column("resolution_due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tickets", sa.Column("sla_breached_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_tickets_sla_breached_at", "tickets", ["sla_breached_at"])


def downgrade() -> None:
    op.drop_index("ix_tickets_sla_breached_at", table_name="tickets")
    op.drop_column("tickets", "sla_breached_at")
    op.drop_column("tickets", "resolution_due_at")
    op.drop_column("tickets", "first_response_due_at")

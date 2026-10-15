"""automations: time-based rules

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "automations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("actions", sa.JSON(), nullable=False),
        sa.Column("after_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_automations_workspace_id", "automations", ["workspace_id"])
    op.create_index("ix_automation_workspace_active", "automations", ["workspace_id", "is_active"])

    op.create_table(
        "ticket_automations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("automation_id", sa.Uuid(), sa.ForeignKey("automations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("ticket_id", "automation_id", name="uq_ticket_automation"),
    )
    op.create_index("ix_ticket_automations_ticket_id", "ticket_automations", ["ticket_id"])
    op.create_index("ix_ticket_automations_automation_id", "ticket_automations", ["automation_id"])


def downgrade() -> None:
    op.drop_table("ticket_automations")
    op.drop_table("automations")

"""requesters: portal tokens for the public surface

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("requesters", sa.Column("portal_token_hash", sa.String(length=64), nullable=True))
    op.add_column("requesters", sa.Column("portal_token_prefix", sa.String(length=16), nullable=True))
    op.add_column("requesters", sa.Column("portal_token_issued_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint("uq_requester_portal_token_hash", "requesters", ["portal_token_hash"])


def downgrade() -> None:
    op.drop_constraint("uq_requester_portal_token_hash", "requesters", type_="unique")
    op.drop_column("requesters", "portal_token_issued_at")
    op.drop_column("requesters", "portal_token_prefix")
    op.drop_column("requesters", "portal_token_hash")

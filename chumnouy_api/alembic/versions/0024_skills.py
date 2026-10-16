"""skills: memberships.skills, tickets.required_skills

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("memberships", sa.Column("skills", sa.JSON(), nullable=True))
    op.add_column("tickets", sa.Column("required_skills", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("tickets", "required_skills")
    op.drop_column("memberships", "skills")

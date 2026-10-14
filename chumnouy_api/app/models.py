"""SQLAlchemy models.

Tenancy is Account → Workspace → Integration (see docs/architecture.md ADR-003).
Every tenant table carries ``workspace_id``; the ticket domain is added later.

UUIDs use SQLAlchemy's generic ``Uuid`` so the schema also builds on SQLite for
tests, while remaining a native ``uuid`` on PostgreSQL.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Account(Base, TimestampMixin):
    """The ownership/billing entity that signs up. Owns workspaces."""

    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("slug", name="uq_account_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="active")


class Workspace(Base, TimestampMixin):
    """The hard data-isolation boundary. Every tenant row carries ``workspace_id``."""

    __tablename__ = "workspaces"
    __table_args__ = (UniqueConstraint("slug", name="uq_workspace_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80))
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class User(Base, TimestampMixin):
    """A human who signs in to the console (agent / workspace admin)."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_user_email"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    platform_role: Mapped[str] = mapped_column(String(20), default="user")
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)


class Membership(Base, TimestampMixin):
    """Links a user to a workspace with a role (owner | admin | agent)."""

    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_membership_workspace_user"),
        Index("ix_membership_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), default="agent")
    status: Mapped[str] = mapped_column(String(20), default="active")


class Integration(Base, TimestampMixin):
    """A registered client app inside a workspace (e.g. "Chmaba POS")."""

    __tablename__ = "integrations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_integration_workspace_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80))
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ApiKey(Base, TimestampMixin):
    """A scoped, environment-tagged credential owned by an integration.

    Only ``secret_hash`` (SHA-256 of the full key) is stored. ``key_prefix`` is a
    short, non-secret fragment shown in the console so a key is identifiable.
    """

    __tablename__ = "api_keys"
    __table_args__ = (Index("ix_api_key_integration", "integration_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    integration_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("integrations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    key_prefix: Mapped[str] = mapped_column(String(24))
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True)
    environment: Mapped[str] = mapped_column(String(10), default="live")
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

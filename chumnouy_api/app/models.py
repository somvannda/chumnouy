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
    Integer,
    String,
    Text,
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
    # Skills this agent can be routed by (lower-case tokens, e.g. "billing").
    skills: Mapped[list] = mapped_column(JSON, default=list)


class WorkspaceInvite(Base, TimestampMixin):
    """A pending invitation to join a workspace.

    Stands alone until accepted (``Membership.user_id`` is not nullable, so the
    ``User`` is only created when the invite is accepted). Only the SHA-256 digest
    of the token is stored; the plaintext is returned once, like an API key.
    """

    __tablename__ = "workspace_invites"
    __table_args__ = (
        UniqueConstraint("workspace_id", "email", name="uq_invite_workspace_email"),
        Index("ix_invite_token_hash", "token_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="agent")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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


# --- Ticket domain ------------------------------------------------------------
# References are short and workspace-scoped (CMY-1042); the UUID is the wire id.


class Requester(Base, TimestampMixin):
    """An external end user (the integrator's customer), keyed by their id."""

    __tablename__ = "requesters"
    __table_args__ = (
        UniqueConstraint("workspace_id", "external_id", name="uq_requester_workspace_external"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(120))
    name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    # Portal token: an opaque credential the integrator hands to their end user
    # so the requester can use the public surface without a console account.
    # Only the SHA-256 digest is stored; the plaintext is returned once.
    portal_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    portal_token_prefix: Mapped[str | None] = mapped_column(String(16), nullable=True)
    portal_token_issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Ticket(Base, TimestampMixin):
    """A support conversation. ``subject`` + the first message are its opening."""

    __tablename__ = "tickets"
    __table_args__ = (
        UniqueConstraint("workspace_id", "reference", name="uq_ticket_workspace_reference"),
        Index("ix_ticket_workspace_created", "workspace_id", "created_at"),
        Index("ix_ticket_workspace_status", "workspace_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[int] = mapped_column(Integer)
    reference: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="open")
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    requester_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("requesters.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_integration_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("integrations.id", ondelete="SET NULL"), nullable=True
    )
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tags: Mapped[list] = mapped_column(JSON, default=list)
    required_skills: Mapped[list] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_response_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_breached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TicketMessage(Base):
    """One message in a ticket thread (requester, agent, system or ai)."""

    __tablename__ = "ticket_messages"
    __table_args__ = (Index("ix_ticket_message_ticket_created", "ticket_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    author_type: Mapped[str] = mapped_column(String(20), default="requester")
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    visibility: Mapped[str] = mapped_column(String(20), default="public")
    body: Mapped[str] = mapped_column(Text)
    # "text" or "html"; an "html" body is stored sanitised (services/sanitize.py).
    body_format: Mapped[str] = mapped_column(String(10), default="text")
    # The inbound email Message-ID, used to thread replies (services/inbound.py).
    email_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TicketEvent(Base):
    """Append-only timeline entry for a ticket (created, replied, assigned, …)."""

    __tablename__ = "ticket_events"
    __table_args__ = (Index("ix_ticket_event_ticket_created", "ticket_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(40))
    actor_type: Mapped[str] = mapped_column(String(20), default="system")
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TicketAttachment(Base):
    """A file attached to a ticket or one of its messages.

    Rows start *unowned* (``ticket_id`` is NULL) while a requester or agent is
    composing, then are claimed by the request/reply that references them. A
    claimed row with ``message_id`` NULL belongs to the opening question; a set
    ``message_id`` attaches the file to that thread message. ``sha256`` is the
    content digest, unique per workspace so identical bytes collapse to one file
    on disk. Ported from Chmaba POS ``SupportTicketAttachment`` (workspace-scoped).
    """

    __tablename__ = "ticket_attachments"
    __table_args__ = (
        Index("ix_ticket_attachment_workspace_sha", "workspace_id", "sha256"),
        Index("ix_ticket_attachment_ticket_created", "ticket_id", "created_at"),
        Index("ix_ticket_attachment_message_id", "message_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ticket_messages.id", ondelete="CASCADE"), nullable=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # "image" or "file" (derived from the content type / suffix at upload time).
    kind: Mapped[str] = mapped_column(String(10), default="image")
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- Teams --------------------------------------------------------------------


class Team(Base, TimestampMixin):
    """A group of agents inside a workspace (routing / collaboration unit)."""

    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_team_workspace_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)


class TeamMember(Base):
    """A user's membership of a team (``lead`` or ``member``)."""

    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_member"),
        Index("ix_team_member_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("teams.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- Canned responses ---------------------------------------------------------


class CannedResponse(Base, TimestampMixin):
    """A saved reply an agent can insert into a ticket message."""

    __tablename__ = "canned_responses"
    __table_args__ = (
        UniqueConstraint("workspace_id", "title", name="uq_canned_workspace_title"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text)
    body_format: Mapped[str] = mapped_column(String(10), default="text")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


# --- Triggers -----------------------------------------------------------------


class Trigger(Base, TimestampMixin):
    """An event-based rule: when ``event`` fires and ``conditions`` match, run
    ``actions`` against the ticket (set status/priority, add/remove a tag, set
    team). Evaluated once per ticket write; actions do not re-trigger."""

    __tablename__ = "triggers"
    __table_args__ = (Index("ix_trigger_workspace_event", "workspace_id", "event"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    event: Mapped[str] = mapped_column(String(40))
    conditions: Mapped[list] = mapped_column(JSON, default=list)
    actions: Mapped[list] = mapped_column(JSON, default=list)
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# --- CSAT ---------------------------------------------------------------------


class CsatResponse(Base):
    """A requester's satisfaction rating for a resolved ticket (one per ticket)."""

    __tablename__ = "csat_responses"
    __table_args__ = (UniqueConstraint("ticket_id", name="uq_csat_ticket"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    rating: Mapped[str] = mapped_column(String(10))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- Automations --------------------------------------------------------------


class Automation(Base, TimestampMixin):
    """A time-based rule: after ``after_minutes`` a ticket that matches
    ``conditions`` and is still open runs ``actions`` (once per ticket)."""

    __tablename__ = "automations"
    __table_args__ = (Index("ix_automation_workspace_active", "workspace_id", "is_active"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    conditions: Mapped[list] = mapped_column(JSON, default=list)
    actions: Mapped[list] = mapped_column(JSON, default=list)
    after_minutes: Mapped[int] = mapped_column(Integer, default=60)
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TicketAutomation(Base):
    """Marks that an automation has been applied to a ticket (once-only)."""

    __tablename__ = "ticket_automations"
    __table_args__ = (
        UniqueConstraint("ticket_id", "automation_id", name="uq_ticket_automation"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    automation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("automations.id", ondelete="CASCADE"), index=True
    )
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- Macros -------------------------------------------------------------------


class Macro(Base, TimestampMixin):
    """A named set of actions an agent applies to a ticket on demand."""

    __tablename__ = "macros"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    actions: Mapped[list] = mapped_column(JSON, default=list)


# --- Ticket presence ----------------------------------------------------------


class TicketPresence(Base):
    """Who is currently viewing a ticket (heartbeat; stale rows age out)."""

    __tablename__ = "ticket_presence"
    __table_args__ = (UniqueConstraint("ticket_id", "user_id", name="uq_ticket_presence"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- Live chat ----------------------------------------------------------------


class ChatSession(Base, TimestampMixin):
    """A real-time chat between a requester and the workspace's agents."""

    __tablename__ = "chat_sessions"
    __table_args__ = (Index("ix_chat_session_workspace_status", "workspace_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    requester_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("requesters.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="open")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChatMessage(Base):
    """One chat message (requester or agent)."""

    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_message_session_created", "session_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    author_type: Mapped[str] = mapped_column(String(20), default="requester")
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- Webhooks -----------------------------------------------------------------
# A workspace registers URLs; ticket events fan out to one delivery row per
# webhook. Delivery is signed (HMAC-SHA256) and retried with backoff.


class Webhook(Base, TimestampMixin):
    """A workspace-registered HTTPS endpoint that receives ticket events.

    ``secret`` is the HMAC signing key, returned to the caller exactly once at
    creation and never exposed again by a read model.
    """

    __tablename__ = "webhooks"
    __table_args__ = (Index("ix_webhook_workspace_active", "workspace_id", "is_active"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    secret: Mapped[str] = mapped_column(String(64))
    events: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class WebhookDelivery(Base, TimestampMixin):
    """One attempt ledger: a queued event for a webhook, sent and retried.

    Rows start ``pending`` and are drained by the delivery worker, which retries
    with backoff until ``delivered`` or ``failed``. ``event_id`` is the stable id
    sent as ``X-Chumnouy-Delivery`` so a receiver can de-duplicate.
    """

    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        Index("ix_webhook_delivery_webhook_created", "webhook_id", "created_at"),
        Index("ix_webhook_delivery_queue", "status", "next_attempt_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    webhook_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("webhooks.id", ondelete="CASCADE"), index=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    event: Mapped[str] = mapped_column(String(60))
    event_id: Mapped[str] = mapped_column(String(36))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --- Idempotency --------------------------------------------------------------


class IdempotencyKey(Base, TimestampMixin):
    """A stored write result so a retried request returns the original response.

    Keyed per workspace by the client-supplied ``Idempotency-Key`` header; the
    response body is replayed verbatim on a repeat.
    """

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("workspace_id", "key", name="uq_idempotency_workspace_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(255))
    endpoint: Mapped[str] = mapped_column(String(80))
    status_code: Mapped[int] = mapped_column(Integer)
    response: Mapped[dict] = mapped_column(JSON, default=dict)


# --- Workspace audit events ---------------------------------------------------
# Ticket writes land in ``ticket_events``; workspace-level changes (settings,
# members, keys, teams) land here so the audit trail covers the account too.


class WorkspaceEvent(Base):
    """An account/workspace-level audit event (no ticket involved)."""

    __tablename__ = "workspace_events"
    __table_args__ = (Index("ix_workspace_event_workspace_created", "workspace_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(60))
    actor_type: Mapped[str] = mapped_column(String(20), default="user")
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- Notifyr outbox -----------------------------------------------------------
# Human-facing delivery is Notifyr's job; we only queue the event and hand it off
# from a worker so a ticket write never blocks on (or fails because of) Notifyr.


class NotifyrEvent(Base, TimestampMixin):
    """A queued hand-off to Notifyr, delivered with retry/backoff."""

    __tablename__ = "notifyr_events"
    __table_args__ = (Index("ix_notifyr_event_queue", "status", "next_attempt_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True
    )
    event: Mapped[str] = mapped_column(String(60))
    recipient: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --- Knowledge base -----------------------------------------------------------
# The per-workspace help corpus. The AI assistant is grounded on these articles.


class KnowledgeArticle(Base, TimestampMixin):
    """A workspace-scoped help article.

    ``slug`` is unique per workspace + ``locale``. ``section`` groups articles;
    ``verticals``/``roles`` are optional targeting hints for retrieval. Articles
    are soft-deleted via ``is_active`` and can be restored.
    """

    __tablename__ = "knowledge_articles"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "slug", "locale", name="uq_knowledge_workspace_slug_locale"
        ),
        Index("ix_knowledge_workspace_section", "workspace_id", "section"),
        Index("ix_knowledge_workspace_active", "workspace_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    slug: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    section: Mapped[str] = mapped_column(String(80), default="general")
    locale: Mapped[str] = mapped_column(String(5), default="en")
    verticals: Mapped[list] = mapped_column(JSON, default=list)
    roles: Mapped[list] = mapped_column(JSON, default=list)
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class HelpArticleFeedback(Base):
    """A reader's verdict on a help article ("was this helpful?")."""

    __tablename__ = "help_article_feedback"
    __table_args__ = (Index("ix_help_feedback_article_created", "article_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("knowledge_articles.id", ondelete="CASCADE"), index=True
    )
    helpful: Mapped[bool] = mapped_column(Boolean, default=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- AI assistant -------------------------------------------------------------
# Conversations are grounded in the workspace knowledge corpus; every answer can
# be rated. Provider credentials live in ``workspace.settings`` (services/ai.py).


class AssistantConversation(Base, TimestampMixin):
    """A rolling assistant thread, scoped to a workspace and its actor."""

    __tablename__ = "assistant_conversations"
    __table_args__ = (
        Index("ix_assistant_conversation_workspace_updated", "workspace_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    integration_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("integrations.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(120))
    locale: Mapped[str] = mapped_column(String(5), default="en")


class AssistantMessage(Base):
    """One turn in an assistant conversation (user or assistant)."""

    __tablename__ = "assistant_messages"
    __table_args__ = (
        Index("ix_assistant_message_conversation_created", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("assistant_conversations.id", ondelete="CASCADE"), index=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    usage: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AssistantFeedback(Base):
    """A rating (up/down) on one assistant answer."""

    __tablename__ = "assistant_feedback"
    __table_args__ = (Index("ix_assistant_feedback_message", "message_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("assistant_messages.id", ondelete="CASCADE")
    )
    rating: Mapped[str] = mapped_column(String(10))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

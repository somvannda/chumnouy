from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthRead(BaseModel):
    status: str
    service: str
    version: str
    environment: str


# --- Auth --------------------------------------------------------------------


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    name: str = Field(min_length=1, max_length=120)
    workspace_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserRead(APIModel):
    id: UUID
    email: EmailStr
    name: str
    is_verified: bool
    created_at: datetime


class WorkspaceRead(APIModel):
    id: UUID
    name: str
    slug: str
    role: str


class AuthRead(BaseModel):
    token: str
    user: UserRead
    workspace: WorkspaceRead


class MeRead(BaseModel):
    user: UserRead
    workspaces: list[WorkspaceRead]


# --- Integrations & keys -----------------------------------------------------


class IntegrationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] | None = None


class IntegrationRead(APIModel):
    id: UUID
    name: str
    slug: str
    scopes: list[str]
    is_active: bool
    created_at: datetime


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    environment: Literal["test", "live"] = "live"
    scopes: list[str] | None = None


class ApiKeyRead(APIModel):
    id: UUID
    name: str
    key_prefix: str
    environment: str
    scopes: list[str]
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime


class ApiKeyCreated(BaseModel):
    """Returned once, at creation. ``key`` is never retrievable again."""

    key: str
    api_key: ApiKeyRead


# --- Tickets -----------------------------------------------------------------
# Read models are built explicitly in the service (the ORM attribute for the
# JSON column is ``metadata_json`` because SQLAlchemy reserves ``.metadata``).


class RequesterInput(BaseModel):
    external_id: str = Field(min_length=1, max_length=120)
    name: str | None = Field(default=None, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    metadata: dict = Field(default_factory=dict)


class RequesterRead(BaseModel):
    id: UUID
    external_id: str
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    metadata: dict = Field(default_factory=dict)


class TicketMessageCreate(BaseModel):
    body: str = Field(min_length=1)
    visibility: Literal["public", "internal"] = "public"
    attachment_ids: list[UUID] = Field(default_factory=list)


class AttachmentRead(APIModel):
    """A staged or claimed file. ``url`` is served from the media prefix."""

    id: UUID
    url: str
    content_type: str | None = None
    byte_size: int
    original_filename: str | None = None
    position: int


class TicketMessageRead(BaseModel):
    id: UUID
    author_type: str
    visibility: str
    body: str
    created_at: datetime
    attachments: list[AttachmentRead] = Field(default_factory=list)


class TicketCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1)
    requester: RequesterInput
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    attachment_ids: list[UUID] = Field(default_factory=list)


class TicketUpdate(BaseModel):
    subject: str | None = Field(default=None, max_length=255)
    status: Literal["open", "pending", "resolved", "closed"] | None = None
    priority: Literal["low", "normal", "high", "urgent"] | None = None
    assignee_user_id: UUID | None = None
    tags: list[str] | None = None


class TicketRead(BaseModel):
    id: UUID
    reference: str
    subject: str
    status: str
    priority: str
    assignee_user_id: UUID | None = None
    requester: RequesterRead | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    resolved_at: datetime | None = None


class TicketDetailRead(TicketRead):
    messages: list[TicketMessageRead] = Field(default_factory=list)
    attachments: list[AttachmentRead] = Field(default_factory=list)


class AttachmentClaim(BaseModel):
    attachment_ids: list[UUID] = Field(default_factory=list)


class TicketListRead(BaseModel):
    data: list[TicketRead] = Field(default_factory=list)
    next_cursor: str | None = None


# --- Webhooks -----------------------------------------------------------------


class WebhookCreate(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=255)
    events: list[str] = Field(default_factory=list)
    is_active: bool = True


class WebhookUpdate(BaseModel):
    url: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=255)
    events: list[str] | None = None
    is_active: bool | None = None


class WebhookRead(BaseModel):
    id: UUID
    url: str
    description: str | None = None
    events: list[str] = Field(default_factory=list)
    is_active: bool
    created_at: datetime


class WebhookCreated(BaseModel):
    """Returned once, at creation. ``secret`` is never retrievable again."""

    secret: str
    webhook: WebhookRead


class WebhookDeliveryRead(BaseModel):
    id: UUID
    webhook_id: UUID
    event: str
    status: str
    attempts: int
    response_status: int | None = None
    error: str | None = None
    created_at: datetime
    delivered_at: datetime | None = None


# --- Knowledge base -----------------------------------------------------------


class KnowledgeArticleCreate(BaseModel):
    slug: str | None = Field(default=None, max_length=160)
    title: str = Field(min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=500)
    body: str = Field(min_length=1)
    section: str = Field(default="general", max_length=80)
    locale: Literal["en", "km"] = "en"
    verticals: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    position: int = 0
    is_active: bool = True


class KnowledgeArticleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=500)
    body: str | None = Field(default=None, min_length=1)
    section: str | None = Field(default=None, max_length=80)
    locale: Literal["en", "km"] | None = None
    verticals: list[str] | None = None
    roles: list[str] | None = None
    position: int | None = None
    is_active: bool | None = None


class KnowledgeArticleRead(BaseModel):
    id: UUID
    slug: str
    title: str
    summary: str | None = None
    body: str
    section: str
    locale: str
    verticals: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    position: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --- AI assistant -------------------------------------------------------------


class AssistantChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: UUID | None = None
    history: list[dict] = Field(default_factory=list)
    locale: Literal["en", "km"] = "en"
    context: dict = Field(default_factory=dict)


class AssistantCitation(BaseModel):
    id: UUID
    title: str
    slug: str


class AssistantMessageRead(BaseModel):
    id: UUID
    role: str
    content: str
    citations: list[AssistantCitation] = Field(default_factory=list)
    created_at: datetime


class AssistantConversationRead(BaseModel):
    id: UUID
    title: str
    locale: str
    created_at: datetime
    updated_at: datetime


class AssistantConversationDetail(AssistantConversationRead):
    messages: list[AssistantMessageRead] = Field(default_factory=list)


class AssistantFeedbackCreate(BaseModel):
    message_id: UUID
    rating: Literal["up", "down"]
    comment: str | None = Field(default=None, max_length=2000)


class AssistantFeedbackRead(BaseModel):
    id: UUID
    message_id: UUID
    rating: str
    comment: str | None = None
    created_at: datetime


class AgentDraftRequest(BaseModel):
    instruction: str | None = Field(default=None, max_length=1000)
    tone: str | None = Field(default=None, max_length=40)


class AgentDraftRead(BaseModel):
    draft: str
    provider: str | None = None
    model: str | None = None

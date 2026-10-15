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
    platform_role: str = "user"
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
    body_format: Literal["text", "html"] = "text"
    visibility: Literal["public", "internal"] = "public"
    attachment_ids: list[UUID] = Field(default_factory=list)
    mentions: list[UUID] = Field(default_factory=list)


class AttachmentRead(APIModel):
    """A staged or claimed file. ``url`` is served from the media prefix."""

    id: UUID
    url: str
    content_type: str | None = None
    kind: str = "image"
    byte_size: int
    original_filename: str | None = None
    position: int


class TicketMessageRead(BaseModel):
    id: UUID
    author_type: str
    visibility: str
    body: str
    body_format: str = "text"
    created_at: datetime
    attachments: list[AttachmentRead] = Field(default_factory=list)


class TicketCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1)
    message_format: Literal["text", "html"] = "text"
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
    team_id: UUID | None = None
    tags: list[str] | None = None


class TicketRead(BaseModel):
    id: UUID
    reference: str
    subject: str
    status: str
    priority: str
    assignee_user_id: UUID | None = None
    team_id: UUID | None = None
    requester: RequesterRead | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    resolved_at: datetime | None = None
    first_response_due_at: datetime | None = None
    resolution_due_at: datetime | None = None
    sla_breached_at: datetime | None = None


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


# --- Requesters & public surface ----------------------------------------------


class RequesterUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    metadata: dict | None = None


class RequesterPortalToken(BaseModel):
    """Returned once, when a portal token is issued. Never retrievable again."""

    token: str
    token_prefix: str


class RequesterDetail(RequesterRead):
    tickets: list[TicketRead] = Field(default_factory=list)


class PublicTicketCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1)
    message_format: Literal["text", "html"] = "text"
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    attachment_ids: list[UUID] = Field(default_factory=list)


class PublicTicketMessageCreate(BaseModel):
    body: str = Field(min_length=1)
    body_format: Literal["text", "html"] = "text"
    attachment_ids: list[UUID] = Field(default_factory=list)


# --- Platform admin -----------------------------------------------------------


class AdminAccountRead(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
    workspace_count: int
    created_at: datetime


class AdminWorkspaceSummary(BaseModel):
    id: UUID
    account_id: UUID
    name: str
    slug: str
    is_active: bool
    ticket_count: int
    created_at: datetime


class AdminWorkspaceDetail(AdminWorkspaceSummary):
    member_count: int
    integration_count: int
    knowledge_article_count: int
    quota: dict = Field(default_factory=dict)


class AdminWorkspaceUpdate(BaseModel):
    is_active: bool | None = None
    quota: dict | None = None


class AdminUsageRead(BaseModel):
    accounts: int
    workspaces: int
    active_workspaces: int
    tickets: int
    open_tickets: int
    requesters: int
    integrations: int
    knowledge_articles: int
    webhook_deliveries: int


# --- Workspace settings (console) ---------------------------------------------


class AISettingsRead(BaseModel):
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key_set: bool
    providers: list[dict] = Field(default_factory=list)


class AISettingsUpdate(BaseModel):
    provider: Literal["openai", "deepseek", "anthropic"] | None = None
    model: str | None = Field(default=None, max_length=120)
    base_url: str | None = Field(default=None, max_length=300)
    api_key: str | None = Field(default=None, max_length=400)


class NotificationSettingsRead(BaseModel):
    notifyr_api_url: str | None = None
    notifyr_api_key_set: bool


class NotificationSettingsUpdate(BaseModel):
    notifyr_api_url: str | None = Field(default=None, max_length=300)
    notifyr_api_key: str | None = Field(default=None, max_length=400)


class SlaSettingsRead(BaseModel):
    first_response_minutes: dict[str, int] = Field(default_factory=dict)
    resolution_minutes: dict[str, int] = Field(default_factory=dict)


class SlaSettingsUpdate(BaseModel):
    first_response_minutes: dict[str, int] | None = None
    resolution_minutes: dict[str, int] | None = None


class WorkspaceSettingsRead(BaseModel):
    locale: str = "en"
    ai: AISettingsRead
    notifications: NotificationSettingsRead
    sla: SlaSettingsRead


class LocaleUpdate(BaseModel):
    locale: Literal["en", "km"] = "en"


# --- Search -------------------------------------------------------------------


class SearchResult(BaseModel):
    type: Literal["ticket", "message", "article"]
    id: UUID
    title: str
    snippet: str = ""
    ticket_id: UUID | None = None
    reference: str | None = None
    created_at: datetime | None = None


class SearchResults(BaseModel):
    query: str
    results: list[SearchResult] = Field(default_factory=list)


# --- Teams --------------------------------------------------------------------


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=255)


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=255)


class TeamMemberAdd(BaseModel):
    user_id: UUID
    role: Literal["lead", "member"] = "member"


class TeamMemberRead(BaseModel):
    user_id: UUID
    role: str


class TeamRead(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None = None
    members: list[TeamMemberRead] = Field(default_factory=list)
    created_at: datetime


# --- Audit log ----------------------------------------------------------------


class AuditEventRead(BaseModel):
    id: UUID
    ticket_id: UUID
    type: str
    actor_type: str
    actor_id: UUID | None = None
    data: dict = Field(default_factory=dict)
    created_at: datetime


class AuditListRead(BaseModel):
    data: list[AuditEventRead] = Field(default_factory=list)
    next_cursor: str | None = None


# --- Inbound email ------------------------------------------------------------


class InboundEmailCreate(BaseModel):
    from_email: EmailStr
    from_name: str | None = Field(default=None, max_length=160)
    subject: str = Field(default="(no subject)", max_length=255)
    body: str = Field(min_length=1)
    body_format: Literal["text", "html"] = "text"
    message_id: str | None = Field(default=None, max_length=255)
    in_reply_to: str | None = Field(default=None, max_length=255)


# --- Canned responses ---------------------------------------------------------


class CannedResponseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1)
    body_format: Literal["text", "html"] = "text"


class CannedResponseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    body: str | None = Field(default=None, min_length=1)
    body_format: Literal["text", "html"] | None = None


class CannedResponseRead(BaseModel):
    id: UUID
    title: str
    body: str
    body_format: str = "text"
    created_at: datetime
    updated_at: datetime


# --- Triggers -----------------------------------------------------------------


class TriggerCondition(BaseModel):
    field: Literal["status", "priority", "tag", "subject"]
    op: Literal["is", "contains"] = "is"
    value: str = Field(max_length=255)


class TriggerAction(BaseModel):
    type: Literal["set_status", "set_priority", "add_tag", "remove_tag", "set_team"]
    value: str = Field(max_length=255)


class TriggerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    event: Literal["ticket.created", "ticket.replied", "ticket.updated"]
    conditions: list[TriggerCondition] = Field(default_factory=list)
    actions: list[TriggerAction] = Field(default_factory=list)
    position: int = 0
    is_active: bool = True


class TriggerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    event: Literal["ticket.created", "ticket.replied", "ticket.updated"] | None = None
    conditions: list[TriggerCondition] | None = None
    actions: list[TriggerAction] | None = None
    position: int | None = None
    is_active: bool | None = None


class TriggerRead(BaseModel):
    id: UUID
    name: str
    event: str
    conditions: list[dict] = Field(default_factory=list)
    actions: list[dict] = Field(default_factory=list)
    position: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --- Reporting ----------------------------------------------------------------


class ReportSummary(BaseModel):
    total: int
    by_status: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    breached: int = 0
    sla_compliance: float | None = None
    avg_first_response_minutes: float | None = None
    avg_resolution_minutes: float | None = None
    csat_responses: int = 0
    csat_positive_pct: float | None = None


# --- CSAT ---------------------------------------------------------------------


class CsatSubmit(BaseModel):
    rating: Literal["up", "down"]
    comment: str | None = Field(default=None, max_length=2000)


class CsatRead(BaseModel):
    ticket_id: UUID
    rating: str
    comment: str | None = None
    created_at: datetime


# --- Bulk actions -------------------------------------------------------------


class BulkAction(BaseModel):
    status: Literal["open", "pending", "resolved", "closed"] | None = None
    priority: Literal["low", "normal", "high", "urgent"] | None = None
    assignee_user_id: UUID | None = None
    team_id: UUID | None = None
    add_tags: list[str] = Field(default_factory=list)
    remove_tags: list[str] = Field(default_factory=list)


class BulkUpdate(BaseModel):
    ticket_ids: list[UUID] = Field(min_length=1, max_length=200)
    action: BulkAction


class BulkResult(BaseModel):
    updated: int
    ticket_ids: list[UUID] = Field(default_factory=list)

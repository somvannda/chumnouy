/* eslint-disable */
// AUTO-GENERATED from chumnouy_api/openapi.json - do not edit by hand.
// Regenerate with: node packages/api-client/scripts/generate.mjs

/** AISettingsRead */
export interface AISettingsRead {
  /** Api Key Set */
  api_key_set: boolean;
  /** Base Url */
  base_url?: string | null;
  /** Model */
  model?: string | null;
  /** Provider */
  provider?: string | null;
  /** Providers */
  providers?: Record<string, unknown>[];
}

/** AISettingsUpdate */
export interface AISettingsUpdate {
  /** Api Key */
  api_key?: string | null;
  /** Base Url */
  base_url?: string | null;
  /** Model */
  model?: string | null;
  /** Provider */
  provider?: "openai" | "deepseek" | "anthropic" | null;
}

/** AdminAccountRead */
export interface AdminAccountRead {
  /** Created At */
  created_at: string;
  /** Id */
  id: string;
  /** Name */
  name: string;
  /** Slug */
  slug: string;
  /** Status */
  status: string;
  /** Workspace Count */
  workspace_count: number;
}

/** AdminUsageRead */
export interface AdminUsageRead {
  /** Accounts */
  accounts: number;
  /** Active Workspaces */
  active_workspaces: number;
  /** Integrations */
  integrations: number;
  /** Knowledge Articles */
  knowledge_articles: number;
  /** Open Tickets */
  open_tickets: number;
  /** Requesters */
  requesters: number;
  /** Tickets */
  tickets: number;
  /** Webhook Deliveries */
  webhook_deliveries: number;
  /** Workspaces */
  workspaces: number;
}

/** AdminWorkspaceDetail */
export interface AdminWorkspaceDetail {
  /** Account Id */
  account_id: string;
  /** Created At */
  created_at: string;
  /** Id */
  id: string;
  /** Integration Count */
  integration_count: number;
  /** Is Active */
  is_active: boolean;
  /** Knowledge Article Count */
  knowledge_article_count: number;
  /** Member Count */
  member_count: number;
  /** Name */
  name: string;
  /** Quota */
  quota?: Record<string, unknown>;
  /** Slug */
  slug: string;
  /** Ticket Count */
  ticket_count: number;
}

/** AdminWorkspaceSummary */
export interface AdminWorkspaceSummary {
  /** Account Id */
  account_id: string;
  /** Created At */
  created_at: string;
  /** Id */
  id: string;
  /** Is Active */
  is_active: boolean;
  /** Name */
  name: string;
  /** Slug */
  slug: string;
  /** Ticket Count */
  ticket_count: number;
}

/** AdminWorkspaceUpdate */
export interface AdminWorkspaceUpdate {
  /** Is Active */
  is_active?: boolean | null;
  /** Quota */
  quota?: Record<string, unknown> | null;
}

/** AgentDraftRead */
export interface AgentDraftRead {
  /** Draft */
  draft: string;
  /** Model */
  model?: string | null;
  /** Provider */
  provider?: string | null;
}

/** AgentDraftRequest */
export interface AgentDraftRequest {
  /** Instruction */
  instruction?: string | null;
  /** Tone */
  tone?: string | null;
}

/** ApiKeyCreate */
export interface ApiKeyCreate {
  /** Environment */
  environment?: "test" | "live";
  /** Name */
  name: string;
  /** Scopes */
  scopes?: string[] | null;
}

/** ApiKeyCreated */
export interface ApiKeyCreated {
  api_key: ApiKeyRead;
  /** Key */
  key: string;
}

/** ApiKeyRead */
export interface ApiKeyRead {
  /** Created At */
  created_at: string;
  /** Environment */
  environment: string;
  /** Id */
  id: string;
  /** Is Active */
  is_active: boolean;
  /** Key Prefix */
  key_prefix: string;
  /** Last Used At */
  last_used_at: string | null;
  /** Name */
  name: string;
  /** Scopes */
  scopes: string[];
}

/** AssistantChatRequest */
export interface AssistantChatRequest {
  /** Context */
  context?: Record<string, unknown>;
  /** Conversation Id */
  conversation_id?: string | null;
  /** History */
  history?: Record<string, unknown>[];
  /** Locale */
  locale?: "en" | "km";
  /** Question */
  question: string;
}

/** AssistantCitation */
export interface AssistantCitation {
  /** Id */
  id: string;
  /** Slug */
  slug: string;
  /** Title */
  title: string;
}

/** AssistantConversationDetail */
export interface AssistantConversationDetail {
  /** Created At */
  created_at: string;
  /** Id */
  id: string;
  /** Locale */
  locale: string;
  /** Messages */
  messages?: AssistantMessageRead[];
  /** Title */
  title: string;
  /** Updated At */
  updated_at: string;
}

/** AssistantConversationRead */
export interface AssistantConversationRead {
  /** Created At */
  created_at: string;
  /** Id */
  id: string;
  /** Locale */
  locale: string;
  /** Title */
  title: string;
  /** Updated At */
  updated_at: string;
}

/** AssistantFeedbackCreate */
export interface AssistantFeedbackCreate {
  /** Comment */
  comment?: string | null;
  /** Message Id */
  message_id: string;
  /** Rating */
  rating: "up" | "down";
}

/** AssistantFeedbackRead */
export interface AssistantFeedbackRead {
  /** Comment */
  comment?: string | null;
  /** Created At */
  created_at: string;
  /** Id */
  id: string;
  /** Message Id */
  message_id: string;
  /** Rating */
  rating: string;
}

/** AssistantMessageRead */
export interface AssistantMessageRead {
  /** Citations */
  citations?: AssistantCitation[];
  /** Content */
  content: string;
  /** Created At */
  created_at: string;
  /** Id */
  id: string;
  /** Role */
  role: string;
}

/** AttachmentClaim */
export interface AttachmentClaim {
  /** Attachment Ids */
  attachment_ids?: string[];
}

/** AttachmentRead */
export interface AttachmentRead {
  /** Byte Size */
  byte_size: number;
  /** Content Type */
  content_type?: string | null;
  /** Id */
  id: string;
  /** Kind */
  kind?: string;
  /** Original Filename */
  original_filename?: string | null;
  /** Position */
  position: number;
  /** Url */
  url: string;
}

/** AuthRead */
export interface AuthRead {
  /** Token */
  token: string;
  user: UserRead;
  workspace: WorkspaceRead;
}

/** Body_upload_attachment_api_v1_uploads_post */
export interface Body_upload_attachment_api_v1_uploads_post {
  /** File */
  file: string;
}

/** HTTPValidationError */
export interface HTTPValidationError {
  /** Detail */
  detail?: ValidationError[];
}

/** HealthRead */
export interface HealthRead {
  /** Environment */
  environment: string;
  /** Service */
  service: string;
  /** Status */
  status: string;
  /** Version */
  version: string;
}

/** IntegrationCreate */
export interface IntegrationCreate {
  /** Name */
  name: string;
  /** Scopes */
  scopes?: string[] | null;
}

/** IntegrationRead */
export interface IntegrationRead {
  /** Created At */
  created_at: string;
  /** Id */
  id: string;
  /** Is Active */
  is_active: boolean;
  /** Name */
  name: string;
  /** Scopes */
  scopes: string[];
  /** Slug */
  slug: string;
}

/** KnowledgeArticleCreate */
export interface KnowledgeArticleCreate {
  /** Body */
  body: string;
  /** Is Active */
  is_active?: boolean;
  /** Locale */
  locale?: "en" | "km";
  /** Position */
  position?: number;
  /** Roles */
  roles?: string[];
  /** Section */
  section?: string;
  /** Slug */
  slug?: string | null;
  /** Summary */
  summary?: string | null;
  /** Title */
  title: string;
  /** Verticals */
  verticals?: string[];
}

/** KnowledgeArticleRead */
export interface KnowledgeArticleRead {
  /** Body */
  body: string;
  /** Created At */
  created_at: string;
  /** Id */
  id: string;
  /** Is Active */
  is_active: boolean;
  /** Locale */
  locale: string;
  /** Position */
  position: number;
  /** Roles */
  roles?: string[];
  /** Section */
  section: string;
  /** Slug */
  slug: string;
  /** Summary */
  summary?: string | null;
  /** Title */
  title: string;
  /** Updated At */
  updated_at: string;
  /** Verticals */
  verticals?: string[];
}

/** KnowledgeArticleUpdate */
export interface KnowledgeArticleUpdate {
  /** Body */
  body?: string | null;
  /** Is Active */
  is_active?: boolean | null;
  /** Locale */
  locale?: "en" | "km" | null;
  /** Position */
  position?: number | null;
  /** Roles */
  roles?: string[] | null;
  /** Section */
  section?: string | null;
  /** Summary */
  summary?: string | null;
  /** Title */
  title?: string | null;
  /** Verticals */
  verticals?: string[] | null;
}

/** LoginRequest */
export interface LoginRequest {
  /** Email */
  email: string;
  /** Password */
  password: string;
}

/** MeRead */
export interface MeRead {
  user: UserRead;
  /** Workspaces */
  workspaces: WorkspaceRead[];
}

/** NotificationSettingsRead */
export interface NotificationSettingsRead {
  /** Notifyr Api Key Set */
  notifyr_api_key_set: boolean;
  /** Notifyr Api Url */
  notifyr_api_url?: string | null;
}

/** NotificationSettingsUpdate */
export interface NotificationSettingsUpdate {
  /** Notifyr Api Key */
  notifyr_api_key?: string | null;
  /** Notifyr Api Url */
  notifyr_api_url?: string | null;
}

/** PublicTicketCreate */
export interface PublicTicketCreate {
  /** Attachment Ids */
  attachment_ids?: string[];
  /** Message */
  message: string;
  /** Message Format */
  message_format?: "text" | "html";
  /** Priority */
  priority?: "low" | "normal" | "high" | "urgent";
  /** Subject */
  subject: string;
}

/** PublicTicketMessageCreate */
export interface PublicTicketMessageCreate {
  /** Attachment Ids */
  attachment_ids?: string[];
  /** Body */
  body: string;
  /** Body Format */
  body_format?: "text" | "html";
}

/** RequesterDetail */
export interface RequesterDetail {
  /** Email */
  email?: string | null;
  /** External Id */
  external_id: string;
  /** Id */
  id: string;
  /** Metadata */
  metadata?: Record<string, unknown>;
  /** Name */
  name?: string | null;
  /** Phone */
  phone?: string | null;
  /** Tickets */
  tickets?: TicketRead[];
}

/** RequesterInput */
export interface RequesterInput {
  /** Email */
  email?: string | null;
  /** External Id */
  external_id: string;
  /** Metadata */
  metadata?: Record<string, unknown>;
  /** Name */
  name?: string | null;
  /** Phone */
  phone?: string | null;
}

/** RequesterPortalToken */
export interface RequesterPortalToken {
  /** Token */
  token: string;
  /** Token Prefix */
  token_prefix: string;
}

/** RequesterRead */
export interface RequesterRead {
  /** Email */
  email?: string | null;
  /** External Id */
  external_id: string;
  /** Id */
  id: string;
  /** Metadata */
  metadata?: Record<string, unknown>;
  /** Name */
  name?: string | null;
  /** Phone */
  phone?: string | null;
}

/** RequesterUpdate */
export interface RequesterUpdate {
  /** Email */
  email?: string | null;
  /** Metadata */
  metadata?: Record<string, unknown> | null;
  /** Name */
  name?: string | null;
  /** Phone */
  phone?: string | null;
}

/** SearchResult */
export interface SearchResult {
  /** Created At */
  created_at?: string | null;
  /** Id */
  id: string;
  /** Reference */
  reference?: string | null;
  /** Snippet */
  snippet?: string;
  /** Ticket Id */
  ticket_id?: string | null;
  /** Title */
  title: string;
  /** Type */
  type: "ticket" | "message" | "article";
}

/** SearchResults */
export interface SearchResults {
  /** Query */
  query: string;
  /** Results */
  results?: SearchResult[];
}

/** SignupRequest */
export interface SignupRequest {
  /** Email */
  email: string;
  /** Name */
  name: string;
  /** Password */
  password: string;
  /** Workspace Name */
  workspace_name?: string | null;
}

/** TicketCreate */
export interface TicketCreate {
  /** Attachment Ids */
  attachment_ids?: string[];
  /** Message */
  message: string;
  /** Message Format */
  message_format?: "text" | "html";
  /** Metadata */
  metadata?: Record<string, unknown>;
  /** Priority */
  priority?: "low" | "normal" | "high" | "urgent";
  requester: RequesterInput;
  /** Subject */
  subject: string;
  /** Tags */
  tags?: string[];
}

/** TicketDetailRead */
export interface TicketDetailRead {
  /** Assignee User Id */
  assignee_user_id?: string | null;
  /** Attachments */
  attachments?: AttachmentRead[];
  /** Created At */
  created_at: string;
  /** Id */
  id: string;
  /** Messages */
  messages?: TicketMessageRead[];
  /** Metadata */
  metadata?: Record<string, unknown>;
  /** Priority */
  priority: string;
  /** Reference */
  reference: string;
  requester?: RequesterRead | null;
  /** Resolved At */
  resolved_at?: string | null;
  /** Status */
  status: string;
  /** Subject */
  subject: string;
  /** Tags */
  tags?: string[];
}

/** TicketListRead */
export interface TicketListRead {
  /** Data */
  data?: TicketRead[];
  /** Next Cursor */
  next_cursor?: string | null;
}

/** TicketMessageCreate */
export interface TicketMessageCreate {
  /** Attachment Ids */
  attachment_ids?: string[];
  /** Body */
  body: string;
  /** Body Format */
  body_format?: "text" | "html";
  /** Visibility */
  visibility?: "public" | "internal";
}

/** TicketMessageRead */
export interface TicketMessageRead {
  /** Attachments */
  attachments?: AttachmentRead[];
  /** Author Type */
  author_type: string;
  /** Body */
  body: string;
  /** Body Format */
  body_format?: string;
  /** Created At */
  created_at: string;
  /** Id */
  id: string;
  /** Visibility */
  visibility: string;
}

/** TicketRead */
export interface TicketRead {
  /** Assignee User Id */
  assignee_user_id?: string | null;
  /** Created At */
  created_at: string;
  /** Id */
  id: string;
  /** Metadata */
  metadata?: Record<string, unknown>;
  /** Priority */
  priority: string;
  /** Reference */
  reference: string;
  requester?: RequesterRead | null;
  /** Resolved At */
  resolved_at?: string | null;
  /** Status */
  status: string;
  /** Subject */
  subject: string;
  /** Tags */
  tags?: string[];
}

/** TicketUpdate */
export interface TicketUpdate {
  /** Assignee User Id */
  assignee_user_id?: string | null;
  /** Priority */
  priority?: "low" | "normal" | "high" | "urgent" | null;
  /** Status */
  status?: "open" | "pending" | "resolved" | "closed" | null;
  /** Subject */
  subject?: string | null;
  /** Tags */
  tags?: string[] | null;
}

/** UserRead */
export interface UserRead {
  /** Created At */
  created_at: string;
  /** Email */
  email: string;
  /** Id */
  id: string;
  /** Is Verified */
  is_verified: boolean;
  /** Name */
  name: string;
  /** Platform Role */
  platform_role?: string;
}

/** ValidationError */
export interface ValidationError {
  /** Context */
  ctx?: Record<string, unknown>;
  /** Input */
  input?: unknown;
  /** Location */
  loc: string | number[];
  /** Message */
  msg: string;
  /** Error Type */
  type: string;
}

/** WebhookCreate */
export interface WebhookCreate {
  /** Description */
  description?: string | null;
  /** Events */
  events?: string[];
  /** Is Active */
  is_active?: boolean;
  /** Url */
  url: string;
}

/** WebhookCreated */
export interface WebhookCreated {
  /** Secret */
  secret: string;
  webhook: WebhookRead;
}

/** WebhookDeliveryRead */
export interface WebhookDeliveryRead {
  /** Attempts */
  attempts: number;
  /** Created At */
  created_at: string;
  /** Delivered At */
  delivered_at?: string | null;
  /** Error */
  error?: string | null;
  /** Event */
  event: string;
  /** Id */
  id: string;
  /** Response Status */
  response_status?: number | null;
  /** Status */
  status: string;
  /** Webhook Id */
  webhook_id: string;
}

/** WebhookRead */
export interface WebhookRead {
  /** Created At */
  created_at: string;
  /** Description */
  description?: string | null;
  /** Events */
  events?: string[];
  /** Id */
  id: string;
  /** Is Active */
  is_active: boolean;
  /** Url */
  url: string;
}

/** WebhookUpdate */
export interface WebhookUpdate {
  /** Description */
  description?: string | null;
  /** Events */
  events?: string[] | null;
  /** Is Active */
  is_active?: boolean | null;
  /** Url */
  url?: string | null;
}

/** WorkspaceRead */
export interface WorkspaceRead {
  /** Id */
  id: string;
  /** Name */
  name: string;
  /** Role */
  role: string;
  /** Slug */
  slug: string;
}

/** WorkspaceSettingsRead */
export interface WorkspaceSettingsRead {
  ai: AISettingsRead;
  notifications: NotificationSettingsRead;
}

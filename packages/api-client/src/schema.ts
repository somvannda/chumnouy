/* eslint-disable */
// AUTO-GENERATED from chumnouy_api/openapi.json - do not edit by hand.
// Regenerate with: node packages/api-client/scripts/generate.mjs

/** AISettingsRead */
export interface AISettingsRead {
  /** Api Key Set */
  api_key_set: boolean;
  /** Auto Triage */
  auto_triage?: boolean;
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
  /** Auto Triage */
  auto_triage?: boolean | null;
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

/** AssistantSummaryRead */
export interface AssistantSummaryRead {
  /** Model */
  model?: string | null;
  /** Provider */
  provider?: string | null;
  /** Summary */
  summary: string;
}

/** AssistantTriageRead */
export interface AssistantTriageRead {
  /** Model */
  model?: string | null;
  /** Priority */
  priority: string;
  /** Provider */
  provider?: string | null;
  /** Tags */
  tags?: string[];
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

/** AuditEventRead */
export interface AuditEventRead {
  /** Actor Id */
  actor_id?: string | null;
  /** Actor Type */
  actor_type: string;
  /** Created At */
  created_at: string;
  /** Data */
  data?: Record<string, unknown>;
  /** Id */
  id: string;
  /** Ticket Id */
  ticket_id: string;
  /** Type */
  type: string;
}

/** AuditListRead */
export interface AuditListRead {
  /** Data */
  data?: AuditEventRead[];
  /** Next Cursor */
  next_cursor?: string | null;
}

/** AuthRead */
export interface AuthRead {
  /** Token */
  token: string;
  user: UserRead;
  workspace: WorkspaceRead;
}

/** AutomationCreate */
export interface AutomationCreate {
  /** Actions */
  actions?: TriggerAction[];
  /** After Minutes */
  after_minutes?: number;
  /** Conditions */
  conditions?: TriggerCondition[];
  /** Is Active */
  is_active?: boolean;
  /** Name */
  name: string;
  /** Position */
  position?: number;
}

/** AutomationRead */
export interface AutomationRead {
  /** Actions */
  actions?: Record<string, unknown>[];
  /** After Minutes */
  after_minutes: number;
  /** Conditions */
  conditions?: Record<string, unknown>[];
  /** Created At */
  created_at: string;
  /** Id */
  id: string;
  /** Is Active */
  is_active: boolean;
  /** Name */
  name: string;
  /** Position */
  position: number;
  /** Updated At */
  updated_at: string;
}

/** AutomationUpdate */
export interface AutomationUpdate {
  /** Actions */
  actions?: TriggerAction[] | null;
  /** After Minutes */
  after_minutes?: number | null;
  /** Conditions */
  conditions?: TriggerCondition[] | null;
  /** Is Active */
  is_active?: boolean | null;
  /** Name */
  name?: string | null;
  /** Position */
  position?: number | null;
}

/** Body_upload_attachment_api_v1_uploads_post */
export interface Body_upload_attachment_api_v1_uploads_post {
  /** File */
  file: string;
}

/** BrandingRead */
export interface BrandingRead {
  /** Accent */
  accent?: string;
  /** Greeting */
  greeting?: string | null;
  /** Label */
  label?: string;
  /** Position */
  position?: "right" | "left";
  /** Pre Chat */
  pre_chat?: boolean;
  /** Title */
  title?: string;
}

/** BrandingUpdate */
export interface BrandingUpdate {
  /** Accent */
  accent?: string | null;
  /** Greeting */
  greeting?: string | null;
  /** Label */
  label?: string | null;
  /** Position */
  position?: "right" | "left" | null;
  /** Pre Chat */
  pre_chat?: boolean | null;
  /** Title */
  title?: string | null;
}

/** BulkAction */
export interface BulkAction {
  /** Add Tags */
  add_tags?: string[];
  /** Assignee User Id */
  assignee_user_id?: string | null;
  /** Priority */
  priority?: "low" | "normal" | "high" | "urgent" | null;
  /** Remove Tags */
  remove_tags?: string[];
  /** Status */
  status?: "open" | "pending" | "resolved" | "closed" | null;
  /** Team Id */
  team_id?: string | null;
}

/** BulkResult */
export interface BulkResult {
  /** Ticket Ids */
  ticket_ids?: string[];
  /** Updated */
  updated: number;
}

/** BulkUpdate */
export interface BulkUpdate {
  action: BulkAction;
  /** Ticket Ids */
  ticket_ids: string[];
}

/** BusinessHoursRead */
export interface BusinessHoursRead {
  /** Days */
  days?: Record<string, string[]>;
  /** Enabled */
  enabled?: boolean;
  /** Timezone */
  timezone?: string;
}

/** BusinessHoursUpdate */
export interface BusinessHoursUpdate {
  /** Days */
  days?: Record<string, string[]> | null;
  /** Enabled */
  enabled?: boolean | null;
  /** Timezone */
  timezone?: string | null;
}

/** CannedResponseCreate */
export interface CannedResponseCreate {
  /** Body */
  body: string;
  /** Body Format */
  body_format?: "text" | "html";
  /** Title */
  title: string;
}

/** CannedResponseRead */
export interface CannedResponseRead {
  /** Body */
  body: string;
  /** Body Format */
  body_format?: string;
  /** Created At */
  created_at: string;
  /** Id */
  id: string;
  /** Title */
  title: string;
  /** Updated At */
  updated_at: string;
}

/** CannedResponseUpdate */
export interface CannedResponseUpdate {
  /** Body */
  body?: string | null;
  /** Body Format */
  body_format?: "text" | "html" | null;
  /** Title */
  title?: string | null;
}

/** ChatMessageCreate */
export interface ChatMessageCreate {
  /** Body */
  body: string;
}

/** ChatMessageRead */
export interface ChatMessageRead {
  /** Author Type */
  author_type: string;
  /** Body */
  body: string;
  /** Created At */
  created_at: string;
  /** Id */
  id: string;
}

/** ChatSessionDetail */
export interface ChatSessionDetail {
  /** Closed At */
  closed_at?: string | null;
  /** Created At */
  created_at: string;
  /** Id */
  id: string;
  /** Messages */
  messages?: ChatMessageRead[];
  /** Status */
  status: string;
}

/** ChatSessionRead */
export interface ChatSessionRead {
  /** Closed At */
  closed_at?: string | null;
  /** Created At */
  created_at: string;
  /** Id */
  id: string;
  /** Status */
  status: string;
}

/** CsatRead */
export interface CsatRead {
  /** Comment */
  comment?: string | null;
  /** Created At */
  created_at: string;
  /** Rating */
  rating: string;
  /** Ticket Id */
  ticket_id: string;
}

/** CsatSubmit */
export interface CsatSubmit {
  /** Comment */
  comment?: string | null;
  /** Rating */
  rating: "up" | "down";
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

/** HelpArticleRead */
export interface HelpArticleRead {
  /** Body */
  body: string;
  /** Locale */
  locale: string;
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
}

/** HelpArticleSummary */
export interface HelpArticleSummary {
  /** Locale */
  locale: string;
  /** Section */
  section: string;
  /** Slug */
  slug: string;
  /** Summary */
  summary?: string | null;
  /** Title */
  title: string;
}

/** HelpIndex */
export interface HelpIndex {
  /** Articles */
  articles?: HelpArticleSummary[];
  /** Sections */
  sections?: HelpSection[];
  /** Workspace */
  workspace: string;
}

/** HelpSection */
export interface HelpSection {
  /** Count */
  count: number;
  /** Section */
  section: string;
}

/** InboundEmailCreate */
export interface InboundEmailCreate {
  /** Body */
  body: string;
  /** Body Format */
  body_format?: "text" | "html";
  /** From Email */
  from_email: string;
  /** From Name */
  from_name?: string | null;
  /** In Reply To */
  in_reply_to?: string | null;
  /** Message Id */
  message_id?: string | null;
  /** Subject */
  subject?: string;
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

/** InviteAccept */
export interface InviteAccept {
  /** Name */
  name?: string | null;
  /** Password */
  password: string;
  /** Token */
  token: string;
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

/** LocaleUpdate */
export interface LocaleUpdate {
  /** Locale */
  locale?: "en" | "km";
}

/** LoginRequest */
export interface LoginRequest {
  /** Email */
  email: string;
  /** Password */
  password: string;
}

/** MacroCreate */
export interface MacroCreate {
  /** Actions */
  actions?: TriggerAction[];
  /** Name */
  name: string;
}

/** MacroRead */
export interface MacroRead {
  /** Actions */
  actions?: Record<string, unknown>[];
  /** Created At */
  created_at: string;
  /** Id */
  id: string;
  /** Name */
  name: string;
  /** Updated At */
  updated_at: string;
}

/** MacroUpdate */
export interface MacroUpdate {
  /** Actions */
  actions?: TriggerAction[] | null;
  /** Name */
  name?: string | null;
}

/** MeRead */
export interface MeRead {
  user: UserRead;
  /** Workspaces */
  workspaces: WorkspaceRead[];
}

/** MemberInvite */
export interface MemberInvite {
  /** Email */
  email: string;
  /** Name */
  name?: string | null;
  /** Role */
  role?: "admin" | "team_lead" | "agent" | "viewer";
}

/** MemberInviteRead */
export interface MemberInviteRead {
  /** Accepted At */
  accepted_at?: string | null;
  /** Email */
  email: string;
  /** Expires At */
  expires_at: string;
  /** Id */
  id: string;
  /** Role */
  role: string;
  /** Status */
  status: string;
  /** Token */
  token?: string | null;
}

/** MemberRead */
export interface MemberRead {
  /** Created At */
  created_at: string;
  /** Email */
  email: string;
  /** Name */
  name?: string | null;
  /** Role */
  role: string;
  /** Skills */
  skills?: string[];
  /** Status */
  status?: string;
  /** User Id */
  user_id: string;
}

/** MemberUpdate */
export interface MemberUpdate {
  /** Role */
  role?: "admin" | "team_lead" | "agent" | "viewer" | null;
  /** Skills */
  skills?: string[] | null;
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

/** PresenceRead */
export interface PresenceRead {
  /** Viewers */
  viewers?: string[];
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

/** ReportSummary */
export interface ReportSummary {
  /** Avg First Response Minutes */
  avg_first_response_minutes?: number | null;
  /** Avg Resolution Minutes */
  avg_resolution_minutes?: number | null;
  /** Breached */
  breached?: number;
  /** By Assignee */
  by_assignee?: Record<string, number>;
  /** By Priority */
  by_priority?: Record<string, number>;
  /** By Status */
  by_status?: Record<string, number>;
  /** By Team */
  by_team?: Record<string, number>;
  /** Csat Positive Pct */
  csat_positive_pct?: number | null;
  /** Csat Responses */
  csat_responses?: number;
  /** Sla Compliance */
  sla_compliance?: number | null;
  /** Total */
  total: number;
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

/** RequesterExport */
export interface RequesterExport {
  requester: RequesterRead;
  /** Tickets */
  tickets?: TicketDetailRead[];
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

/** SlaSettingsRead */
export interface SlaSettingsRead {
  /** First Response Minutes */
  first_response_minutes?: Record<string, number>;
  /** Resolution Minutes */
  resolution_minutes?: Record<string, number>;
  /** Teams */
  teams?: Record<string, SlaTeamPolicy>;
}

/** SlaSettingsUpdate */
export interface SlaSettingsUpdate {
  /** First Response Minutes */
  first_response_minutes?: Record<string, number> | null;
  /** Resolution Minutes */
  resolution_minutes?: Record<string, number> | null;
  /** Teams */
  teams?: Record<string, SlaTeamPolicy> | null;
}

/** SlaTeamPolicy */
export interface SlaTeamPolicy {
  /** First Response Minutes */
  first_response_minutes?: Record<string, number>;
  /** Resolution Minutes */
  resolution_minutes?: Record<string, number>;
}

/** SsoSettingsRead */
export interface SsoSettingsRead {
  /** Allowed Domains */
  allowed_domains?: string[];
  /** Client Id */
  client_id?: string | null;
  /** Client Secret Set */
  client_secret_set?: boolean;
  /** Enabled */
  enabled?: boolean;
  /** Issuer */
  issuer?: string | null;
}

/** SsoSettingsUpdate */
export interface SsoSettingsUpdate {
  /** Allowed Domains */
  allowed_domains?: string[] | null;
  /** Client Id */
  client_id?: string | null;
  /** Client Secret */
  client_secret?: string | null;
  /** Enabled */
  enabled?: boolean | null;
  /** Issuer */
  issuer?: string | null;
}

/** SsoStart */
export interface SsoStart {
  /** Authorize Url */
  authorize_url: string;
  /** State */
  state: string;
}

/** TeamCreate */
export interface TeamCreate {
  /** Description */
  description?: string | null;
  /** Name */
  name: string;
}

/** TeamMemberAdd */
export interface TeamMemberAdd {
  /** Role */
  role?: "lead" | "member";
  /** User Id */
  user_id: string;
}

/** TeamMemberRead */
export interface TeamMemberRead {
  /** Role */
  role: string;
  /** User Id */
  user_id: string;
}

/** TeamRead */
export interface TeamRead {
  /** Created At */
  created_at: string;
  /** Description */
  description?: string | null;
  /** Id */
  id: string;
  /** Members */
  members?: TeamMemberRead[];
  /** Name */
  name: string;
  /** Slug */
  slug: string;
}

/** TeamUpdate */
export interface TeamUpdate {
  /** Description */
  description?: string | null;
  /** Name */
  name?: string | null;
}

/** TicketAssign */
export interface TicketAssign {
  /** Skill */
  skill?: string | null;
  /** Strategy */
  strategy?: "round_robin" | "load_balanced" | "team" | "skill";
  /** Team Id */
  team_id?: string | null;
  /** User Id */
  user_id?: string | null;
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
  /** Required Skills */
  required_skills?: string[];
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
  /** First Response Due At */
  first_response_due_at?: string | null;
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
  /** Required Skills */
  required_skills?: string[];
  /** Resolution Due At */
  resolution_due_at?: string | null;
  /** Resolved At */
  resolved_at?: string | null;
  /** Sla Breached At */
  sla_breached_at?: string | null;
  /** Status */
  status: string;
  /** Subject */
  subject: string;
  /** Tags */
  tags?: string[];
  /** Team Id */
  team_id?: string | null;
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
  /** Mentions */
  mentions?: string[];
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
  /** First Response Due At */
  first_response_due_at?: string | null;
  /** Id */
  id: string;
  /** Metadata */
  metadata?: Record<string, unknown>;
  /** Priority */
  priority: string;
  /** Reference */
  reference: string;
  requester?: RequesterRead | null;
  /** Required Skills */
  required_skills?: string[];
  /** Resolution Due At */
  resolution_due_at?: string | null;
  /** Resolved At */
  resolved_at?: string | null;
  /** Sla Breached At */
  sla_breached_at?: string | null;
  /** Status */
  status: string;
  /** Subject */
  subject: string;
  /** Tags */
  tags?: string[];
  /** Team Id */
  team_id?: string | null;
}

/** TicketUpdate */
export interface TicketUpdate {
  /** Assignee User Id */
  assignee_user_id?: string | null;
  /** Clear Assignee */
  clear_assignee?: boolean;
  /** Clear Team */
  clear_team?: boolean;
  /** Priority */
  priority?: "low" | "normal" | "high" | "urgent" | null;
  /** Required Skills */
  required_skills?: string[] | null;
  /** Status */
  status?: "open" | "pending" | "resolved" | "closed" | null;
  /** Subject */
  subject?: string | null;
  /** Tags */
  tags?: string[] | null;
  /** Team Id */
  team_id?: string | null;
}

/** TriggerAction */
export interface TriggerAction {
  /** Type */
  type: "set_status" | "set_priority" | "add_tag" | "remove_tag" | "set_team" | "notify";
  /** Value */
  value: string;
}

/** TriggerCondition */
export interface TriggerCondition {
  /** Field */
  field: "status" | "priority" | "tag" | "subject";
  /** Op */
  op?: "is" | "contains";
  /** Value */
  value: string;
}

/** TriggerCreate */
export interface TriggerCreate {
  /** Actions */
  actions?: TriggerAction[];
  /** Conditions */
  conditions?: TriggerCondition[];
  /** Event */
  event: "ticket.created" | "ticket.replied" | "ticket.updated";
  /** Is Active */
  is_active?: boolean;
  /** Name */
  name: string;
  /** Position */
  position?: number;
}

/** TriggerRead */
export interface TriggerRead {
  /** Actions */
  actions?: Record<string, unknown>[];
  /** Conditions */
  conditions?: Record<string, unknown>[];
  /** Created At */
  created_at: string;
  /** Event */
  event: string;
  /** Id */
  id: string;
  /** Is Active */
  is_active: boolean;
  /** Name */
  name: string;
  /** Position */
  position: number;
  /** Updated At */
  updated_at: string;
}

/** TriggerUpdate */
export interface TriggerUpdate {
  /** Actions */
  actions?: TriggerAction[] | null;
  /** Conditions */
  conditions?: TriggerCondition[] | null;
  /** Event */
  event?: "ticket.created" | "ticket.replied" | "ticket.updated" | null;
  /** Is Active */
  is_active?: boolean | null;
  /** Name */
  name?: string | null;
  /** Position */
  position?: number | null;
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
  branding: BrandingRead;
  business_hours: BusinessHoursRead;
  /** Locale */
  locale?: string;
  notifications: NotificationSettingsRead;
  sla: SlaSettingsRead;
  sso: SsoSettingsRead;
}

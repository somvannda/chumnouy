# Chumnouy Architecture & Decision Records

Status: Proposal — documentation first; no application code yet.
Owners: Engineering
Scope: repo layout, tenancy model, auth, API surface, the agent console, the AI
assistant, webhooks, and the incremental build order.

Related: `docs/api.md`, `docs/tenancy.md`, `docs/reuse-from-chmaba.md`,
`AGENTS.md`.

## 1. Goal

Chumnouy is a standalone, multi-tenant, API-first **tickets & support service**.
An integrator signs up, receives an API key, and calls a stable REST API to open
and manage support conversations. Every product that would otherwise rebuild a
support inbox, a ticket thread, attachments, statuses, SLA and an AI assistant
should instead point at Chumnouy once.

The first client is **Chmaba POS**, which today owns a support system
(`support_tickets`, `app/services/support*.py`, the help centre). Chumnouy lifts
that capability out, generalizes it, and gives it a public API so it is never
rebuilt per product.

## 2. Non-goals

- **Outbound notification delivery** belongs to **Notifyr**. Chumnouy raises
  events and calls Notifyr; it never sends email/SMS/Telegram itself.
- No billing/metering engine in v1 (usage counts are recorded, not charged).
- No raw database access for the AI assistant (see ADR-008).
- No multi-region / sharding in v1.

## 3. Decisions (ADRs)

### ADR-001: API-first; the console is just another client
The REST API is the product. The React console (agents/workspace admin) is built
on the **same public endpoints** an integrator uses, with no privileged private
API. This guarantees the API is complete and documented, and keeps one code path.

### ADR-002: Separate repository and deployable
Chumnouy is its own repo and its own service, not a module inside the Chmaba POS
monorepo. Independent release cadence, independent scaling, and a hard boundary
so any product can adopt it. It mirrors the Chmaba stack (ADR-006) so the team's
tooling and UI carry over unchanged.

### ADR-003: Tenancy is Account → Workspace → Integration
The single most important generalization. Chmaba's `company_id` / `store_id`
becomes:

| Concept | Meaning |
|---|---|
| **Account** | The billing/ownership entity that signs up. Owns workspaces. |
| **Workspace** | The hard data-isolation boundary. Every row carries `workspace_id`. |
| **Integration** | A registered client app inside a workspace (e.g. "Chmaba POS"). Owns API keys, webhooks, allowed scopes and settings. |

A workspace can have several integrations (POS + website + mobile). Tickets
record which integration created them (`source_integration_id`) so a workspace
can see per-product volume.

### ADR-004: API keys, scoped, test + live
Machine clients authenticate with a key: `chm_live_<random>` / `chm_test_<random>`.
The key carries scopes (`tickets:read`, `tickets:write`, `webhooks:manage`,
`assistant:use`, …) and an environment. Only a hash of the secret is stored.
Keys are created/rotated/revoked per integration. Human users (agents) use
email + password JWT, identical to Chmaba POS.

### ADR-005: One contract — REST + committed OpenAPI
FastAPI emits OpenAPI; `chumnouy_api/openapi.json` is committed and CI fails on
drift. `packages/api-client` is generated from it and consumed by the console.
Same discipline as Chmaba (ADR-005 there).

### ADR-006: Reuse the Chmaba POS stack and design system
Backend: FastAPI + PostgreSQL + Alembic + pytest. Frontend: React + Vite +
Tailwind + react-router + lucide-react. Styling comes from `@chmaba/ui`
(`packages/ui`, vendored from `Chmaba/packages/ui`) so Chumnouy looks identical to
Chmaba POS, including dark mode and the Inter/Niradei/Noto-Khmer font stack.

### ADR-007: Signed, retried webhooks
Outbound events (`ticket.created`, `ticket.replied`, `ticket.status_changed`,
`ticket.resolved`, `ticket.assigned`) are POSTed to integration endpoints with an
HMAC-SHA256 signature header and a timestamp (replay protection). Deliveries are
queued, retried with backoff, and recorded in `webhook_deliveries` for inspection.
Webhook payloads are the same shape as the corresponding API resource.

### ADR-008: Reuse the AI engine, grounded and read-only
Port `app/services/support.py` + `support_tools.py` + `support_content.py` +
`help_repo.py`. Answers come from the workspace's knowledge corpus and from
**read-only, workspace-scoped** data the integrator supplies through a small
"data tool" contract. The model never runs SQL and never writes (no create/refund
style actions). Provider selection/keys reuse the same pattern (`provider`,
`api_key`, `model`, `base_url`) configured per workspace.

### ADR-009: Application-enforced isolation, one schema
All tenant tables share one schema and carry `workspace_id`. Every query in the
repository layer is scoped by the caller's workspace resolved from their
credential. No cross-workspace joins. (Row-level security is a possible later
hardening; not needed for v1 and it complicates migrations.)

### ADR-010: Idempotent, safe-to-retry writes
Every `POST` accepts an `Idempotency-Key` header. A repeated key with the same
body returns the original result instead of creating a duplicate — essential when
the caller is itself retrying (offline POS, flaky network).

### ADR-011: Reference IDs are short, opaque, workspace-scoped
Each ticket gets a human reference (`CMY-1042`) unique per workspace, plus a UUID
primary key. Integrators surface the reference; the UUID is used on the wire.

### ADR-012: The external requester is a first-class identity
A ticket's requester is not necessarily a Chumnouy user. Integrations pass an
`external_id` (their own customer id) plus optional name/email/phone; Chumnouy
stores it on a `Requester` row keyed by `(workspace_id, requester_external_id)`.
This is what lets any product's end users open tickets without accounts here.

## 4. Target repository layout

```
chumnouy.chmaba.com/
├─ chumnouy_api/             # FastAPI backend
│  ├─ app/
│  │  ├─ api/                # v1.py (machine+console), console.py, admin.py, public.py
│  │  ├─ services/           # tickets.py, assistant.py, assistant_tools.py, webhooks.py, knowledge.py
│  │  ├─ models.py
│  │  ├─ schemas.py
│  │  ├─ deps.py             # auth: API key + JWT, workspace resolution
│  │  ├─ config.py
│  │  └─ main.py
│  ├─ alembic/
│  ├─ scripts/               # export_openapi.py
│  ├─ tests/                 # pytest
│  ├─ requirements.txt
│  └─ .env.example
├─ apps/
│  └─ web/                   # agent console + workspace admin (React + Vite)
│     └─ src/
│        ├─ features/        # inbox, ticket, knowledge, integrations, settings
│        ├─ components/      # incl. ported SupportChat, ui primitives
│        ├─ lib/             # api client, auth, theme
│        └─ main.jsx
├─ packages/
│  ├─ ui/                    # @chmaba/ui (vendored)
│  └─ api-client/            # generated TS client
├─ docs/
├─ deploy/
└─ README.md
```

## 5. Domain model

```
Account ──< Workspace ──< Integration ──< ApiKey
                 │              └────────< Webhook ──< WebhookDelivery
                 ├──< Agent  (membership: owner|admin|agent)
                 ├──< Requester
                 ├──< Ticket ──< TicketMessage ──< Attachment
                 │        └──< TicketEvent (audit timeline)
                 ├──< KnowledgeArticle
                 └──< AssistantConversation ──< AssistantMessage
```

| Table | Key columns (beyond `id`, `created_at`, `updated_at`) |
|---|---|
| `accounts` | `name`, `slug`, `status` |
| `workspaces` | `account_id`, `name`, `slug`, `settings` (JSON) |
| `users` | `email`, `password_hash`, `name`, `is_verified` |
| `memberships` | `workspace_id`, `user_id`, `role` |
| `integrations` | `workspace_id`, `name`, `slug`, `scopes`, `settings`, `is_active` |
| `api_keys` | `integration_id`, `name`, `key_prefix`, `secret_hash`, `scopes`, `environment`, `last_used_at`, `revoked_at` |
| `requesters` | `workspace_id`, `external_id`, `name`, `email`, `phone`, `metadata` |
| `tickets` | `workspace_id`, `reference`, `subject`, `status`, `priority`, `assignee_user_id`, `requester_id`, `source_integration_id`, `tags`, `metadata`, `first_response_at`, `resolved_at` |
| `ticket_messages` | `ticket_id`, `author_type` (`requester\|agent\|system\|ai`), `author_user_id`, `visibility` (`public\|internal`), `body`, `metadata` |
| `ticket_attachments` | `ticket_id`, `message_id?`, `workspace_id`, `url`, `content_type`, `byte_size`, `filename`, `position` |
| `ticket_events` | `ticket_id`, `type`, `actor_type`, `actor_id`, `data` (JSON) |
| `knowledge_articles` | `workspace_id`, `section`, `title`, `body`, `verticals`, `roles`, `locale`, `is_active`, `position` |
| `assistant_conversations` | `workspace_id`, `ticket_id?`, `created_by` |
| `assistant_messages` | `conversation_id`, `role`, `content`, `tool_name`, `tool_payload` |
| `webhooks` | `integration_id`, `url`, `secret`, `events`, `is_active` |
| `webhook_deliveries` | `webhook_id`, `event`, `payload`, `status`, `attempts`, `response_status`, `response_body`, `next_attempt_at` |
| `idempotency_keys` | `workspace_id`, `key`, `request_hash`, `response_body`, `expires_at` |

## 6. Auth & isolation

Three credential types, all resolving to a **workspace context** in `deps.py`:

1. **API key** (`Authorization: Bearer chm_live_…` or `X-Api-Key`) → resolves
   integration → workspace + scopes. Used by machine integrations.
2. **User JWT** (console) → resolves membership → workspace + role.
3. **Requester token** (public/widget/customer portal) → resolves a single
   requester's tickets only.

Every endpoint declares the scopes/roles it needs; `deps.py` enforces workspace
scoping so a service function never sees another workspace's rows.

## 7. Surfaces

- **Machine API** — `/v1/*` (tickets, requesters, attachments, knowledge,
  assistant, webhooks). API-key auth.
- **Console API** — same `/v1/*` resources, JWT auth, plus `/v1/console/me`,
  inbox views, assignment, bulk actions.
- **Public API** — `/v1/public/*` requester token (widget / customer portal).
- **Admin API** — `/api/admin/*` platform-operator only (accounts, workspaces,
  usage, abuse). A separate router like Chmaba's `admin.py`.

See `docs/api.md` for the concrete endpoint list.

## 8. Integrations & interoperability

- **Chmaba POS** is the reference client: it replaces `support_tickets` with
  Chumnouy API calls and points its help centre at the Chumnouy knowledge API.
- **Notifyr** is called by Chumnouy when a ticket event must reach a person
  (new ticket to agents, reply to requester, SLA breach). Chumnouy stores no
  email transport.
- Any other product integrates the same way: create an integration, take a key,
  post tickets. Nothing else is required.

## 9. Observability & operations

- Request logs include workspace + integration id (never secrets or message
  bodies at info level).
- Webhook deliveries are inspectable and replayable from the console.
- Usage counters per workspace (`tickets_created`, `assistant_requests`,
  `webhook_deliveries`) feed future metering.
- Health (`GET /health`) for the load balancer; readiness checks the DB.

## 10. Build order (each step shippable, green CI)

1. **Docs** (this) — architecture, API contract, tenancy, reuse notes.
2. **Skeleton** — `chumnouy_api` with health + config + db + alembic; `apps/web`
   boots with `@chmaba/ui` styling; CI for API + web.
3. **Tenancy + auth** — accounts, workspaces, users, memberships, integrations,
   API keys; signup/login; key auth in `deps.py`.
4. **Tickets core** — create/list/get/update, messages, statuses, assignment,
   reference IDs, idempotency. Console inbox + ticket view.
5. **Attachments** — staged upload + claim (ported from Chmaba).
6. **Webhooks** — register, sign, deliver, retry, inspect.
7. **Knowledge + AI assistant** — articles, retrieval, streaming chat, read-only
   data tools (ported and generalized).
8. **Requesters + public/widget** — requester tokens, customer portal, embeddable
   widget.
9. **Notifyr integration** — raise ticket events to Notifyr; per-workspace prefs.

## 11. Risks & open questions

1. **Widget vs API-only** — do we ship an embeddable JS widget in v1, or API +
   customer portal first? (Recommend portal first; widget later.)
2. **AI data tools contract** — how does an integrator expose *their* data to the
   assistant safely? (Proposed: they register read-only tool handlers we call
   back into; decide before §10.7.)
3. **SLA model** — business hours per workspace vs simple calendar hours?
4. **Email inbound** — reply-by-email into a ticket (needs inbound parsing; likely
   a Notifyr responsibility).
5. **Metering/billing** — when do usage counts become invoices?
6. **UI package sharing** — vendored copies in each repo now; extract to a real
   published `@chmaba/ui` if drift becomes a problem.

# Chumnouy API (v1) — Contract

Status: Draft proposal. The committed `chumnouy_api/openapi.json` is the source of
truth once code exists; this document is the design intent.

Base URL: `https://api.chumnouy.chmaba.com/v1` (dev: `http://127.0.0.1:8100/v1`).

## Conventions

- JSON in, JSON out.
- Machine auth: `Authorization: Bearer chm_live_…` (or `X-Api-Key`).
- Console auth: `Authorization: Bearer <jwt>`.
- Writes accept `Idempotency-Key: <uuid>`; a repeat returns the original result.
  Implemented for ticket creation and replies.
- Pagination: `?limit=&cursor=`; response carries `{ "data": [...], "next_cursor": "…" }`.
- Errors: `{ "error": { "code": "…", "message": "…", "details": {…} } }` with a
  proper HTTP status. `429` includes `Retry-After`. The public surface is rate
  limited per client IP.
- Every resource includes `id` (UUID) + `created_at`; tickets also carry
  `reference` (`CMY-1042`).
- A workspace may cap its monthly ticket volume
  (`workspace.settings.quota.tickets_per_month`); exceeding it returns `429`
  (`too_many_requests`). `0`/absent = unlimited.

## 1. Integrations & keys (console)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/integrations` | Register a client app in the workspace |
| `GET` | `/v1/integrations` | List integrations |
| `PATCH` | `/v1/integrations/{id}` | Rename, set scopes/settings, enable/disable |
| `POST` | `/v1/integrations/{id}/keys` | Create an API key (returns secret **once**) |
| `GET` | `/v1/integrations/{id}/keys` | List keys (prefix + metadata only) |
| `POST` | `/v1/keys/{id}/revoke` | Revoke a key |

Scopes: `tickets:read`, `tickets:write`, `requesters:read`, `requesters:write`,
`knowledge:read`, `knowledge:write`, `assistant:use`, `webhooks:manage`.

## 2. Tickets

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/tickets` | Create a ticket (+ first message) |
| `GET` | `/v1/tickets` | List/filter: `status`, `priority`, `assignee`, `tag`, `integration`, `q`, `created_after/before` |
| `GET` | `/v1/tickets/{id}` | Ticket + thread + attachments |
| `PATCH` | `/v1/tickets/{id}` | `subject`, `status`, `priority`, `assignee_user_id`, `tags`, `metadata` |
| `POST` | `/v1/tickets/{id}/messages` | Reply (`visibility`: `public` \| `internal`) |

Messages are `text` by default; pass `body_format: "html"` (or `message_format`
on ticket create) to send rich text, which is **stored sanitised** (strict tag/
attribute allowlist) so any client can render it verbatim.
| `POST` | `/v1/tickets/{id}/assign` | Assign/claim |
| `POST` | `/v1/tickets/{id}/resolve` | Resolve (optional note) |
| `POST` | `/v1/tickets/{id}/reopen` | Reopen |
| `POST` | `/v1/tickets/{id}/attachments` | Attach an uploaded file to the ticket |
| `GET` | `/v1/tickets/{id}/events` | Timeline/audit |

### Create ticket — request

```json
{
  "subject": "Card reader not charging",
  "message": "The terminal stopped charging this morning.",
  "requester": {
    "external_id": "cust_88213",
    "name": "Sok Dara",
    "email": "dara@example.com",
    "phone": "+855…"
  },
  "priority": "normal",
  "tags": ["hardware"],
  "metadata": { "store_id": "store_7", "order_ref": "ORD-2231" },
  "attachment_ids": ["…"],
  "source": { "integration": "chmaba-pos" }
}
```

### Create ticket — response (201)

```json
{
  "id": "6f1…",
  "reference": "CMY-1042",
  "subject": "Card reader not charging",
  "status": "open",
  "priority": "normal",
  "assignee_user_id": null,
  "requester": { "id": "…", "external_id": "cust_88213", "name": "Sok Dara" },
  "tags": ["hardware"],
  "metadata": { "store_id": "store_7" },
  "attachments": [],
  "created_at": "2026-10-14T09:12:00Z"
}
```

## 3. Requesters
| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/requesters` | List/search by external id, email, name |
| `GET` | `/v1/requesters/{id}` | Detail + their tickets |
| `PATCH` | `/v1/requesters/{id}` | Update name/email/phone/metadata |
| `POST` | `/v1/requesters/{id}/portal-token` | Issue/rotate the requester's public-surface token (shown once) |

Scopes: `requesters:read`, `requesters:write`. A requester is created implicitly
when a ticket is opened with a new `external_id`.

## 4. Attachments

Staged upload then claim (ported from Chmaba):

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/uploads` | Upload an image/file; returns `{ "id", "url" }` (unowned) |
| `POST` | `/v1/tickets/{id}/attachments` | Claim staged uploads: `{ "attachment_ids": [...] }` |

Rules: only the caller's own, still-unowned rows can be claimed; foreign or
already-claimed ids are rejected with `400`. Any type in `UPLOAD_SUFFIXES`
(default images + common documents/archives) up to `MAX_UPLOAD_BYTES` (5 MB), at
most 5 per message; each attachment carries a `kind` (`image` or `file`). Ticket
create and reply accept an `attachment_ids` list that claims staged uploads in the
same request (opening files land on the ticket; reply files land on the message).

## 5. Knowledge (help corpus)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/knowledge/articles` | List (filter: `section`, `q`, `locale`, `active`) |
| `POST` | `/v1/knowledge/articles` | Create |
| `GET` | `/v1/knowledge/articles/{id}` | Detail |
| `PATCH` | `/v1/knowledge/articles/{id}` | Update / deactivate (`is_active: false`) |
| `POST` | `/v1/knowledge/articles/{id}/restore` | Reactivate |

Articles are workspace-scoped and soft-deleted via `is_active`. `slug` is derived
from the title when omitted and de-duplicated per workspace + `locale`
(`en`/`km`); `verticals`/`roles` are optional targeting hints for retrieval. A new
workspace is seeded with a small generic default corpus. Scopes:
`knowledge:read`, `knowledge:write`.

## 6. AI assistant

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/assistant/chat` | `text/event-stream`; grounded answer with cited articles |
| `GET` | `/v1/assistant/conversations` | List conversations |
| `GET` | `/v1/assistant/conversations/{id}` | Transcript |
| `POST` | `/v1/assistant/feedback` | `{ message_id, rating: up|down, comment? }` |
| `POST` | `/v1/tickets/{id}/assistant/draft` | AI-drafted agent reply (rewrite/suggest) |

Request body (`/assistant/chat`):

```json
{
  "question": "How do I refund an order?",
  "conversation_id": null,
  "history": [{ "role": "user", "content": "…" }],
  "locale": "en",
  "context": { "vertical": "electronics", "role": "owner" }
}
```

Stream events: `citation`, `token`, `done`, `error`. Scope: `assistant:use`.
Answers are grounded in the workspace knowledge corpus (retrieval by locale and
optional vertical/role); each stream starts with a `citation` event listing the
articles used. The provider/key is configured per workspace (`workspace.settings`:
`ai_provider`, `ai_api_key`, `ai_model`, `ai_base_url`), falling back to the
`AI_*` environment variables; an unconfigured workspace returns `400`.

## 7. Webhooks

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/webhooks` | Register `{ url, events, is_active }` (secret returned once) |
| `GET` | `/v1/webhooks` | List registrations |
| `PATCH` | `/v1/webhooks/{id}` | Update url/events/active |
| `DELETE` | `/v1/webhooks/{id}` | Delete |
| `GET` | `/v1/webhooks/{id}/deliveries` | Delivery log |
| `POST` | `/v1/webhooks/deliveries/{id}/replay` | Replay a delivery |

Events: `ticket.created`, `ticket.replied`, `ticket.status_changed`,
`ticket.assigned`, `ticket.resolved`, `ticket.reopened`, `sla.breached`.

Delivery headers:

```
X-Chumnouy-Event: ticket.created
X-Chumnouy-Delivery: <uuid>
X-Chumnouy-Timestamp: 1760432400
X-Chumnouy-Signature: sha256=<hmac(secret, timestamp + "." + body)>
```

The signing secret is returned once at registration and never again. A delivery
retries with backoff (10s → 60s → 5m → 30m, then `failed`; `WEBHOOK_MAX_ATTEMPTS`,
default 5) and can be re-queued with the replay endpoint. A background worker
drains due deliveries when `WEBHOOK_WORKER_ENABLED=true`; otherwise run an
external process that drives the worker loop.

## 8. Console-only (JWT)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/console/me` | Current user, workspace, role, scopes |
| `GET` | `/v1/console/inbox` | Saved views: mine, unassigned, open, overdue |
| `GET` | `/v1/console/overview` | Counts, first-response time, SLA, volume by integration |
| `POST` | `/v1/console/bulk` | Apply one action (status/priority/assignee/team/tags) to many tickets (`tickets:write`) |
| `GET` | `/v1/console/settings` | Current workspace settings (AI + notifications) |
| `PATCH` | `/v1/console/settings/ai` | Set AI provider/model/base_url/api_key (secret write-only) |
| `PATCH` | `/v1/console/settings/notifications` | Set the Notifyr url/key override (secret write-only) |
| `PATCH` | `/v1/console/settings/locale` | Set the workspace locale (`en`/`km`) |
| `PATCH` | `/v1/console/settings/sla` | Set per-priority response/resolution targets (minutes) |

Settings are owner/admin only; secrets are never returned, only a `*_set` flag.

## 9. Public (requester token)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/public/tickets` | Open a ticket from the widget/portal |
| `GET` | `/v1/public/tickets` | My tickets |
| `GET` | `/v1/public/tickets/{id}` | My ticket + public messages |
| `POST` | `/v1/public/tickets/{id}/messages` | Reply |
| `POST` | `/v1/public/tickets/{id}/csat` | Rate the ticket (`rating`: `up`/`down`, `comment?`) |

Auth: a requester portal token (`Authorization: Bearer rqt_…` or
`X-Requester-Token`), issued via `/v1/requesters/{id}/portal-token`. Only public
messages are ever returned — internal notes and the requester's own scope are
enforced server-side, so a token can never read another requester's ticket.

`packages/widget/` ships a dependency-free embeddable launcher over these
endpoints (list, open, reply) for integrators who want the portal without
building UI.

## 10. Admin (platform operator)

`/api/admin/*` — accounts, workspaces, usage, quota, abuse, impersonation. Separate
router and credential (a console user whose `platform_role` is `admin`/`super_admin`),
never reachable with a tenant API key. Mirrors Chmaba's `admin.py` split.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/admin/accounts` | Accounts + workspace counts |
| `GET` | `/admin/workspaces` | List/search, filter `active` |
| `GET` | `/admin/workspaces/{id}` | Detail: counts + quota |
| `PATCH` | `/admin/workspaces/{id}` | Enable/disable, set quota |
| `GET` | `/admin/usage` | Platform-wide counts |

## 11. Auth (console users)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/auth/signup` | Create account + first workspace + owner |
| `POST` | `/v1/auth/login` | JWT |
| `POST` | `/v1/auth/verify-email` | Confirm email |
| `POST` | `/v1/auth/request-reset` / `/auth/reset` | Password reset |
| `GET` | `/v1/auth/me` | Profile |
| `POST` | `/v1/workspaces/{id}/invitations` | Invite teammate |

## 12. Notifyr hand-off

Chumnouy calls Notifyr's API (not exposed here) for human-facing delivery. The
hand-off contract is: Chumnouy emits an event with `workspace`, `ticket_ref`,
`recipient` and template variables; Notifyr owns transport, retries and
preferences. Configured per workspace under `/v1/console/settings/notifications`.

Implemented (`app/services/notifyr.py`): `POST {notifyr_api_url}/v1/events` with
`Authorization: Bearer {notifyr_api_key}`, body `{ event, workspace, ticket,
recipient, variables }`. Raised on ticket create (recipient `null` → Notifyr
resolves the workspace's agents) and on public replies (requester email for an
agent reply, `null` for a requester reply). Events are **queued**
(`notifyr_events`) inside the ticket transaction and handed off by the worker with
retry/backoff; an unconfigured workspace enqueues nothing.

## 13. Search

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/search` | Search tickets, messages and articles (`q`, `types`, `limit`) |

Workspace-scoped; scope `tickets:read`. `types` is a comma-separated subset of
`ticket,message,article`. Each result carries `type`, `id`, `title`, `snippet`
and, for tickets/messages, `ticket_id` + `reference`.

## 14. Audit log

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/audit` | Ticket events (`type`, `actor_type`, `ticket_id`, `limit`, `cursor`) |

Workspace-scoped; scope `tickets:read`. A filterable, newest-first trail over
`ticket_events` (`ticket.created`, `ticket.replied`, `ticket.updated`,
`ticket.resolved`, …) with `data` (the changed fields / visibility / team).

## 15. Inbound email

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/inbound/email` | Hand off a parsed inbound email → create or append a ticket |

Scope `tickets:write`; called by Notifyr (which owns transport + parsing). Body:
`{ from_email, from_name?, subject, body, body_format?, message_id?, in_reply_to? }`.
`in_reply_to` threads the message onto the matching ticket (else the sender's
latest open ticket, else a new ticket); the sender is created as a requester on
first contact. A new ticket is subject to the workspace quota.

## 16. Canned responses

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/canned-responses` | List saved replies |
| `POST` | `/v1/canned-responses` | Create |
| `GET` | `/v1/canned-responses/{id}` | Detail |
| `PATCH` | `/v1/canned-responses/{id}` | Update |
| `DELETE` | `/v1/canned-responses/{id}` | Delete |

Workspace-scoped; `tickets:read` / `tickets:write`. Body carries `title`,
`body` and `body_format` (`text`/`html`, sanitised). Titles are unique per
workspace.

## 17. Triggers

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/triggers` | List rules |
| `POST` | `/v1/triggers` | Create |
| `GET` | `/v1/triggers/{id}` | Detail |
| `PATCH` | `/v1/triggers/{id}` | Update / deactivate |
| `DELETE` | `/v1/triggers/{id}` | Delete |

Workspace-scoped; `tickets:read` / `tickets:write`. A trigger fires on an
`event` (`ticket.created`, `ticket.replied`, `ticket.updated`) when its
`conditions` match and runs its `actions` on the ticket:
`conditions` = `[{field: status|priority|tag|subject, op: is|contains, value}]`;
`actions` = `[{type: set_status|set_priority|add_tag|remove_tag|set_team, value}]`.
Evaluated once per write, in `position` order; each application records a
`trigger.applied` audit event.

## 18. Reports

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/reports/summary` | Ticket counts, response/resolution averages, SLA compliance |

Workspace-scoped; scope `tickets:read`. Returns `total`, `by_status`,
`by_priority`, `breached`, `sla_compliance` (%), `avg_first_response_minutes` /
`avg_resolution_minutes` (null when no data), and `csat_responses` /
`csat_positive_pct`. Computed on the fly from the ticket table.

## 19. Help centre (public)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/public/help/{workspace_slug}` | Index: sections + articles (`section`, `q`, `locale`) |
| `GET` | `/v1/public/help/{workspace_slug}/articles/{slug}` | One article (`locale`) |

**Unauthenticated**, addressed by workspace slug; only active articles are
exposed. Rate-limited by the public middleware.

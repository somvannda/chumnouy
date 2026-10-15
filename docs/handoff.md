# Handoff & Roadmap

A clean stopping point. Everything below is committed, lint-clean and green.
Each task in §4 is sized to be started and finished in its own chat session.

## 1. Where things stand

Status: tenancy, API-key auth, the ticket domain, attachments, webhooks, the
knowledge base, the AI assistant, the public requester surface (with an embeddable
widget), the agent console, the platform admin router and the Notifyr hand-off are
implemented and tested.

| Area | State |
|---|---|
| Repo layout, docs, ADRs, shared `@chmaba/ui` tokens | Done |
| FastAPI skeleton (config, db, alembic, `export_openapi.py`, CI) | Done |
| Agent console: auth, inbox (saved views), ticket view + composer, integrations & keys | Done |
| Tenancy: Account → Workspace → Integration + API keys | Done |
| Console auth: signup / login / me | Done |
| Machine auth: scoped API keys (test/live) + `whoami` | Done |
| Tickets: create / list / get / update / reply / resolve / reopen / events | Done |
| Attachments: staged upload + claim, allowlisted types + `kind`, content-addressed store | Done |
| Webhooks: registrations, signed delivery, retry/backoff, delivery log + replay | Done |
| Knowledge: workspace articles, sections/locales, seeded default corpus | Done |
| AI assistant: grounded streaming chat, conversations, feedback, agent draft | Done |
| Requesters & public surface: CRUD, portal tokens, requester-token tickets | Done |
| Admin router: accounts, workspaces, usage, quota (separate platform credential) | Done |
| Admin console: platform usage/accounts/workspaces, quota (platform admins) | Done |
| Notifyr hand-off: ticket events queued + delivered with retry/backoff | Done |
| Workspace settings: per-workspace AI provider + Notifyr override (console) | Done |
| Idempotency: ticket creation and replies honour `Idempotency-Key` | Done |
| Public surface: per-IP rate limiting (429 + `Retry-After`) | Done |
| Errors: uniform `{error:{code,message,details}}` envelope | Done |
| Embeddable widget: dependency-free launcher over the public surface | Done |
| Rich text: sanitised HTML message bodies (`body_format`) | Done |
| Search: workspace-scoped tickets / messages / articles | Done |
| Teams: groups + membership, role permissions, ticket team assignment | Done |
| Audit log: filterable ticket-event trail (`GET /v1/audit`) | Done |
| Quotas: monthly ticket cap per workspace (429 when exceeded) | Done |
| Inbound email: `POST /v1/inbound/email` with threading (P1) | Done |
| i18n: workspace locale (en/km), surfaced to Notifyr for delivery | Done |
| SLA: per-priority response/resolution targets, due dates, breach sweep | Done |
| Canned responses: workspace saved replies (CRUD) (P3) | Done |
| Triggers: event-based rules (conditions → actions) (P3) | Done |
| Reports: workspace summary (counts, averages, SLA compliance) (P4) | Done |
| CSAT: requester satisfaction ratings + report (P4) | Done |
| Migrations | `0001`…`0018` (`0018_csat`) |
| Tests | 118 API (in-memory SQLite, incl. an end-to-end journey) + 7 web (`node --test`) |

Backlog complete (C1–C8, D1–D5). Remaining work is process: CI/merge and review.

## 2. Run & verify locally

```powershell
# API
cd chumnouy_api
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest                       # 118 passing
python -m ruff check app tests
python scripts\export_openapi.py        # regenerate committed openapi.json
python scripts\smoke_live.py            # live smoke vs the real DB (needs alembic upgrade head)
uvicorn app.main:app --reload --port 8100

# Console
cd apps\web; npm install; npm test; npm run build; npm run dev   # http://localhost:8101
```

## 3. Conventions (see `AGENTS.md`)

- Branch per unit of work off `main`: `feat/…`, `fix/…`, `docs/…`, `chore/…`.
- Conventional Commits. CI gate = green.
- Any endpoint change: regenerate and commit `chumnouy_api/openapi.json`.
- Run the app, alembic and pytest from `chumnouy_api`; `.env` and `MEDIA_ROOT`
  resolve from that directory.
- Alembic: chain `down_revision` to the single head (`alembic heads` = one).
- New JSON columns: the ORM attribute must not be named `metadata` (SQLAlchemy
  reserves it) — use `metadata_json` with `mapped_column("metadata", JSON)` and
  build read models explicitly.
- Cross-app: Chumnouy does **not** send notifications itself; it calls Notifyr.

> Note: both repos currently have no git remote, so history was bootstrapped
> directly on `main`. Once a GitHub remote + CI exist, switch to the branch/PR
> flow above for every change.

## 4. Task backlog (one session each)

### C1 — Attachments ✅
Staged upload + claim (port `bind_attachments` / `ticket_detail_read` from
Chmaba POS). `POST /v1/uploads` → unowned `ticket_attachments`; claim via
`POST /v1/tickets/{id}/attachments` or the `attachment_ids` field on ticket
create / reply. Local content-addressed media store under `MEDIA_ROOT`, served
from `MEDIA_URL_PREFIX`. Migration `0003_attachments`.

### C2 — Webhooks ✅
`webhooks` + `webhook_deliveries`, HMAC-signed delivery with replay protection,
retry/backoff worker, delivery log and replay endpoint. Events:
`ticket.created`, `ticket.replied`, `ticket.status_changed`, `ticket.assigned`,
`ticket.resolved`, `ticket.reopened`. Migration `0004_webhooks`.

### C3 — Knowledge base ✅
`knowledge_articles` CRUD (workspace-scoped), sections, locales (en/km),
`verticals`/`roles` metadata, seeded default corpus (seeded on signup).
Migration `0005_knowledge`.

### C4 — AI assistant ✅
Provider plumbing reused from Chaba's `services/ai.py` (per-workspace settings +
env fallback), retrieval over the knowledge corpus, streaming
`POST /v1/assistant/chat`, conversations, `feedback`, agent draft endpoints.
Migration `0006_assistant`.

### C5 — Requesters + public surface ✅
`requesters` CRUD (already modelled), requester portal tokens, customer portal
endpoints (`/v1/public/tickets`) returning public messages only. Embeddable
widget still to come. Migration `0007_requesters`.

### C6 — Console UI ✅
Signup/login screens, inbox (saved views), ticket view with thread + composer,
integrations & API-key management. Reuses `@chmaba/ui`. Web tests run under
`node --test`.

### C7 — Admin router (platform operator) ✅
`/api/admin/*`: accounts, workspaces, usage, quota. Separate credential
(`platform_role`), never reachable with a tenant key.

### C8 — Notifyr hand-off ✅
Ticket events are queued (`notifyr_events`) inside the ticket transaction and
handed off to Notifyr by the worker with retry/backoff (new ticket → agents,
public reply → requester / agents). A ticket write never blocks on, or fails
because of, Notifyr. Config: `notifyr_api_url`, `notifyr_api_key` (per workspace
or env). Migration `0009_notifyr`.

### D1 — Workspace settings surface ✅
Console endpoints under `/v1/console/settings` to configure a workspace without
direct DB writes: the AI provider (`ai_provider` / `ai_model` / `ai_base_url` /
`ai_api_key`) and the Notifyr override, stored in `workspace.settings`. Secrets
are write-only. Unblocks the assistant end-to-end.

### D2 — Embeddable widget ✅
`packages/widget/chumnouy-widget.js` — a dependency-free launcher over the public
surface, driven by a requester portal token (list, open, reply). No build step.

### D3 — Console depth ✅
The agent console now covers inbox, ticket view, integrations, settings, the
knowledge editor, the grounded assistant (streaming), requesters and webhook
management.

### D4 — Platform admin console ✅
Console UI over `/api/admin/*`: usage cards, accounts, workspaces with
enable/disable and quota. Shown only to platform admins
(`UserRead.platform_role`) behind a route guard.

### D5 — API hardening ✅
**Idempotent ticket creation** (`Idempotency-Key`, migration `0008_idempotency`),
**public-surface rate limiting** (per-IP sliding window, 429 + `Retry-After`) and
the **uniform `{ "error": { code, message, details } }` envelope** all ship.

## 5. Decisions

1. **Console scope** — decided: the React console is in scope and built (C6).
2. **Admin** — decided: an admin router on the same API with a separate
   credential (C7), not a second app.
3. **Widget** — shipped (`packages/widget`, D2) as an optional launcher; the
   customer portal remains available for integrators who prefer their own UI.
4. **AI data tools** — open: how an integrator exposes their own read-only data
   to the assistant. C4 shipped corpus-only grounding.
5. **Shared `@chmaba/ui`** — vendored copy today; publish a package if drift hurts.

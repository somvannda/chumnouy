# Handoff & Roadmap

A clean stopping point. Everything below is committed, lint-clean and green.
Each task in §4 is sized to be started and finished in its own chat session.

## 1. Where things stand

Status: tenancy, API-key auth, the ticket domain, attachments, webhooks, the
knowledge base, the AI assistant, the public requester surface, the agent console,
the platform admin router and the Notifyr hand-off are implemented and tested.

| Area | State |
|---|---|
| Repo layout, docs, ADRs, shared `@chmaba/ui` tokens | Done |
| FastAPI skeleton (config, db, alembic, `export_openapi.py`, CI) | Done |
| Agent console: auth, inbox (saved views), ticket view + composer, integrations & keys | Done |
| Tenancy: Account → Workspace → Integration + API keys | Done |
| Console auth: signup / login / me | Done |
| Machine auth: scoped API keys (test/live) + `whoami` | Done |
| Tickets: create / list / get / update / reply / resolve / reopen / events | Done |
| Attachments: staged upload + claim, content-addressed media store | Done |
| Webhooks: registrations, signed delivery, retry/backoff, delivery log + replay | Done |
| Knowledge: workspace articles, sections/locales, seeded default corpus | Done |
| AI assistant: grounded streaming chat, conversations, feedback, agent draft | Done |
| Requesters & public surface: CRUD, portal tokens, requester-token tickets | Done |
| Admin router: accounts, workspaces, usage, quota (separate platform credential) | Done |
| Notifyr hand-off: ticket events raised to Notifyr (best-effort) | Done |
| Workspace settings: per-workspace AI provider + Notifyr override (console) | Done |
| Migrations | `0001`…`0007` (`0007_requesters`) |
| Tests | 66 API (in-memory SQLite) + 6 web (`node --test`) |

Not built yet: embeddable widget, deeper console screens
(knowledge/assistant/requesters/webhooks), platform admin console, API hardening
(idempotency + error envelope).

> **Out of scope here:** the Chmaba POS support/help cutover. That migration is
> owned by the Chmaba POS project — Chumnouy only provides the API it migrates
> onto, and ships no POS-side code or cutover runbook.

## 2. Run & verify locally

```powershell
# API
cd chumnouy_api
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest                       # 66 passing
python -m ruff check app tests
python scripts\export_openapi.py        # regenerate committed openapi.json
uvicorn app.main:app --reload --port 8100

# Console
cd apps\web; npm install; npm test; npm run build; npm run dev   # http://localhost:8101
```

## 3. Conventions (see `AGENTS.md`)

- Branch per unit of work off `main`: `feat/…`, `fix/…`, `docs/…`, `chore/…`.
- Conventional Commits. CI gate = green.
- Any endpoint change: regenerate and commit `chumnouy_api/openapi.json`.
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
Ticket events are raised to the Notifyr API (new ticket → agents, public reply →
requester / agents). Best-effort: a ticket write never fails because Notifyr is
unreachable or unconfigured. Config: `notifyr_api_url`, `notifyr_api_key`.

### D1 — Workspace settings surface ✅
Console endpoints under `/v1/console/settings` to configure a workspace without
direct DB writes: the AI provider (`ai_provider` / `ai_model` / `ai_base_url` /
`ai_api_key`) and the Notifyr override, stored in `workspace.settings`. Secrets
are write-only. Unblocks the assistant end-to-end.

### D2 — Embeddable widget
A small embeddable JS widget for the public surface (C5), backed by a requester
portal token. Branch: `feat/widget`.

### D3 — Console depth
Knowledge editor, assistant page, requesters view and webhook management in the
agent console (C6 covered auth / inbox / ticket view / integrations only).

### D4 — Platform admin console
Console UI over `/api/admin/*` (accounts, workspaces, usage, quota).

### D5 — API hardening
`Idempotency-Key` on writes and the `{ "error": { code, message, details } }`
envelope from `docs/api.md`; rate limiting on the public surface.

## 5. Decisions

1. **Console scope** — decided: the React console is in scope and built (C6).
2. **Admin** — decided: an admin router on the same API with a separate
   credential (C7), not a second app.
3. **Widget** — open: embeddable JS widget vs customer-portal only (D2).
4. **AI data tools** — open: how an integrator exposes their own read-only data
   to the assistant. C4 shipped corpus-only grounding.
5. **Shared `@chmaba/ui`** — vendored copy today; publish a package if drift hurts.

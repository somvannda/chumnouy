# Handoff & Roadmap

A clean stopping point. Everything below is committed, lint-clean and green.
Each task in §4 is sized to be started and finished in its own chat session.

## 1. Where things stand

Status: tenancy, API-key auth, the ticket domain and attachments are implemented
and tested.

| Area | State |
|---|---|
| Repo layout, docs, ADRs, shared `@chmaba/ui` tokens | Done |
| FastAPI skeleton (config, db, alembic, `export_openapi.py`, CI) | Done |
| Console skeleton (Vite/React/Tailwind on the Chmaba design system) | Done |
| Tenancy: Account → Workspace → Integration + API keys | Done |
| Console auth: signup / login / me | Done |
| Machine auth: scoped API keys (test/live) + `whoami` | Done |
| Tickets: create / list / get / update / reply / resolve / reopen / events | Done |
| Attachments: staged upload + claim, content-addressed media store | Done |
| Migrations | `0001_tenancy`, `0002_tickets`, `0003_attachments` |
| Tests | 29 passing (in-memory SQLite) |

Not built yet: webhooks, knowledge, AI assistant, public/requester surface,
console UI, admin router, Notifyr hand-off, Chmaba POS migration.

## 2. Run & verify locally

```powershell
# API
cd chumnouy_api
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest                       # 29 passing
python -m ruff check app tests
python scripts\export_openapi.py        # regenerate committed openapi.json
uvicorn app.main:app --reload --port 8100

# Console
cd apps\web; npm install; npm run dev    # http://localhost:8101
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

### C2 — Webhooks
`webhooks` + `webhook_deliveries`, HMAC-signed delivery with replay protection,
retry/backoff worker, delivery log and replay endpoint. Events:
`ticket.created`, `ticket.replied`, `ticket.status_changed`, `ticket.assigned`,
`ticket.resolved`. Branch: `feat/webhooks`. Migration `0004_webhooks`.

### C3 — Knowledge base
`knowledge_articles` CRUD (workspace-scoped), sections, locales (en/km),
`verticals`/`roles` metadata, seeded default corpus. Branch: `feat/knowledge`.

### C4 — AI assistant
Provider plumbing reused from Chaba's `services/ai.py` (per-workspace key +
env fallback), retrieval over the knowledge corpus, streaming `POST
/v1/assistant/chat`, `feedback`, agent draft endpoints. Branch: `feat/assistant`.

### C5 — Requesters + public surface
`requesters` CRUD (already modelled), requester tokens, customer portal endpoints
(`/v1/public/tickets`), embeddable widget later. Branch: `feat/public-portal`.

### C6 — Console UI
Signup/login screens, inbox (saved views), ticket view with thread + composer,
integrations & API-key management. Reuse `@chmaba/ui`. Branch: `feat/console-ui`.

### C7 — Admin router (platform operator)
`/api/admin/*`: accounts, workspaces, usage, quota. Separate credential
(`platform_role`), never reachable with a tenant key. Branch: `feat/admin`.

### C8 — Notifyr hand-off
Raise ticket events to the Notifyr API (new ticket → agents, reply → requester,
SLA breach). Config already present (`notifyr_api_url`, `notifyr_api_key`).
Branch: `feat/notifyr-integration`.

### C9 — Chmaba POS migration
Point POS support/help at Chumnouy; delete the in-app support backend once parity
is verified. Owns the cutover runbook. Branch: `feat/pos-support-migration`.

## 5. Open decisions

1. **Console vs API-first scope** — is the React console a priority next, or do we
   stay API-only and build the console later? (Backlog assumes console later.)
2. **Separate `apps/admin`** — v1 assumes an admin router on the same API, not a
   second app. Confirm before C7.
3. **Widget** — ship an embeddable JS widget, or customer-portal only (C5)?
4. **AI data tools contract** — how an integrator exposes their own read-only data
   to the assistant (decide before C4).
5. **Shared `@chmaba/ui`** — vendored copy today; publish a package if drift hurts.

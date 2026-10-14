# Chumnouy

Tickets & support as a service. A standalone, multi-tenant, **API-first** support
platform. Any product — Chmaba POS, Apartment, School, Booking, or a third party —
signs up once, gets an API key, and reuses conversations, attachments, statuses,
SLA, an AI assistant and a help centre **without rebuilding them**.

> Build the support layer once, integrate it everywhere.

## Why it exists

Support was built inside Chmaba POS (`support_tickets`, the AI assistant, the help
centre). That code is good, but it is coupled to the POS (`company_id`, `store_id`,
POS models). Chumnouy extracts the same capability into an independent service so
the next product does not have to rebuild it.

## What you get

- **REST API** for creating, reading, replying to and resolving tickets.
- **API keys** (test / live, scoped) for server-to-server integrations.
- **Signed webhooks** for ticket lifecycle events.
- **Attachments** with secure staged upload.
- **AI assistant** grounded in your help corpus + your own data (opt-in).
- **Help centre** content API.
- **Agent console** (React) for the humans who operate it — integrators who only
  want the API never need to open it.

## Repository layout

```
chumnouy_api/        FastAPI backend (PostgreSQL, alembic migrations, pytest)
apps/
  web/               Agent console + workspace admin (React + Vite)
packages/
  ui/                @chmaba/ui — shared design tokens + Tailwind preset
  api-client/        TypeScript client generated from the committed OpenAPI spec
docs/                Architecture, ADRs, API contract, reuse notes
deploy/              docker-compose + deployment notes
```

## Stack

Mirrors Chmaba POS exactly so the UX/UI is identical and the team's tooling is
unchanged: **FastAPI + PostgreSQL + Alembic** on the backend, **React + Vite +
Tailwind (react-router, lucide-react)** on the frontend, sharing the
`@chmaba/ui` design tokens and dark mode.

## Documentation

- `docs/architecture.md` — target architecture and decision records (ADRs)
- `docs/api.md` — the v1 API contract (machine + console surfaces)
- `docs/reuse-from-chmaba.md` — exactly what to lift from Chmaba POS and how
- `docs/tenancy.md` — account / workspace / integration isolation model
- `docs/handoff.md` — current state, local run/verify steps, and the task backlog

## Status

In progress. Tenancy, API-key auth, the ticket domain, attachments, webhooks, the
knowledge base, the AI assistant, the public requester surface and the agent
console are implemented and tested. See [`docs/handoff.md`](docs/handoff.md) for
the roadmap.

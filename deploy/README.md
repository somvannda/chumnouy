# Deploy

Deployment topology and configuration for Chumnouy. Planned alongside the first
runnable release (see `../docs/architecture.md` §10).

Target (single host to start):

```
browser
  -> https://chumnouy.chmaba.com        -> apps/web build (console)
  -> https://api.chumnouy.chmaba.com    -> chumnouy_api (uvicorn behind a proxy)
        -> postgres
        -> notifyr API (human-facing notification delivery)
```

Configuration lives in `chumnouy_api/.env` (`chumnouy_api/.env.example`) and
`apps/web/.env` (`apps/web/.env.example`). No secrets are committed.

## Postgres

One server can host every project: give each project its **own database and
role**, not its own server. Locally the native PostgreSQL service on
`127.0.0.1:5432` and the Docker Postgres containers on other ports are all
usable; pick one and create the database once:

```powershell
psql -h 127.0.0.1 -U postgres -c "CREATE DATABASE chumnouy"
```

Point `DATABASE_URL` (asyncpg, the app) and `SYNC_DATABASE_URL` (psycopg, used by
Alembic) at it — see `chumnouy_api/.env.example`. Use a dedicated role with a
strong password in production, not the `postgres` superuser.

## Migrations

Alembic is the only schema authority; the application never creates tables.
Apply before starting the API:

```powershell
cd chumnouy_api
alembic upgrade head      # 0001_tenancy -> 0002_tickets -> 0003_attachments
```

`alembic heads` must show a single head. Each revision rolls back
(`alembic downgrade 0002`).

## Media (attachments)

Ticket attachments are written by the API to `MEDIA_ROOT` (content-addressed
under `workspaces/<workspace_id>/…`) and served from `MEDIA_URL_PREFIX`:

- Mount `MEDIA_ROOT` (`chumnouy_api/media`) on a **persistent volume** — the
  files are the durable record behind each attachment URL.
- Serve the prefix through the API (FastAPI `StaticFiles`) or, preferably, a
  reverse proxy/CDN in front of the media directory; keep `MEDIA_URL_PREFIX` and
  the proxy route identical.
- Back up the media tree together with the database: an attachment row is only
  useful if its file is present.

## Webhook delivery

Outbound webhooks are signed and retried (see `docs/api.md` §7). Either enable
the in-process worker (`WEBHOOK_WORKER_ENABLED=true`) or run a dedicated
worker/cron that drains due deliveries. Run only **one** drainer per database so
deliveries are not sent twice.

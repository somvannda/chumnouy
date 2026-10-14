# chumnouy_api

FastAPI backend for **Chumnouy** — tickets & support as a service.

Source of truth for accounts, workspaces, integrations, API keys, tickets,
requesters, knowledge and the assistant. See `../docs/architecture.md`.

## Requirements

- Python 3.12+
- PostgreSQL 15+

## Setup

```powershell
cd chumnouy_api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
Copy-Item .env.example .env
# create the database, then:
alembic -c alembic.ini upgrade head
```

Run the API (default `http://127.0.0.1:8100`):

```powershell
uvicorn app.main:app --reload --port 8100
```

Docs: `/docs` (Swagger) and `/redoc`. Health: `GET /api/v1/health`.

## Tests

```powershell
pytest
```

## OpenAPI

`openapi.json` is committed; CI fails on drift. Regenerate after changing
endpoints:

```powershell
python scripts/export_openapi.py
```

## Layout

```
app/
  api/          routers (v1 machine+console, admin, public)
  services/     tickets, assistant, webhooks, knowledge
  models.py     SQLAlchemy models
  schemas.py    Pydantic models
  deps.py       auth + workspace resolution
  config.py     settings
  db.py         engine + session
  main.py       app factory / lifespan
alembic/        migrations
scripts/        export_openapi.py
tests/          pytest
```

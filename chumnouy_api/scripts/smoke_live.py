"""Live smoke test: exercise the API against the real database.

Unlike ``pytest`` (which runs on in-memory SQLite), this drives the ASGI app with
its real engine, so it validates the Postgres path — Uuid/JSON columns, unique
constraints, migrations and the error envelope. Requires a migrated database
(``alembic upgrade head``) and ``asyncpg``.

    cd chumnouy_api
    python scripts\\smoke_live.py

It creates a throwaway workspace and ticket each run.
"""
import asyncio
import sys
import uuid
from pathlib import Path

import httpx
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402


async def main() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://smoke") as c:
        email = f"smoke-{uuid.uuid4().hex[:8]}@example.com"
        signup = await c.post(
            "/api/v1/auth/signup",
            json={
                "email": email,
                "password": "supersecret123",
                "name": "Smoke",
                "workspace_name": "Smoke WS",
            },
        )
        assert signup.status_code == 201, signup.text
        token = signup.json()["token"]
        console = {"Authorization": f"Bearer {token}"}
        print("signup            ", signup.status_code, signup.json()["workspace"]["slug"])

        corpus = await c.get("/api/v1/knowledge/articles", headers=console)
        print("knowledge seeded  ", corpus.status_code, len(corpus.json()), "articles")

        integration = await c.post(
            "/api/v1/integrations",
            json={"name": "Smoke", "scopes": ["tickets:read", "tickets:write", "requesters:write"]},
            headers=console,
        )
        assert integration.status_code == 201, integration.text
        key = (
            await c.post(
                f"/api/v1/integrations/{integration.json()['id']}/keys",
                json={"name": "k"},
                headers=console,
            )
        ).json()["key"]
        machine = {"X-Api-Key": key}

        body = {
            "subject": "Smoke ticket",
            "message": "hello",
            "requester": {"external_id": "smoke1", "email": "s@example.com"},
        }
        first = await c.post(
            "/api/v1/tickets", json=body, headers={**machine, "Idempotency-Key": "smoke-1"}
        )
        second = await c.post(
            "/api/v1/tickets", json=body, headers={**machine, "Idempotency-Key": "smoke-1"}
        )
        assert first.status_code == 201, first.text
        assert first.json()["id"] == second.json()["id"], "idempotency not honoured"
        ticket_id = first.json()["id"]
        print("idempotent create ", first.status_code, first.json()["reference"])

        reply = await c.post(
            f"/api/v1/tickets/{ticket_id}/messages",
            json={"body": "on it"},
            headers={**console, "Idempotency-Key": "smoke-2"},
        )
        assert reply.status_code == 201, reply.text
        resolved = await c.post(f"/api/v1/tickets/{ticket_id}/resolve", headers=console)
        print("reply + resolve   ", reply.status_code, resolved.json()["status"])

        hook = await c.post(
            "/api/v1/webhooks",
            json={"url": "https://example.com/hook", "events": ["ticket.created"]},
            headers=console,
        )
        print("webhook register  ", hook.status_code, "secret" in hook.json())

        requester = (await c.get("/api/v1/requesters?q=smoke1", headers=console)).json()[0]
        portal_token = (
            await c.post(f"/api/v1/requesters/{requester['id']}/portal-token", headers=console)
        ).json()["token"]
        portal = await c.get(
            f"/api/v1/public/tickets/{ticket_id}", headers={"X-Requester-Token": portal_token}
        )
        print("requester portal  ", portal.status_code, len(portal.json()["messages"]), "messages")

        missing = await c.get("/api/v1/tickets/11111111-1111-1111-1111-111111111111", headers=console)
        print("error envelope    ", missing.status_code, missing.json()["error"]["code"])

        async with SessionLocal() as session:
            user = (await session.execute(select(User).where(User.email == email))).scalar_one()
            user.platform_role = "admin"
            await session.commit()
        usage = await c.get("/api/admin/usage", headers=console)
        print("admin usage       ", usage.status_code, "tickets=", usage.json()["tickets"])

    print("\nSMOKE OK")


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import errors
from app.api.admin import router as admin_router
from app.api.assistant import router as assistant_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.automations import router as automations_router
from app.api.bulk import router as bulk_router
from app.api.canned_responses import router as canned_responses_router
from app.api.console import router as console_router
from app.api.help_centre import router as help_centre_router
from app.api.inbound import router as inbound_router
from app.api.integrations import router as integrations_router
from app.api.knowledge import router as knowledge_router
from app.api.macros import router as macros_router
from app.api.presence import router as presence_router
from app.api.public import router as public_router
from app.api.reports import router as reports_router
from app.api.requesters import router as requesters_router
from app.api.search import router as search_router
from app.api.sso import router as sso_router
from app.api.teams import router as teams_router
from app.api.tickets import router as tickets_router
from app.api.triggers import router as triggers_router
from app.api.uploads import router as uploads_router
from app.api.v1 import router as v1_router
from app.api.webhooks import router as webhooks_router
from app.config import settings
from app.db import engine
from app.services import ratelimit


@asynccontextmanager
async def lifespan(_: FastAPI):
    # The webhook delivery worker attaches here when enabled; otherwise
    # deliveries are drained by an external runner (e.g. a cron/worker process).
    stop = asyncio.Event()
    worker: asyncio.Task | None = None
    if settings.webhook_worker_enabled:
        from app.services.webhooks import run_worker

        worker = asyncio.create_task(run_worker(stop))
    try:
        yield
    finally:
        stop.set()
        if worker is not None:
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass
        await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Tickets & support as a service.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

errors.install(app)

PUBLIC_PREFIX = "/api/v1/public"


@app.middleware("http")
async def limit_public_requests(request: Request, call_next):
    """Throttle the public surface per client IP (429 with Retry-After)."""
    if request.url.path.startswith(PUBLIC_PREFIX):
        client = request.client.host if request.client else "unknown"
        if not ratelimit.allow(
            f"public:{client}",
            limit=settings.public_rate_limit_per_minute,
            window_seconds=60,
        ):
            return JSONResponse(
                errors.envelope("too_many_requests", "Too many requests; slow down"),
                status_code=429,
                headers={"Retry-After": "60"},
            )
    return await call_next(request)


app.include_router(v1_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(integrations_router, prefix="/api/v1")
app.include_router(tickets_router, prefix="/api/v1")
app.include_router(uploads_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(assistant_router, prefix="/api/v1")
app.include_router(console_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(teams_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(inbound_router, prefix="/api/v1")
app.include_router(canned_responses_router, prefix="/api/v1")
app.include_router(triggers_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(bulk_router, prefix="/api/v1")
app.include_router(help_centre_router, prefix="/api/v1")
app.include_router(automations_router, prefix="/api/v1")
app.include_router(sso_router, prefix="/api/v1")
app.include_router(macros_router, prefix="/api/v1")
app.include_router(presence_router, prefix="/api/v1")
app.include_router(requesters_router, prefix="/api/v1")
app.include_router(public_router, prefix="/api/v1")

# Platform operator surface: separate prefix and credential, never a tenant key.
app.include_router(admin_router, prefix="/api/admin")

# Attachment files are stored content-addressed under the media root and served
# from the public media prefix (see app/media.py).
_media_root = Path(settings.media_root)
_media_root.mkdir(parents=True, exist_ok=True)
app.mount(settings.media_url_prefix, StaticFiles(directory=str(_media_root)), name="media")


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "version": "v1", "docs": "/docs"}

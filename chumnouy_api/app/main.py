import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.integrations import router as integrations_router
from app.api.tickets import router as tickets_router
from app.api.uploads import router as uploads_router
from app.api.v1 import router as v1_router
from app.api.webhooks import router as webhooks_router
from app.config import settings
from app.db import engine


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

app.include_router(v1_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(integrations_router, prefix="/api/v1")
app.include_router(tickets_router, prefix="/api/v1")
app.include_router(uploads_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")

# Attachment files are stored content-addressed under the media root and served
# from the public media prefix (see app/media.py).
_media_root = Path(settings.media_root)
_media_root.mkdir(parents=True, exist_ok=True)
app.mount(settings.media_url_prefix, StaticFiles(directory=str(_media_root)), name="media")


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "version": "v1", "docs": "/docs"}

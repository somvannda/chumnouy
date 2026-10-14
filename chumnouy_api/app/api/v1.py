"""v1 machine + console API.

Health is public; ``whoami`` proves an API key resolves to a workspace and shows
its scopes. Tenancy lives in ``auth.py`` / ``integrations.py``; tickets,
requesters, knowledge, assistant and webhooks follow.
"""
from fastapi import APIRouter, Depends

from app.config import settings
from app.deps import IntegrationContext, get_integration_context
from app.schemas import HealthRead

router = APIRouter()


@router.get("/health", response_model=HealthRead, tags=["system"])
async def health() -> HealthRead:
    return HealthRead(
        status="ok",
        service=settings.app_name,
        version="v1",
        environment=settings.environment,
    )


@router.get("/whoami", tags=["system"])
async def whoami(ctx: IntegrationContext = Depends(get_integration_context)) -> dict:
    """Return the workspace/integration an API key resolves to, and its scopes."""
    return {
        "workspace": ctx.workspace.slug,
        "integration": ctx.integration.slug,
        "environment": ctx.api_key.environment,
        "scopes": sorted(ctx.scopes),
    }

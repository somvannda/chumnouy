"""v1 machine + console API.

Tenancy, tickets, requesters, knowledge, assistant and webhooks are added in
later build steps; the health endpoint proves the app wiring today.
"""
from fastapi import APIRouter

from app.config import settings
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

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Chumnouy API"
    environment: Literal["development", "test", "production"] = "development"

    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/chumnouy"
    sync_database_url: str = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/chumnouy"

    jwt_secret: str = "chumnouy-local-development-secret-change-me"
    jwt_access_ttl_minutes: int = 15
    jwt_remember_ttl_minutes: int = 60 * 24 * 30

    frontend_url: str = "http://localhost:8101"
    cors_origins: str = "http://localhost:8101"
    # Absolute origin the API is reachable at (used to build links in mail the
    # caller sends through Notifyr).
    api_public_url: str = "http://127.0.0.1:8100"

    # Integration API keys look like ``chm_live_<random>`` / ``chm_test_<random>``.
    api_key_prefix: str = "chm"

    # AI assistant. A workspace brings its own key; these are env fallbacks used
    # when no per-workspace setting exists (see docs/architecture.md ADR-008).
    ai_provider: str | None = None
    ai_api_key: str | None = None
    ai_model: str | None = None
    ai_base_url: str | None = None
    assistant_rate_limit_per_hour: int = 60
    assistant_max_question_chars: int = 1000
    assistant_max_history_turns: int = 8
    assistant_max_output_tokens: int = 800

    # Notifyr hand-off. Human-facing delivery lives in Notifyr, not here.
    notifyr_api_url: str | None = None
    notifyr_api_key: str | None = None

    # Outbound webhooks.
    webhook_timeout_seconds: int = 10
    webhook_max_attempts: int = 5
    webhook_worker_enabled: bool = False
    webhook_worker_interval_seconds: int = 15

    # Public-surface protection: in-process sliding window, per client IP.
    public_rate_limit_per_minute: int = 120

    # Ticket attachments. Files are content-addressed under
    # <media_root>/workspaces/<workspace_id>/… and served from <media_url_prefix>.
    media_root: str = "chumnouy_api/media"
    media_url_prefix: str = "/media"
    max_upload_bytes: int = 5_000_000
    max_attachments_per_message: int = 5

    model_config = SettingsConfigDict(
        env_file="chumnouy_api/.env", env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

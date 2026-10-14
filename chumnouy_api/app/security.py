from __future__ import annotations

import hashlib
import re
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import bcrypt
import jwt

from app.config import settings

ALGORITHM = "HS256"
KEY_ENVIRONMENTS = ("test", "live")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: UUID, ttl_minutes: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(
        minutes=ttl_minutes if ttl_minutes is not None else settings.jwt_access_ttl_minutes
    )
    payload: dict[str, Any] = {"sub": str(user_id), "exp": expires, "iat": now, "type": "access"}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])


# --- Integration API keys -----------------------------------------------------
# A key looks like ``chm_live_<random>`` / ``chm_test_<random>``. Only its
# SHA-256 digest is stored; the plaintext is returned exactly once at creation.


def generate_api_key(environment: str = "live") -> str:
    env = environment if environment in KEY_ENVIRONMENTS else "live"
    return f"{settings.api_key_prefix}_{env}_{secrets.token_urlsafe(32)}"


def api_key_prefix(key: str, length: int = 16) -> str:
    """A short, non-secret fragment shown in the console to identify a key."""
    return key[:length]


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def slugify(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return slug or "workspace"

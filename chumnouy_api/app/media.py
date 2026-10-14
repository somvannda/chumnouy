"""Content-addressed media storage, scoped per workspace.

An upload is stored under its SHA-256 digest inside the owning workspace's
directory::

    <media_root>/workspaces/<workspace_id>/<sha[:2]>/<sha><ext>

Two consequences fall out of this shape:

* **Dedup** — identical bytes within one workspace always resolve to the same
  path and URL, so re-uploading the same picture costs nothing extra.
* **Tenant isolation** — a file physically lives under exactly one workspace, so
  one tenant's media can never be read from another tenant's path.

The URL written to the database is derived from the digest, so the same bytes
always map to the same URL. Ported from Chmaba POS `app/media.py` with
``company_id`` renamed to ``workspace_id``.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status

from app.config import settings

# Images are accepted only by suffix and size, shared by every upload surface.
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


async def read_image_upload(file: UploadFile) -> tuple[str, bytes]:
    """Validate an uploaded image and return ``(suffix, content)``.

    Raises ``HTTPException`` 400 for an unsupported type or a size outside the
    1 byte – ``max_upload_bytes`` window, matching the error shape the upload
    endpoints return.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported image type")
    content = await file.read()
    if not content or len(content) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes // 1_000_000
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image must be 1 byte to {limit_mb}MB",
        )
    return suffix, content


def media_root() -> Path:
    return Path(settings.media_root)


def content_digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def store_image(content: bytes, suffix: str, workspace_id: UUID) -> str:
    """Persist ``content`` for ``workspace_id`` and return its public URL.

    Idempotent: if a file with the same digest already exists it is reused, not
    rewritten.
    """
    digest = content_digest(content)
    relative = Path("workspaces") / str(workspace_id) / digest[:2] / f"{digest}{suffix}"
    target = media_root() / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(content)
    return f"{settings.media_url_prefix}/{relative.as_posix()}"


def delete_by_url(url: str) -> None:
    """Best-effort removal of a stored file, refusing to escape the media root."""
    prefix = f"{settings.media_url_prefix}/"
    if not url.startswith(prefix):
        return
    relative = url[len(prefix):]
    root = media_root().resolve()
    target = (root / relative).resolve()
    if target != root and root in target.parents and target.is_file():
        target.unlink()

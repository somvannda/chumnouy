"""Staged attachment uploads (v1).

A client uploads a file before it has a ticket (or while composing a reply); the
row starts unowned and is claimed later by the ticket create/reply payload or
``POST /tickets/{id}/attachments``. Writes require ``tickets:write``.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import TenantContext, require_tenant_scopes
from app.media import content_digest, read_image_upload, store_image
from app.schemas import AttachmentRead
from app.services import attachments as svc

router = APIRouter(prefix="/uploads", tags=["attachments"])

_write = require_tenant_scopes("tickets:write")


@router.post("", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> AttachmentRead:
    """Stage a file while composing a request or reply (images, 5 MB max).

    The row starts unowned and is claimed by ticket creation, a reply, or
    ``POST /tickets/{id}/attachments``, so abandoning a draft leaves nothing
    visible on any ticket. Images only, 5 MB max, at most 5 per message.
    """
    suffix, content = await read_image_upload(file)
    url = store_image(content, suffix, ctx.workspace.id)
    return await svc.stage_attachment(
        db,
        ctx,
        url=url,
        sha256=content_digest(content),
        content_type=file.content_type,
        byte_size=len(content),
        original_filename=file.filename,
    )

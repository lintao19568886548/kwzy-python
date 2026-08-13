"""功能说明：附件 REST。"""

from __future__ import annotations

import base64
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.attachments.application.attachment_service import AttachmentService
from app.shared.deps import get_tenant_context, require_permissions
from app.shared.response import ok
from app.shared.tenant_context import TenantContext

router = APIRouter(tags=["Attachments"])


class AttachmentUpload(BaseModel):
    biz_type: str = Field(min_length=1, max_length=64)
    biz_id: str = Field(min_length=1, max_length=64)
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str
    content_type: str = "application/octet-stream"
    park_id: Optional[int] = None


def _svc(
    db: Session = Depends(get_db), ctx: TenantContext = Depends(get_tenant_context)
) -> AttachmentService:
    return AttachmentService(db, ctx)


@router.post("/attachments")
def upload_attachment(body: AttachmentUpload, svc: AttachmentService = Depends(_svc)) -> dict:
    raw = base64.b64decode(body.content_base64.encode("ascii"))
    return ok(
        svc.upload(
            biz_type=body.biz_type,
            biz_id=body.biz_id,
            filename=body.filename,
            content=raw,
            content_type=body.content_type,
            park_id=body.park_id,
        ),
        message="uploaded",
    )


@router.get(
    "/attachments",
    dependencies=[Depends(require_permissions("attachment:read"))],
)
def list_attachments(
    biz_type: str,
    biz_id: str,
    svc: AttachmentService = Depends(_svc),
) -> dict:
    return ok(svc.list_for_biz(biz_type=biz_type, biz_id=biz_id))


@router.get("/attachments/{attachment_id}/content")
def download_attachment(attachment_id: int, svc: AttachmentService = Depends(_svc)) -> Response:
    data, meta = svc.download(attachment_id)
    return Response(
        content=data,
        media_type=meta["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{meta["filename"]}"'},
    )


@router.delete("/attachments/{attachment_id}")
def delete_attachment(attachment_id: int, svc: AttachmentService = Depends(_svc)) -> dict:
    svc.soft_delete(attachment_id)
    return ok(None, message="deleted")

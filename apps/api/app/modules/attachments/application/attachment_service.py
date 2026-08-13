"""功能说明：附件上传/下载/软删（租户隔离）。"""

from __future__ import annotations

import re
import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.platform.providers import get_file_storage
from app.modules.attachments.infrastructure.attachment_repository import AttachmentRepository
from app.shared.tenant_context import TenantContext

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+")


class AttachmentService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.repo = AttachmentRepository(session, ctx.tenant_id)
        self.audit = AuditRecorder(session, ctx)
        settings = get_settings()
        self.storage = get_file_storage(
            app_env=settings.app_env,
            provider=settings.oss_provider,
            local_root=settings.oss_local_root,
            endpoint=settings.oss_endpoint,
            bucket=settings.oss_bucket,
            access_key=settings.oss_access_key,
            secret_key=settings.oss_secret_key,
        )
        self.max_bytes = int(settings.oss_max_bytes)

    def _safe_filename(self, name: str) -> str:
        base = (name or "file").replace("\\", "/").split("/")[-1]
        base = _SAFE_NAME.sub("_", base).strip("._") or "file"
        return base[:200]

    def upload(
        self,
        *,
        biz_type: str,
        biz_id: str,
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        park_id: Optional[int] = None,
    ) -> dict[str, Any]:
        if not self.ctx.has_permission("attachment:write"):
            raise AppError("无附件上传权限", code="PERMISSION_DENIED", status_code=403)
        if not biz_type or not biz_id:
            raise AppError("biz_type/biz_id 必填", code="VALIDATION_ERROR", status_code=400)
        if len(content) > self.max_bytes:
            raise AppError("文件过大", code="ATTACHMENT_TOO_LARGE", status_code=400)
        if len(content) == 0:
            raise AppError("空文件", code="VALIDATION_ERROR", status_code=400)
        safe = self._safe_filename(filename)
        object_key = f"t{self.ctx.tenant_id}/{biz_type}/{biz_id}/{uuid.uuid4().hex}_{safe}"
        obj = self.storage.put_bytes(
            object_key=object_key,
            data=content,
            content_type=content_type or "application/octet-stream",
        )
        row = self.repo.add(
            park_id=park_id,
            biz_type=biz_type,
            biz_id=str(biz_id),
            filename=safe,
            content_type=content_type or "application/octet-stream",
            size_bytes=obj.size,
            object_key=obj.object_key,
            etag=obj.etag,
            uploaded_by=self.ctx.user_id or None,
        )
        self.audit.record(
            action="upload",
            resource_type="ATTACHMENT",
            resource_id=row.id,
            park_id=park_id,
            detail={"filename": safe, "size": obj.size},
        )
        self.session.commit()
        return self._to_dict(row)

    def list_for_biz(self, *, biz_type: str, biz_id: str) -> list[dict]:
        if not self.ctx.has_permission("attachment:read"):
            raise AppError("无附件查看权限", code="PERMISSION_DENIED", status_code=403)
        return [self._to_dict(r) for r in self.repo.list_active(biz_type=biz_type, biz_id=str(biz_id))]

    def download(self, attachment_id: int) -> tuple[bytes, dict]:
        if not self.ctx.has_permission("attachment:read"):
            raise AppError("无附件下载权限", code="PERMISSION_DENIED", status_code=403)
        row = self.repo.get(attachment_id)
        if row is None or row.status != "ACTIVE":
            raise AppError("附件不存在", code="ATTACHMENT_NOT_FOUND", status_code=404)
        data = self.storage.get_bytes(row.object_key)
        return data, self._to_dict(row)

    def soft_delete(self, attachment_id: int) -> None:
        if not self.ctx.has_permission("attachment:write"):
            raise AppError("无附件删除权限", code="PERMISSION_DENIED", status_code=403)
        row = self.repo.get(attachment_id)
        if row is None:
            raise AppError("附件不存在", code="ATTACHMENT_NOT_FOUND", status_code=404)
        row.status = "DELETED"
        self.session.add(row)
        self.audit.record(
            action="delete",
            resource_type="ATTACHMENT",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"filename": row.filename},
        )
        self.session.commit()

    def _to_dict(self, row) -> dict[str, Any]:
        return {
            "id": row.id,
            "biz_type": row.biz_type,
            "biz_id": row.biz_id,
            "filename": row.filename,
            "content_type": row.content_type,
            "size_bytes": row.size_bytes,
            "status": row.status,
            "etag": row.etag,
        }

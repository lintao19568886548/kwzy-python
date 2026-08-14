"""功能说明：附件上传/下载/软删（租户隔离）。"""

from __future__ import annotations

import io
import re
import uuid
import zipfile
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.platform.providers import get_file_storage
from app.modules.attachments.infrastructure.attachment_repository import AttachmentRepository
from app.shared.tenant_context import TenantContext

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+")
_ALLOWED_CONTENT_TYPES: dict[str, set[str]] = {
    ".txt": {"text/plain"},
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".webp": {"image/webp"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
}


class AttachmentService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.repo = AttachmentRepository(session, ctx)
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
        if park_id is None:
            if not self.ctx.has_all_park_access:
                raise AppError("无租户级附件访问范围", code="PARK_SCOPE_DENIED", status_code=403)
        else:
            if not self.ctx.allows_park(park_id):
                raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
            if not self.repo.park_exists(park_id):
                raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        safe = self._safe_filename(filename)
        normalized_content_type = self._validate_content(
            filename=safe,
            content=content,
            content_type=content_type,
        )
        object_key = f"t{self.ctx.tenant_id}/{biz_type}/{biz_id}/{uuid.uuid4().hex}_{safe}"
        obj = self.storage.put_bytes(
            object_key=object_key,
            data=content,
            content_type=normalized_content_type,
        )
        row = self.repo.add(
            park_id=park_id,
            biz_type=biz_type,
            biz_id=str(biz_id),
            filename=safe,
            content_type=normalized_content_type,
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

    def _validate_content(self, *, filename: str, content: bytes, content_type: str) -> str:
        extension = Path(filename).suffix.lower()
        allowed = _ALLOWED_CONTENT_TYPES.get(extension)
        if not allowed:
            raise AppError(
                "不支持的附件类型",
                code="ATTACHMENT_TYPE_NOT_ALLOWED",
                status_code=400,
            )
        declared = (content_type or "application/octet-stream").split(";", 1)[0].strip().lower()
        normalized = next(iter(allowed)) if declared == "application/octet-stream" else declared
        if normalized not in allowed:
            raise AppError(
                "附件扩展名与内容类型不匹配",
                code="ATTACHMENT_CONTENT_TYPE_MISMATCH",
                status_code=400,
            )
        valid_magic = True
        if extension == ".pdf":
            valid_magic = content.startswith(b"%PDF-")
        elif extension == ".png":
            valid_magic = content.startswith(b"\x89PNG\r\n\x1a\n")
        elif extension in {".jpg", ".jpeg"}:
            valid_magic = content.startswith(b"\xff\xd8\xff")
        elif extension == ".webp":
            valid_magic = len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
        elif extension == ".txt":
            valid_magic = b"\x00" not in content
            if valid_magic:
                try:
                    content.decode("utf-8")
                except UnicodeDecodeError:
                    valid_magic = False
        elif extension in {".docx", ".xlsx"}:
            required = "word/document.xml" if extension == ".docx" else "xl/workbook.xml"
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as archive:
                    names = archive.namelist()
                    valid_magic = (
                        required in names
                        and len(names) <= 10_000
                        and all(".." not in name.replace("\\", "/").split("/") for name in names)
                    )
            except (zipfile.BadZipFile, OSError):
                valid_magic = False
        if not valid_magic:
            raise AppError(
                "附件内容与声明类型不匹配",
                code="ATTACHMENT_MAGIC_MISMATCH",
                status_code=400,
            )
        return normalized

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
            "park_id": row.park_id,
            "filename": row.filename,
            "content_type": row.content_type,
            "size_bytes": row.size_bytes,
            "status": row.status,
            "etag": row.etag,
        }

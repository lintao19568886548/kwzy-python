"""附件 ORM 访问。"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.attachment import Attachment


class AttachmentRepository:
    def __init__(self, session: Session, tenant_id: int) -> None:
        self.session = session
        self.tenant_id = tenant_id

    def add(
        self,
        *,
        park_id: Optional[int],
        biz_type: str,
        biz_id: str,
        filename: str,
        content_type: str,
        size_bytes: int,
        object_key: str,
        etag: str,
        uploaded_by: Optional[int],
    ) -> Attachment:
        row = Attachment(
            tenant_id=self.tenant_id,
            park_id=park_id,
            biz_type=biz_type,
            biz_id=biz_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            object_key=object_key,
            etag=etag,
            uploaded_by=uploaded_by,
            status="ACTIVE",
        )
        self.session.add(row)
        self.session.flush()
        return row

    def list_active(self, *, biz_type: str, biz_id: str) -> Sequence[Attachment]:
        return list(
            self.session.scalars(
                select(Attachment).where(
                    Attachment.tenant_id == self.tenant_id,
                    Attachment.biz_type == biz_type,
                    Attachment.biz_id == biz_id,
                    Attachment.status == "ACTIVE",
                )
            ).all()
        )

    def get(self, attachment_id: int) -> Optional[Attachment]:
        row = self.session.get(Attachment, attachment_id)
        if row is None or int(row.tenant_id) != self.tenant_id:
            return None
        return row

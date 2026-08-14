"""附件 ORM 访问。"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import false, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.attachment import Attachment
from app.infrastructure.database.models.park_property import Park
from app.infrastructure.database.models.records_seal import RecordRevision
from app.shared.tenant_context import ParkScopeMode, TenantContext


class AttachmentRepository:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.tenant_id = ctx.tenant_id

    def _scope_condition(self):
        """Return a fail-closed attachment park-scope predicate."""

        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return None
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return Attachment.park_id.in_(self.ctx.park_ids)
        return false()

    def park_exists(self, park_id: int) -> bool:
        return (
            self.session.scalar(
                select(Park.id).where(
                    Park.id == park_id,
                    Park.tenant_id == self.tenant_id,
                    Park.is_deleted.is_(False),
                )
            )
            is not None
        )

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
        conditions = [
            Attachment.tenant_id == self.tenant_id,
            Attachment.biz_type == biz_type,
            Attachment.biz_id == biz_id,
            Attachment.status == "ACTIVE",
        ]
        scope_condition = self._scope_condition()
        if scope_condition is not None:
            conditions.append(scope_condition)
        return list(
            self.session.scalars(
                select(Attachment).where(*conditions)
            ).all()
        )

    def get(self, attachment_id: int) -> Optional[Attachment]:
        conditions = [
            Attachment.id == attachment_id,
            Attachment.tenant_id == self.tenant_id,
        ]
        scope_condition = self._scope_condition()
        if scope_condition is not None:
            conditions.append(scope_condition)
        return self.session.scalar(select(Attachment).where(*conditions))

    def is_governed_record_evidence(self, attachment_id: int) -> bool:
        """Return true when an active governed record revision pins this object."""

        return bool(
            self.session.scalar(
                select(RecordRevision.id).where(
                    RecordRevision.tenant_id == self.tenant_id,
                    RecordRevision.attachment_id == int(attachment_id),
                    RecordRevision.status == "ACTIVE",
                )
            )
        )

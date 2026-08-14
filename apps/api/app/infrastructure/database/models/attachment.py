"""功能说明：附件元数据 ORM。"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, TimestampMixin


class Attachment(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "attachments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uk_attachments_tenant_id_id"),
        UniqueConstraint("tenant_id", "object_key", name="uk_attachment_object_key"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=True)
    biz_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    biz_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False, default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    etag: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    uploaded_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")

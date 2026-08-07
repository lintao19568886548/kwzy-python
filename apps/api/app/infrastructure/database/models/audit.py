"""关键业务写操作审计模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, utc_now


class AuditLog(Base, PrimaryKeyMixin):
    """记录关键资源的写操作，不保存密码、Token 等敏感数据。"""

    __tablename__ = "audit_logs"

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True
    )
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    park_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("parks.id"), nullable=True
    )
    detail_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    client_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

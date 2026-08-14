"""关键业务写操作审计模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, utc_now


class AuditLog(Base, PrimaryKeyMixin):
    """记录关键资源的写操作，不保存密码、Token 等敏感数据。"""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_tenant_created_at", "tenant_id", "created_at"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index(
            "uk_audit_logs_tenant_sequence",
            "tenant_id",
            "sequence_no",
            unique=True,
            postgresql_where=text("sequence_no IS NOT NULL"),
            sqlite_where=text("sequence_no IS NOT NULL"),
        ),
        Index("ix_audit_logs_tenant_action", "tenant_id", "action", "created_at"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    park_id: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=True)
    detail_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    sequence_no: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    record_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    integrity_version: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AuditChainHead(Base):
    """每租户单行链头；追加审计时行锁保证确定性顺序。"""

    __tablename__ = "audit_chain_heads"

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), primary_key=True, autoincrement=False
    )
    sequence_no: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="GENESIS")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

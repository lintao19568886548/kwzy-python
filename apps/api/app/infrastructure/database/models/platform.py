"""功能说明：平台幂等键与编号序列表。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin


class NumberSequence(Base, PrimaryKeyMixin):
    __tablename__ = "number_sequences"
    __table_args__ = (
        UniqueConstraint("tenant_id", "biz_type", "period_key", name="uk_number_seq"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True)
    biz_type: Mapped[str] = mapped_column(String(32), nullable=False)
    period_key: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    next_val: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)


class IdempotencyKey(Base, PrimaryKeyMixin):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("tenant_id", "operation", "idem_key", name="uk_idem_tenant_op_key"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(FK_TYPE, nullable=True)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    idem_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="COMPLETED")
    resource_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    response_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)

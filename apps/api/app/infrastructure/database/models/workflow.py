"""功能说明：最小审批单 ORM（可运行适配，非完整 BPM）。"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, TimestampMixin


class ApprovalRequest(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "approval_requests"
    __table_args__ = (
        UniqueConstraint("tenant_id", "biz_type", "biz_id", name="uk_approval_biz"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("parks.id"), nullable=True, index=True
    )
    biz_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    biz_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    applicant_user_id: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    approver_user_id: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decision_remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ApprovalEvent(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "approval_events"

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    approval_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("approval_requests.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

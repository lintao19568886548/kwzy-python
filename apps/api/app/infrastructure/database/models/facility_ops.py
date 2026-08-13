"""功能说明：运维工单 ORM。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, TimestampMixin


class WorkOrder(Base, PrimaryKeyMixin, TimestampMixin):
    """园区运维工单。"""

    __tablename__ = "work_orders"

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("parks.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="GENERAL")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="MEDIUM")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN", index=True)
    reporter_user_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True
    )
    assignee_user_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True, index=True
    )
    unit_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("units.id"), nullable=True
    )
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="MANUAL")
    source_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")

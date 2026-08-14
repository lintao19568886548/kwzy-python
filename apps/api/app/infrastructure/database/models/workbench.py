"""Workbench work items (auto todos)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, TimestampMixin


class WorkItem(Base, PrimaryKeyMixin, TimestampMixin):
    """租户内待办/工作项。"""

    __tablename__ = "work_items"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "source_type",
            "source_id",
            "item_type",
            name="uk_work_item_source",
        ),
        CheckConstraint(
            "escalation_level >= 0 AND lock_version >= 1",
            name="ck_work_item_escalation_version",
        ),
        Index("ix_work_items_last_event_id", "last_event_id"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("parks.id"), nullable=True, index=True
    )
    item_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="MEDIUM")
    assignee_user_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True, index=True
    )
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="MANUAL")
    source_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deep_link: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    escalation_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reassigned_from_user_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True
    )
    last_event_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("business_events.id"), nullable=True
    )
    source_owned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

"""功能说明：招商线索 ORM。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, TimestampMixin


class Lead(Base, PrimaryKeyMixin, TimestampMixin):
    """功能说明：招商线索 leads。"""

    __tablename__ = "leads"

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("parks.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    contact_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    agent_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    intent_level: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    intent_area: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    desired_usage: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    budget_unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW", index=True)
    normalized_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    normalized_phone: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="MANUAL")
    source_ref: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    duplicate_override_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pool_status: Mapped[str] = mapped_column(String(16), nullable=False, default="PRIVATE", index=True)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_user_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True, index=True
    )
    party_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("parties.id"), nullable=True, index=True
    )
    lease_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("lease_contracts.id"), nullable=True, index=True
    )
    converted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    lost_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    first_contact_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_follow_up_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    recycle_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    merged_into_lead_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("leads.id"), nullable=True, index=True
    )
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index(
            "uk_leads_source_ref",
            "tenant_id",
            "source_type",
            "source_ref",
            unique=True,
            postgresql_where=text("source_ref IS NOT NULL"),
            sqlite_where=text("source_ref IS NOT NULL"),
        ),
        Index("ix_leads_scope_owner_stage", "tenant_id", "park_id", "owner_user_id", "status"),
        Index("ix_leads_scope_pool_stage", "tenant_id", "park_id", "pool_status", "status"),
        Index("ix_leads_scope_source_created", "tenant_id", "park_id", "source_type", "created_at"),
    )


class LeadActivity(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lead_activities"

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False, index=True)
    lead_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("leads.id"), nullable=False, index=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    activity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    next_follow_up_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    stage_from: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    stage_to: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    attributes_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_lead_activities_timeline", "tenant_id", "lead_id", "occurred_at", "id"),
    )


class LeadAssignmentEvent(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lead_assignment_events"

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False, index=True)
    lead_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("leads.id"), nullable=False, index=True)
    from_owner_user_id: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    to_owner_user_id: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        Index("ix_lead_assignment_timeline", "tenant_id", "lead_id", "occurred_at", "id"),
    )


class LeadMergeLink(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lead_merge_links"

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False, index=True)
    source_lead_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("leads.id"), nullable=False, unique=True)
    target_lead_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("leads.id"), nullable=False, index=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    merged_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class LeadUnitLock(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lead_unit_locks"

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False, index=True)
    lead_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("leads.id"), nullable=False, index=True)
    unit_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("units.id"), nullable=False, index=True)
    lease_id: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("lease_contracts.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index(
            "uk_lead_unit_locks_active_unit",
            "tenant_id",
            "unit_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
        Index("ix_lead_unit_locks_expiry", "tenant_id", "status", "expires_at"),
    )

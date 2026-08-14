"""功能说明：招商线索 ORM。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
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
        UniqueConstraint("tenant_id", "id", name="uk_leads_tenant_id_id"),
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
    rule_version_id: Mapped[Optional[int]] = mapped_column(FK_TYPE, nullable=True, index=True)
    trigger: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    decision_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_lead_assignment_timeline", "tenant_id", "lead_id", "occurred_at", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "rule_version_id"],
            ["lead_assignment_rule_versions.tenant_id", "lead_assignment_rule_versions.id"],
            name="fk_lead_assignment_event_tenant_rule_version",
        ),
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
    intent_application_id: Mapped[Optional[int]] = mapped_column(FK_TYPE, nullable=True, index=True)
    intent_version_id: Mapped[Optional[int]] = mapped_column(FK_TYPE, nullable=True, index=True)

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
        ForeignKeyConstraint(
            ["tenant_id", "intent_application_id"],
            ["lead_intent_applications.tenant_id", "lead_intent_applications.id"],
            name="fk_lead_locks_tenant_intent_application",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "intent_version_id"],
            ["lead_intent_versions.tenant_id", "lead_intent_versions.id"],
            name="fk_lead_locks_tenant_intent_version",
        ),
    )


class LeadAssignmentRule(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lead_assignment_rules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uk_lead_assignment_rules_tenant_id_id"),
        UniqueConstraint(
            "tenant_id", "park_id", "trigger", name="uk_lead_assignment_rule_park_trigger"
        ),
        CheckConstraint(
            "trigger IN ('MANUAL_CREATE', 'CHANNEL_INTAKE', 'RECYCLE')",
            name="ck_lead_assignment_rule_trigger",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'RETIRED')", name="ck_lead_assignment_rule_status"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_lead_assignment_rule_tenant_park",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    updated_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))


class LeadAssignmentRuleVersion(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lead_assignment_rule_versions"
    __table_args__ = (
        UniqueConstraint(
            "rule_id", "version", name="uk_lead_assignment_rule_version"
        ),
        UniqueConstraint(
            "tenant_id", "id", name="uk_lead_assignment_rule_versions_tenant_id_id"
        ),
        Index(
            "uk_lead_assignment_rule_one_draft",
            "rule_id",
            unique=True,
            postgresql_where=text("status = 'DRAFT'"),
            sqlite_where=text("status = 'DRAFT'"),
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'PUBLISHED', 'RETIRED')",
            name="ck_lead_assignment_rule_version_status",
        ),
        CheckConstraint(
            "strategy = 'LEAST_LOAD'", name="ck_lead_assignment_rule_strategy"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "rule_id"],
            ["lead_assignment_rules.tenant_id", "lead_assignment_rules.id"],
            name="fk_lead_assignment_rule_version_tenant_rule",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    rule_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    strategy: Mapped[str] = mapped_column(String(32), nullable=False, default="LEAST_LOAD")
    recycle_after_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=72)
    created_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    published_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class LeadAssignmentMember(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lead_assignment_members"
    __table_args__ = (
        UniqueConstraint("version_id", "user_id", name="uk_lead_assignment_member_user"),
        UniqueConstraint(
            "version_id", "member_order", name="uk_lead_assignment_member_order"
        ),
        CheckConstraint("capacity > 0 AND capacity <= 10000", name="ck_lead_assignment_capacity"),
        CheckConstraint("weight > 0 AND weight <= 100", name="ck_lead_assignment_weight"),
        CheckConstraint("member_order > 0", name="ck_lead_assignment_member_order_positive"),
        ForeignKeyConstraint(
            ["tenant_id", "version_id"],
            ["lead_assignment_rule_versions.tenant_id", "lead_assignment_rule_versions.id"],
            name="fk_lead_assignment_member_tenant_version",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_lead_assignment_member_tenant_user",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    version_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False, index=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    member_order: Mapped[int] = mapped_column(Integer, nullable=False)
    last_assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class LeadViewing(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lead_viewings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uk_lead_viewings_tenant_id_id"),
        Index(
            "ix_lead_viewings_owner_window",
            "tenant_id",
            "owner_user_id",
            "status",
            "starts_at",
            "ends_at",
        ),
        Index(
            "uk_lead_viewing_completion_key",
            "tenant_id",
            "completion_idempotency_key",
            unique=True,
            postgresql_where=text("completion_idempotency_key IS NOT NULL"),
            sqlite_where=text("completion_idempotency_key IS NOT NULL"),
        ),
        CheckConstraint(
            "status IN ('SCHEDULED', 'CONFIRMED', 'COMPLETED', 'CANCELLED', 'NO_SHOW')",
            name="ck_lead_viewing_status",
        ),
        CheckConstraint("ends_at > starts_at", name="ck_lead_viewing_time_order"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_lead_viewing_tenant_park",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "lead_id"],
            ["leads.tenant_id", "leads.id"],
            name="fk_lead_viewing_tenant_lead",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "owner_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_lead_viewing_tenant_owner",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False, index=True)
    lead_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False, index=True)
    owner_user_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="SCHEDULED")
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    visitor_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    visitor_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    next_follow_up_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    completion_idempotency_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    updated_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))


class LeadViewingUnit(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lead_viewing_units"
    __table_args__ = (
        UniqueConstraint("viewing_id", "unit_id", name="uk_lead_viewing_unit"),
        ForeignKeyConstraint(
            ["tenant_id", "viewing_id"],
            ["lead_viewings.tenant_id", "lead_viewings.id"],
            name="fk_lead_viewing_unit_tenant_viewing",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["units.tenant_id", "units.id"],
            name="fk_lead_viewing_unit_tenant_unit",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    viewing_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False, index=True)
    unit_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False, index=True)
    unit_version: Mapped[int] = mapped_column(Integer, nullable=False)


class LeadIntentApplication(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lead_intent_applications"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uk_lead_intent_applications_tenant_id_id"),
        UniqueConstraint("tenant_id", "lead_id", name="uk_lead_intent_application_lead"),
        CheckConstraint(
            "status IN ('DRAFT', 'PENDING', 'APPROVED', 'REJECTED', 'RETURNED', 'WITHDRAWN')",
            name="ck_lead_intent_application_status",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_lead_intent_application_tenant_park",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "lead_id"],
            ["leads.tenant_id", "leads.id"],
            name="fk_lead_intent_application_tenant_lead",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "approval_request_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_lead_intent_application_tenant_approval",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False, index=True)
    lead_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    approval_request_id: Mapped[Optional[int]] = mapped_column(FK_TYPE, nullable=True, index=True)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    updated_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))


class LeadIntentVersion(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lead_intent_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uk_lead_intent_versions_tenant_id_id"),
        UniqueConstraint("application_id", "version", name="uk_lead_intent_version"),
        CheckConstraint("ends_on > starts_on", name="ck_lead_intent_date_order"),
        CheckConstraint("proposed_unit_price >= 0", name="ck_lead_intent_price_nonnegative"),
        ForeignKeyConstraint(
            ["tenant_id", "application_id"],
            ["lead_intent_applications.tenant_id", "lead_intent_applications.id"],
            name="fk_lead_intent_version_tenant_application",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    application_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    proposed_unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))


class LeadIntentUnit(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lead_intent_units"
    __table_args__ = (
        UniqueConstraint("intent_version_id", "unit_id", name="uk_lead_intent_unit"),
        CheckConstraint("requested_area > 0", name="ck_lead_intent_unit_area_positive"),
        ForeignKeyConstraint(
            ["tenant_id", "intent_version_id"],
            ["lead_intent_versions.tenant_id", "lead_intent_versions.id"],
            name="fk_lead_intent_unit_tenant_version",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["units.tenant_id", "units.id"],
            name="fk_lead_intent_unit_tenant_unit",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    intent_version_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False, index=True)
    unit_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False, index=True)
    unit_version: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_area: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class LeadChannel(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lead_channels"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uk_lead_channels_tenant_id_id"),
        UniqueConstraint("tenant_id", "code", name="uk_lead_channel_code"),
        UniqueConstraint("public_id", name="uk_lead_channel_public_id"),
        CheckConstraint(
            "verification_status IN ('NOT_CONNECTED', 'LOCAL_CONTRACT_VERIFIED', 'SANDBOX_VERIFIED', 'LIVE_CONNECTED')",
            name="ck_lead_channel_verification_status",
        ),
        CheckConstraint(
            "max_clock_skew_seconds >= 30 AND max_clock_skew_seconds <= 900",
            name="ck_lead_channel_clock_skew",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_lead_channel_tenant_park",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    public_id: Mapped[str] = mapped_column(String(36), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    secret_env_key: Mapped[str] = mapped_column(String(128), nullable=False)
    previous_secret_env_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    max_clock_skew_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    allow_auto_assign: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    mapping_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    verification_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="NOT_CONNECTED"
    )
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    updated_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))


class LeadChannelInboxEvent(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lead_channel_inbox_events"
    __table_args__ = (
        UniqueConstraint("channel_id", "external_event_id", name="uk_lead_channel_event"),
        CheckConstraint(
            "status IN ('RECEIVED', 'ACCEPTED', 'QUARANTINED')",
            name="ck_lead_channel_event_status",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "channel_id"],
            ["lead_channels.tenant_id", "lead_channels.id"],
            name="fk_lead_channel_event_tenant_channel",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_lead_channel_event_tenant_park",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "lead_id"],
            ["leads.tenant_id", "leads.id"],
            name="fk_lead_channel_event_tenant_lead",
        ),
        Index("ix_lead_channel_events_status", "tenant_id", "channel_id", "status", "received_at"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    channel_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False, index=True)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False, index=True)
    external_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_ciphertext: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_key_ref: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="RECEIVED")
    safe_preview_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    failure_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    lead_id: Mapped[Optional[int]] = mapped_column(FK_TYPE, nullable=True, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    replay_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_replayed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

"""Policy, enterprise-service, park-activity, and announcement persistence."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, TimestampMixin


class EngagementPolicy(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "engagement_policies"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','PENDING_APPROVAL','APPROVED','PUBLISHED','REJECTED','EXPIRED','WITHDRAWN')",
            name="ck_eng_policy_status",
        ),
        CheckConstraint("current_version >= 1", name="ck_eng_policy_current_version"),
        CheckConstraint("lock_version > 0", name="ck_eng_policy_lock"),
        UniqueConstraint("tenant_id", "code", name="uk_eng_policy_code"),
        UniqueConstraint("tenant_id", "id", name="uk_eng_policy_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_eng_policy_park",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "approval_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_eng_policy_approval",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_policy_creator",
        ),
        Index("ix_eng_policy_scope", "tenant_id", "park_id", "status"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    code: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT")
    current_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    published_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approval_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)


class EngagementPolicyVersion(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "engagement_policy_versions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','APPROVED','PUBLISHED','REJECTED','RETIRED')",
            name="ck_eng_policy_version_status",
        ),
        CheckConstraint("version >= 1", name="ck_eng_policy_version_no"),
        CheckConstraint(
            "expires_on IS NULL OR effective_on IS NULL OR expires_on >= effective_on",
            name="ck_eng_policy_version_dates",
        ),
        UniqueConstraint("tenant_id", "policy_id", "version", name="uk_eng_policy_version"),
        UniqueConstraint("tenant_id", "id", name="uk_eng_policy_version_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "policy_id"],
            ["engagement_policies.tenant_id", "engagement_policies.id"],
            name="fk_eng_policy_version_policy",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "approval_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_eng_policy_version_approval",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_policy_version_creator",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "published_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_policy_version_publisher",
        ),
        Index("ix_eng_policy_version_window", "tenant_id", "status", "effective_on", "expires_on"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    policy_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    region_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_system: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_identifier: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_publisher: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    effective_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    attachments_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    applicability_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    published_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EngagementPolicyEvent(Base, PrimaryKeyMixin):
    __tablename__ = "engagement_policy_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('CREATED','UPDATED','SUBMITTED','APPROVED','REJECTED','PUBLISHED','EXPIRED','WITHDRAWN','MATCH_EVALUATED')",
            name="ck_eng_policy_event_type",
        ),
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_eng_policy_event_key"),
        ForeignKeyConstraint(
            ["tenant_id", "policy_id"],
            ["engagement_policies.tenant_id", "engagement_policies.id"],
            name="fk_eng_policy_event_policy",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "actor_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_policy_event_actor",
        ),
        Index("ix_eng_policy_event_timeline", "tenant_id", "policy_id", "occurred_at"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    policy_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    detail_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class EngagementPolicyFollow(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "engagement_policy_follows"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','UNFOLLOWED')", name="ck_eng_policy_follow_status"),
        UniqueConstraint("tenant_id", "policy_id", "party_id", name="uk_eng_policy_follow"),
        ForeignKeyConstraint(
            ["tenant_id", "policy_id"],
            ["engagement_policies.tenant_id", "engagement_policies.id"],
            name="fk_eng_policy_follow_policy",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_eng_policy_follow_party",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_eng_policy_follow_park",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_policy_follow_user",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    policy_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    party_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    user_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")


class EngagementPolicyConsultation(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "engagement_policy_consultations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN','IN_PROGRESS','CLOSED','CANCELLED')",
            name="ck_eng_policy_consult_status",
        ),
        CheckConstraint("lock_version > 0", name="ck_eng_policy_consult_lock"),
        UniqueConstraint("tenant_id", "case_no", name="uk_eng_policy_consult_no"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_eng_policy_consult_key"),
        ForeignKeyConstraint(
            ["tenant_id", "policy_id"],
            ["engagement_policies.tenant_id", "engagement_policies.id"],
            name="fk_eng_policy_consult_policy",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_eng_policy_consult_party",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_eng_policy_consult_park",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_policy_consult_creator",
        ),
        Index("ix_eng_policy_consult_scope", "tenant_id", "park_id", "status"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    policy_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    party_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    case_no: Mapped[str] = mapped_column(String(48), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="OPEN")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)


class EngagementServiceCatalog(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "engagement_service_catalogs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','PENDING_APPROVAL','APPROVED','PUBLISHED','REJECTED','RETIRED')",
            name="ck_eng_service_catalog_status",
        ),
        CheckConstraint("current_version >= 1", name="ck_eng_service_catalog_version"),
        CheckConstraint("lock_version > 0", name="ck_eng_service_catalog_lock"),
        UniqueConstraint("tenant_id", "park_id", "code", name="uk_eng_service_catalog_code"),
        UniqueConstraint("tenant_id", "id", name="uk_eng_service_catalog_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_eng_service_catalog_park",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "approval_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_eng_service_catalog_approval",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_service_catalog_creator",
        ),
        Index("ix_eng_service_catalog_scope", "tenant_id", "park_id", "status"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    code: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT")
    current_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    published_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approval_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)


class EngagementServiceVersion(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "engagement_service_versions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','APPROVED','PUBLISHED','REJECTED','RETIRED')",
            name="ck_eng_service_version_status",
        ),
        CheckConstraint("version >= 1", name="ck_eng_service_version_no"),
        CheckConstraint(
            "provider_type IN ('INTERNAL','EXTERNAL')", name="ck_eng_service_provider_type"
        ),
        CheckConstraint(
            "provider_state IN ('LOCAL','NOT_CONNECTED')", name="ck_eng_service_provider_state"
        ),
        CheckConstraint("sla_hours BETWEEN 1 AND 8760", name="ck_eng_service_sla"),
        CheckConstraint("price_amount IS NULL OR price_amount >= 0", name="ck_eng_service_price"),
        UniqueConstraint("tenant_id", "catalog_id", "version", name="uk_eng_service_version"),
        UniqueConstraint("tenant_id", "id", name="uk_eng_service_version_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "catalog_id"],
            ["engagement_service_catalogs.tenant_id", "engagement_service_catalogs.id"],
            name="fk_eng_service_version_catalog",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "approval_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_eng_service_version_approval",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_service_version_creator",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    catalog_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(16), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_state: Mapped[str] = mapped_column(String(24), nullable=False)
    sla_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    appointment_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    eligibility_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    evidence_rules_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    price_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="CNY", server_default="CNY"
    )
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EngagementServiceCase(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "engagement_service_cases"
    __table_args__ = (
        CheckConstraint(
            "status IN ('SUBMITTED','ACCEPTED','ASSIGNED','APPOINTED','IN_PROGRESS','RESULT_READY','DISPUTED','CONFIRMED','CANCELLED')",
            name="ck_eng_service_case_status",
        ),
        CheckConstraint(
            "priority IN ('LOW','MEDIUM','HIGH','URGENT')", name="ck_eng_service_case_priority"
        ),
        CheckConstraint("lock_version > 0", name="ck_eng_service_case_lock"),
        UniqueConstraint("tenant_id", "case_no", name="uk_eng_service_case_no"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_eng_service_case_key"),
        UniqueConstraint("tenant_id", "id", name="uk_eng_service_case_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_eng_service_case_park",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "catalog_id"],
            ["engagement_service_catalogs.tenant_id", "engagement_service_catalogs.id"],
            name="fk_eng_service_case_catalog",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "service_version_id"],
            ["engagement_service_versions.tenant_id", "engagement_service_versions.id"],
            name="fk_eng_service_case_version",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_eng_service_case_party",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["tenant_service_principals.tenant_id", "tenant_service_principals.id"],
            name="fk_eng_service_case_principal",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "assigned_to"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_service_case_assignee",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "work_order_id"],
            ["work_orders.tenant_id", "work_orders.park_id", "work_orders.id"],
            name="fk_eng_service_case_work_order",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_service_case_creator",
        ),
        Index("ix_eng_service_case_scope", "tenant_id", "park_id", "status", "sla_due_at"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    catalog_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    service_version_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    party_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    principal_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    case_no: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="SUBMITTED")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="MEDIUM")
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    contact_masked: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assigned_to: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    work_order_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    sla_due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    appointment_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)


class EngagementServiceCaseEvent(Base, PrimaryKeyMixin):
    __tablename__ = "engagement_service_case_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('SUBMITTED','ACCEPTED','ASSIGNED','APPOINTED','EVIDENCE','PROGRESS','RESULT_READY','DISPUTED','CONFIRMED','CANCELLED','SLA_ESCALATED','WORK_ORDER_LINKED')",
            name="ck_eng_service_case_event_type",
        ),
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_eng_service_case_event_key"),
        ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["engagement_service_cases.tenant_id", "engagement_service_cases.id"],
            name="fk_eng_service_case_event_case",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "actor_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_service_case_event_actor",
        ),
        Index("ix_eng_service_case_event_time", "tenant_id", "case_id", "occurred_at"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    case_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class EngagementServiceFeedback(Base, PrimaryKeyMixin):
    __tablename__ = "engagement_service_feedback"
    __table_args__ = (
        CheckConstraint("score BETWEEN 1 AND 5", name="ck_eng_service_feedback_score"),
        UniqueConstraint("tenant_id", "case_id", name="uk_eng_service_feedback_case"),
        ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["engagement_service_cases.tenant_id", "engagement_service_cases.id"],
            name="fk_eng_service_feedback_case",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_eng_service_feedback_party",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    case_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    party_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class EngagementActivity(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "engagement_activities"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','PENDING_APPROVAL','APPROVED','PUBLISHED','REGISTRATION_CLOSED','IN_PROGRESS','REJECTED','COMPLETED','CANCELLED')",
            name="ck_eng_activity_status",
        ),
        CheckConstraint("current_version >= 1", name="ck_eng_activity_version"),
        CheckConstraint("lock_version > 0", name="ck_eng_activity_lock"),
        UniqueConstraint("tenant_id", "park_id", "code", name="uk_eng_activity_code"),
        UniqueConstraint("tenant_id", "id", name="uk_eng_activity_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_eng_activity_park",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "approval_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_eng_activity_approval",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_activity_creator",
        ),
        Index("ix_eng_activity_scope", "tenant_id", "park_id", "status"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    code: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT")
    current_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    published_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approval_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)


class EngagementActivityVersion(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "engagement_activity_versions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','APPROVED','PUBLISHED','REJECTED','RETIRED')",
            name="ck_eng_activity_version_status",
        ),
        CheckConstraint("version >= 1", name="ck_eng_activity_version_no"),
        CheckConstraint("ends_at > starts_at", name="ck_eng_activity_schedule"),
        CheckConstraint(
            "registration_closes_at >= registration_opens_at",
            name="ck_eng_activity_registration_window",
        ),
        CheckConstraint(
            "registration_closes_at <= starts_at", name="ck_eng_activity_registration_close"
        ),
        CheckConstraint("capacity > 0", name="ck_eng_activity_capacity"),
        CheckConstraint(
            "confirmed_count >= 0 AND confirmed_count <= capacity", name="ck_eng_activity_confirmed"
        ),
        CheckConstraint("waitlist_count >= 0", name="ck_eng_activity_waitlist"),
        UniqueConstraint("tenant_id", "activity_id", "version", name="uk_eng_activity_version"),
        UniqueConstraint("tenant_id", "id", name="uk_eng_activity_version_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "activity_id"],
            ["engagement_activities.tenant_id", "engagement_activities.id"],
            name="fk_eng_activity_version_activity",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "approval_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_eng_activity_version_approval",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_activity_version_creator",
        ),
        Index("ix_eng_activity_version_schedule", "tenant_id", "status", "starts_at"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    activity_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    registration_opens_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    registration_closes_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    confirmed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    waitlist_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    attendee_rules_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    audience_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    attachments_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    cancellation_terms: Mapped[str] = mapped_column(String(1000), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EngagementActivityRegistration(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "engagement_activity_registrations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('CONFIRMED','WAITLISTED','CANCELLED','CHECKED_IN')",
            name="ck_eng_activity_registration_status",
        ),
        CheckConstraint("attendee_count > 0", name="ck_eng_activity_registration_count"),
        CheckConstraint(
            "waitlist_position IS NULL OR waitlist_position > 0",
            name="ck_eng_activity_waitlist_position",
        ),
        CheckConstraint("lock_version > 0", name="ck_eng_activity_registration_lock"),
        UniqueConstraint(
            "tenant_id",
            "activity_version_id",
            "party_id",
            name="uk_eng_activity_registration_party",
        ),
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_eng_activity_registration_key"),
        UniqueConstraint("tenant_id", "id", name="uk_eng_activity_registration_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_eng_activity_registration_park",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "activity_id"],
            ["engagement_activities.tenant_id", "engagement_activities.id"],
            name="fk_eng_activity_registration_activity",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "activity_version_id"],
            ["engagement_activity_versions.tenant_id", "engagement_activity_versions.id"],
            name="fk_eng_activity_registration_version",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_eng_activity_registration_party",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["tenant_service_principals.tenant_id", "tenant_service_principals.id"],
            name="fk_eng_activity_registration_principal",
        ),
        Index(
            "ix_eng_activity_registration_queue",
            "tenant_id",
            "activity_version_id",
            "status",
            "waitlist_position",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    activity_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    activity_version_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    party_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    principal_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attendee_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    waitlist_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EngagementActivityEvent(Base, PrimaryKeyMixin):
    __tablename__ = "engagement_activity_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('UPDATED','SUBMITTED','APPROVED','PUBLISHED','REGISTRATION_CLOSED','IN_PROGRESS','REGISTERED','WAITLISTED','PROMOTED','CANCELLED','CHECKED_IN','COMPLETED')",
            name="ck_eng_activity_event_type",
        ),
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_eng_activity_event_key"),
        ForeignKeyConstraint(
            ["tenant_id", "activity_id"],
            ["engagement_activities.tenant_id", "engagement_activities.id"],
            name="fk_eng_activity_event_activity",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "registration_id"],
            ["engagement_activity_registrations.tenant_id", "engagement_activity_registrations.id"],
            name="fk_eng_activity_event_registration",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "actor_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_activity_event_actor",
        ),
        Index("ix_eng_activity_event_timeline", "tenant_id", "activity_id", "occurred_at"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    activity_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    registration_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class EngagementActivityFeedback(Base, PrimaryKeyMixin):
    __tablename__ = "engagement_activity_feedback"
    __table_args__ = (
        CheckConstraint("score BETWEEN 1 AND 5", name="ck_eng_activity_feedback_score"),
        UniqueConstraint(
            "tenant_id", "registration_id", name="uk_eng_activity_feedback_registration"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "registration_id"],
            ["engagement_activity_registrations.tenant_id", "engagement_activity_registrations.id"],
            name="fk_eng_activity_feedback_registration",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_eng_activity_feedback_party",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    registration_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    party_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class EngagementAnnouncement(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "engagement_announcements"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','PENDING_APPROVAL','APPROVED','SCHEDULED','PUBLISHED','REJECTED','EXPIRED','WITHDRAWN')",
            name="ck_eng_announcement_status",
        ),
        CheckConstraint("current_version >= 1", name="ck_eng_announcement_version"),
        CheckConstraint("lock_version > 0", name="ck_eng_announcement_lock"),
        UniqueConstraint("tenant_id", "code", name="uk_eng_announcement_code"),
        UniqueConstraint("tenant_id", "id", name="uk_eng_announcement_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_eng_announcement_park",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "approval_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_eng_announcement_approval",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_announcement_creator",
        ),
        Index("ix_eng_announcement_scope", "tenant_id", "park_id", "status"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    code: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT")
    current_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    published_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approval_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)


class EngagementAnnouncementVersion(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "engagement_announcement_versions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','APPROVED','SCHEDULED','PUBLISHED','REJECTED','RETIRED')",
            name="ck_eng_announcement_version_status",
        ),
        CheckConstraint("version >= 1", name="ck_eng_announcement_version_no"),
        CheckConstraint(
            "priority IN ('NORMAL','IMPORTANT','URGENT')", name="ck_eng_announcement_priority"
        ),
        CheckConstraint(
            "expires_at IS NULL OR expires_at > publish_at", name="ck_eng_announcement_expiry"
        ),
        CheckConstraint(
            "pin_to IS NULL OR pin_from IS NULL OR pin_to >= pin_from",
            name="ck_eng_announcement_pin_window",
        ),
        UniqueConstraint(
            "tenant_id", "announcement_id", "version", name="uk_eng_announcement_version"
        ),
        UniqueConstraint("tenant_id", "id", name="uk_eng_announcement_version_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "announcement_id"],
            ["engagement_announcements.tenant_id", "engagement_announcements.id"],
            name="fk_eng_announcement_version_header",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "approval_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_eng_announcement_version_approval",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_announcement_version_creator",
        ),
        Index("ix_eng_announcement_publish", "tenant_id", "status", "publish_at", "expires_at"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    announcement_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="NORMAL")
    pin_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pin_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    publish_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attachments_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    audience_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EngagementAnnouncementTarget(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "engagement_announcement_targets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('TARGETED','DELIVERED','SKIPPED','FAILED','READ')",
            name="ck_eng_announcement_target_status",
        ),
        UniqueConstraint(
            "tenant_id",
            "announcement_version_id",
            "recipient_user_id",
            name="uk_eng_announcement_target_recipient",
        ),
        UniqueConstraint("tenant_id", "id", name="uk_eng_announcement_target_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "announcement_id"],
            ["engagement_announcements.tenant_id", "engagement_announcements.id"],
            name="fk_eng_announcement_target_header",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "announcement_version_id"],
            ["engagement_announcement_versions.tenant_id", "engagement_announcement_versions.id"],
            name="fk_eng_announcement_target_version",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_eng_announcement_target_park",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_eng_announcement_target_party",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "recipient_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_announcement_target_recipient",
        ),
        Index(
            "ix_eng_announcement_target_delivery", "tenant_id", "announcement_version_id", "status"
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    announcement_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    announcement_version_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    park_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    party_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    recipient_user_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    source_type: Mapped[str] = mapped_column(String(24), nullable=False)
    source_key: Mapped[str] = mapped_column(String(128), nullable=False)
    audience_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="TARGETED")


class EngagementAnnouncementDelivery(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "engagement_announcement_deliveries"
    __table_args__ = (
        CheckConstraint("channel = 'IN_APP'", name="ck_eng_announcement_delivery_channel"),
        CheckConstraint(
            "status IN ('PENDING','DELIVERED','SKIPPED','FAILED','READ')",
            name="ck_eng_announcement_delivery_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_eng_announcement_delivery_attempts"),
        UniqueConstraint("tenant_id", "target_id", name="uk_eng_announcement_delivery_target"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_eng_announcement_delivery_key"),
        ForeignKeyConstraint(
            ["tenant_id", "target_id"],
            ["engagement_announcement_targets.tenant_id", "engagement_announcement_targets.id"],
            name="fk_eng_announcement_delivery_target",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["business_events.tenant_id", "business_events.id"],
            name="fk_eng_announcement_delivery_event",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "notification_id"],
            ["in_app_notifications.tenant_id", "in_app_notifications.id"],
            name="fk_eng_announcement_delivery_notification",
        ),
        Index("ix_eng_announcement_delivery_retry", "tenant_id", "status", "updated_at"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    target_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    event_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    notification_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(192), nullable=False)
    channel: Mapped[str] = mapped_column(
        String(16), nullable=False, default="IN_APP", server_default="IN_APP"
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EngagementMigrationRun(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "engagement_migration_runs"
    __table_args__ = (
        CheckConstraint(
            "provenance IN ('SYNTHETIC','DEIDENTIFIED','REAL')", name="ck_eng_migration_provenance"
        ),
        CheckConstraint(
            "status IN ('DRY_RUN','RUNNING','SUCCEEDED','FAILED','ROLLED_BACK')",
            name="ck_eng_migration_status",
        ),
        CheckConstraint("production_contacted = FALSE", name="ck_eng_migration_no_production"),
        UniqueConstraint("tenant_id", "run_key", name="uk_eng_migration_run_key"),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_migration_creator",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    run_key: Mapped[str] = mapped_column(String(128), nullable=False)
    source_system: Mapped[str] = mapped_column(String(128), nullable=False)
    provenance: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    checkpoint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    report_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    production_contacted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)

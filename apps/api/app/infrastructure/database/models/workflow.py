"""版本化审批定义、实例、任务、委托与事件 ORM。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, TimestampMixin


class ApprovalDefinition(Base, PrimaryKeyMixin, TimestampMixin):
    """租户内审批定义；已发布版本不可原位修改。"""

    __tablename__ = "approval_definitions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uk_approval_definition_code"),
        CheckConstraint("status IN ('ACTIVE', 'RETIRED')", name="ck_approval_definition_status"),
        Index("ix_approval_definitions_tenant_biz", "tenant_id", "biz_type", "status"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("parks.id"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    biz_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    updated_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"))


class ApprovalDefinitionVersion(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "approval_definition_versions"
    __table_args__ = (
        UniqueConstraint("definition_id", "version", name="uk_approval_definition_version"),
        CheckConstraint(
            "status IN ('DRAFT', 'PUBLISHED', 'RETIRED')",
            name="ck_approval_definition_version_status",
        ),
        Index(
            "uk_approval_definition_one_draft",
            "definition_id",
            unique=True,
            postgresql_where=text("status = 'DRAFT'"),
            sqlite_where=text("status = 'DRAFT'"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    definition_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("approval_definitions.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    published_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ApprovalDefinitionStep(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "approval_definition_steps"
    __table_args__ = (
        UniqueConstraint("version_id", "step_order", name="uk_approval_step_order"),
        CheckConstraint("approval_mode IN ('ANY', 'ALL')", name="ck_approval_step_mode"),
        CheckConstraint("step_order > 0", name="ck_approval_step_order_positive"),
        CheckConstraint("min_approvals > 0", name="ck_approval_step_min_positive"),
        CheckConstraint("sla_hours > 0", name="ck_approval_step_sla_positive"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    version_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("approval_definition_versions.id"), nullable=False, index=True
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    approval_mode: Mapped[str] = mapped_column(String(8), nullable=False, default="ANY")
    min_approvals: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sla_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)


class ApprovalStepAssignee(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "approval_step_assignees"
    __table_args__ = (
        CheckConstraint(
            "(user_id IS NOT NULL AND role_id IS NULL) OR "
            "(user_id IS NULL AND role_id IS NOT NULL)",
            name="ck_approval_assignee_exactly_one",
        ),
        UniqueConstraint("step_id", "user_id", name="uk_approval_step_user"),
        UniqueConstraint("step_id", "role_id", name="uk_approval_step_role"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    step_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("approval_definition_steps.id"), nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    role_id: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("roles.id"))


class ApprovalRequest(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "approval_requests"
    __table_args__ = (
        UniqueConstraint("tenant_id", "biz_type", "biz_id", name="uk_approval_biz"),
        Index(
            "uk_approval_request_no",
            "tenant_id",
            "request_no",
            unique=True,
            postgresql_where=text("request_no IS NOT NULL"),
            sqlite_where=text("request_no IS NOT NULL"),
        ),
        Index(
            "uk_approval_submit_idempotency",
            "tenant_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
            sqlite_where=text("idempotency_key IS NOT NULL"),
        ),
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'RETURNED', 'WITHDRAWN')",
            name="ck_approval_request_status_v2",
        ),
        CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')",
            name="ck_approval_request_priority",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("parks.id"), nullable=True, index=True
    )
    biz_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    biz_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    applicant_user_id: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    approver_user_id: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    definition_version_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("approval_definition_versions.id"), nullable=True, index=True
    )
    request_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="MEDIUM")
    current_step_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    compatibility_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="NATIVE")


class ApprovalDelegation(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "approval_delegations"
    __table_args__ = (
        CheckConstraint("grantor_user_id <> delegate_user_id", name="ck_delegation_not_self"),
        CheckConstraint("ends_at > starts_at", name="ck_delegation_time_order"),
        CheckConstraint("status IN ('ACTIVE', 'REVOKED')", name="ck_delegation_status"),
        Index(
            "ix_approval_delegation_effective",
            "tenant_id",
            "grantor_user_id",
            "status",
            "starts_at",
            "ends_at",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    grantor_user_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=False, index=True
    )
    delegate_user_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=False, index=True
    )
    biz_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"))


class ApprovalTask(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "approval_tasks"
    __table_args__ = (
        UniqueConstraint(
            "approval_id",
            "round_no",
            "step_order",
            "assignee_user_id",
            name="uk_approval_task_candidate",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'RETURNED', 'SKIPPED', 'CANCELLED')",
            name="ck_approval_task_status",
        ),
        Index(
            "uk_approval_task_decision_key",
            "tenant_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
            sqlite_where=text("idempotency_key IS NOT NULL"),
        ),
        Index(
            "ix_approval_tasks_inbox",
            "tenant_id",
            "assignee_user_id",
            "status",
            "due_at",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    approval_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("approval_requests.id"), nullable=False, index=True
    )
    step_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("approval_definition_steps.id"), nullable=False, index=True
    )
    round_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    assignee_user_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decision_remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    acted_by_user_id: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    delegation_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("approval_delegations.id"), nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ApprovalEvent(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "approval_events"
    __table_args__ = (
        Index(
            "uk_approval_event_idempotency",
            "tenant_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
            sqlite_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    approval_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("approval_requests.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    step_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    task_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("approval_tasks.id"), nullable=True, index=True
    )
    original_assignee_user_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

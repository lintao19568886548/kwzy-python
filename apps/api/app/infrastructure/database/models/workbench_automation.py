"""Event-driven workbench automation persistence models."""

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


class BusinessEvent(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "business_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_business_event_idempotency"),
        Index("ix_business_event_dispatch", "tenant_id", "occurred_at", "id"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("parks.id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(96), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(192), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class EventConsumerLog(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "event_consumer_logs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "event_id",
            "consumer_name",
            "generation",
            name="uk_event_consumer_generation",
        ),
        CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCEEDED','RETRY','DEAD')",
            name="ck_event_consumer_status",
        ),
        Index(
            "ix_event_consumer_claim",
            "tenant_id",
            "consumer_name",
            "status",
            "next_attempt_at",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    event_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("business_events.id"), nullable=False, index=True
    )
    consumer_name: Mapped[str] = mapped_column(String(96), nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    claimed_by: Mapped[Optional[str]] = mapped_column(String(96), nullable=True)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)


class AutomationRule(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "automation_rules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uk_automation_rule_code"),
        CheckConstraint("status IN ('ACTIVE','RETIRED')", name="ck_automation_rule_status"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("parks.id"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    updated_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))


class AutomationRuleVersion(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "automation_rule_versions"
    __table_args__ = (
        UniqueConstraint("rule_id", "version", name="uk_automation_rule_version"),
        CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','RETIRED')",
            name="ck_automation_rule_version_status",
        ),
        Index("ix_automation_rule_match", "tenant_id", "event_type", "status"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    rule_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("automation_rules.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    event_type: Mapped[str] = mapped_column(String(96), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    conditions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    actions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    published_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AutomationExecution(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "automation_executions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "event_id", "rule_version_id", name="uk_automation_execution"
        ),
        CheckConstraint(
            "status IN ('MATCHED','NOT_MATCHED','SUCCEEDED','FAILED')",
            name="ck_automation_execution_status",
        ),
        Index("ix_automation_execution_query", "tenant_id", "status", "created_at"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    event_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("business_events.id"), nullable=False, index=True
    )
    rule_version_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("automation_rule_versions.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    matched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    action_results_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class InAppNotification(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "in_app_notifications"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uk_in_app_notification_idempotency"
        ),
        CheckConstraint(
            "status IN ('UNREAD','READ','ARCHIVED')", name="ck_in_app_notification_status"
        ),
        CheckConstraint("channel = 'IN_APP'", name="ck_in_app_notification_channel"),
        Index(
            "ix_in_app_notification_inbox",
            "tenant_id",
            "recipient_user_id",
            "status",
            "created_at",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("parks.id"), nullable=True, index=True
    )
    recipient_user_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=False, index=True
    )
    event_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("business_events.id"), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(192), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="SYSTEM")
    channel: Mapped[str] = mapped_column(String(16), nullable=False, default="IN_APP")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    deep_link: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="UNREAD")
    delivered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SchedulerDefinition(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scheduler_definitions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uk_scheduler_definition_code"),
        CheckConstraint(
            "concurrency_policy IN ('FORBID','ALLOW')", name="ck_scheduler_concurrency_policy"
        ),
        Index("ix_scheduler_due", "tenant_id", "enabled", "next_run_at"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    handler_key: Mapped[str] = mapped_column(String(96), nullable=False)
    parameters_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    cadence_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    concurrency_policy: Mapped[str] = mapped_column(String(16), nullable=False, default="FORBID")
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    updated_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))


class SchedulerRun(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scheduler_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_scheduler_run_idempotency"),
        CheckConstraint(
            "status IN ('RUNNING','SUCCEEDED','FAILED','TIMED_OUT')",
            name="ck_scheduler_run_status",
        ),
        Index("ix_scheduler_run_query", "tenant_id", "schedule_id", "created_at"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    schedule_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("scheduler_definitions.id"), nullable=False, index=True
    )
    fire_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    idempotency_key: Mapped[str] = mapped_column(String(192), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="RUNNING")
    claim_token: Mapped[str] = mapped_column(String(96), nullable=False)
    claimed_by: Mapped[str] = mapped_column(String(96), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)


class WorkbenchLayout(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workbench_layouts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "owner_user_id", name="uk_workbench_layout_user"),
        UniqueConstraint("tenant_id", "role_id", name="uk_workbench_layout_role"),
        CheckConstraint(
            "((owner_user_id IS NOT NULL AND role_id IS NULL) OR "
            "(owner_user_id IS NULL AND role_id IS NOT NULL))",
            name="ck_workbench_layout_owner",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    owner_user_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True, index=True
    )
    role_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("roles.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))
    updated_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"))


class WorkbenchWidget(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workbench_widgets"
    __table_args__ = (
        UniqueConstraint("layout_id", "widget_key", name="uk_workbench_layout_widget"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    layout_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("workbench_layouts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    widget_key: Mapped[str] = mapped_column(String(64), nullable=False)
    position_x: Mapped[int] = mapped_column(Integer, nullable=False)
    position_y: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

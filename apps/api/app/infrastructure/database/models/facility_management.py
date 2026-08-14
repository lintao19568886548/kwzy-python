"""Facility device, inspection and IoT alarm persistence models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, TimestampMixin


class FacilityDevice(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "facility_devices"
    __table_args__ = (
        UniqueConstraint("tenant_id", "device_code", name="uk_facility_device_code"),
        UniqueConstraint("tenant_id", "id", name="uk_facility_devices_tenant_id_id"),
        UniqueConstraint(
            "tenant_id", "park_id", "id", name="uk_facility_devices_tenant_park_id"
        ),
        CheckConstraint(
            "device_type IN ('FIRE','ELEVATOR','TRANSFORMER','ELECTRICAL','HVAC','WATER','SECURITY','CUSTOM')",
            name="ck_facility_device_type",
        ),
        CheckConstraint(
            "status IN ('ACTIVE','MAINTENANCE','RETIRED')",
            name="ck_facility_device_status",
        ),
        CheckConstraint(
            "criticality IN ('LOW','MEDIUM','HIGH','CRITICAL')",
            name="ck_facility_device_criticality",
        ),
        CheckConstraint("lock_version > 0", name="ck_facility_device_lock_version"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_facility_device_park",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "unit_id"],
            ["units.tenant_id", "units.park_id", "units.id"],
            name="fk_facility_device_unit",
        ),
        Index("ix_facility_device_queue", "tenant_id", "park_id", "status", "device_type"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    unit_id: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("units.id"), nullable=True)
    device_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    device_type: Mapped[str] = mapped_column(String(32), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    criticality: Mapped[str] = mapped_column(String(16), nullable=False, default="MEDIUM")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    manufacturer: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    serial_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    commissioned_on: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    warranty_expires_on: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    properties_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    retired_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    retirement_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class FacilityDeviceHistory(Base, PrimaryKeyMixin):
    __tablename__ = "facility_device_history"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "device_id", "version_no", name="uk_facility_device_history_version"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "device_id"],
            ["facility_devices.tenant_id", "facility_devices.park_id", "facility_devices.id"],
            name="fk_facility_device_history_device",
        ),
        Index("ix_facility_device_history_timeline", "tenant_id", "device_id", "changed_at"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    device_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    before_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    changed_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class InspectionTemplate(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "inspection_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uk_inspection_template_code"),
        UniqueConstraint("tenant_id", "id", name="uk_inspection_templates_tenant_id_id"),
        CheckConstraint("status IN ('ACTIVE','RETIRED')", name="ck_inspection_template_status"),
        CheckConstraint("current_version >= 0", name="ck_inspection_template_current_version"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    device_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)


class InspectionTemplateVersion(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "inspection_template_versions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "template_id", "version_no", name="uk_inspection_template_version"
        ),
        UniqueConstraint(
            "tenant_id", "id", name="uk_inspection_template_versions_tenant_id_id"
        ),
        CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','RETIRED')",
            name="ck_inspection_template_version_status",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "template_id"],
            ["inspection_templates.tenant_id", "inspection_templates.id"],
            name="fk_inspection_template_version_template",
        ),
        Index(
            "uk_inspection_template_published",
            "tenant_id",
            "template_id",
            unique=True,
            postgresql_where=text("status = 'PUBLISHED'"),
            sqlite_where=text("status = 'PUBLISHED'"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    template_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    published_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    retired_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class InspectionTemplateItem(Base, PrimaryKeyMixin):
    __tablename__ = "inspection_template_items"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "template_version_id", "item_code", name="uk_inspection_item_code"
        ),
        UniqueConstraint(
            "tenant_id", "template_version_id", "position", name="uk_inspection_item_position"
        ),
        CheckConstraint(
            "result_type IN ('BOOLEAN','NUMBER','TEXT','SELECT')",
            name="ck_inspection_item_result_type",
        ),
        CheckConstraint("position > 0", name="ck_inspection_item_position"),
        ForeignKeyConstraint(
            ["tenant_id", "template_version_id"],
            ["inspection_template_versions.tenant_id", "inspection_template_versions.id"],
            name="fk_inspection_item_version",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    template_version_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    item_code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    result_type: Mapped[str] = mapped_column(String(16), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    critical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    minimum: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    maximum: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    options_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)


class InspectionSchedule(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "inspection_schedules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uk_inspection_schedule_code"),
        UniqueConstraint("tenant_id", "id", name="uk_inspection_schedules_tenant_id_id"),
        UniqueConstraint(
            "tenant_id", "park_id", "id", name="uk_inspection_schedules_tenant_park_id"
        ),
        CheckConstraint("status IN ('ACTIVE','PAUSED','RETIRED')", name="ck_inspection_schedule_status"),
        CheckConstraint("weekday >= 1 AND weekday <= 7", name="ck_inspection_schedule_weekday"),
        CheckConstraint(
            "completion_window_minutes > 0 AND completion_window_minutes <= 10080",
            name="ck_inspection_schedule_window",
        ),
        CheckConstraint("lock_version > 0", name="ck_inspection_schedule_lock_version"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "device_id"],
            ["facility_devices.tenant_id", "facility_devices.park_id", "facility_devices.id"],
            name="fk_inspection_schedule_device",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "template_version_id"],
            ["inspection_template_versions.tenant_id", "inspection_template_versions.id"],
            name="fk_inspection_schedule_template_version",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "assignee_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_inspection_schedule_assignee",
        ),
        Index("ix_inspection_schedule_generation", "tenant_id", "status", "weekday"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    device_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    template_version_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    assignee_user_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai")
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    local_due_time: Mapped[str] = mapped_column(String(5), nullable=False)
    completion_window_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=1440)
    missed_work_order: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class InspectionTask(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "inspection_tasks"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "schedule_id", "window_start", name="uk_inspection_task_window"
        ),
        UniqueConstraint("tenant_id", "id", name="uk_inspection_tasks_tenant_id_id"),
        UniqueConstraint(
            "tenant_id", "park_id", "id", name="uk_inspection_tasks_tenant_park_id"
        ),
        CheckConstraint(
            "status IN ('PENDING','IN_PROGRESS','PASSED','FAILED','MISSED','CANCELLED')",
            name="ck_inspection_task_status",
        ),
        CheckConstraint("lock_version > 0", name="ck_inspection_task_lock_version"),
        CheckConstraint("window_due_at > window_start", name="ck_inspection_task_window_order"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "schedule_id"],
            ["inspection_schedules.tenant_id", "inspection_schedules.park_id", "inspection_schedules.id"],
            name="fk_inspection_task_schedule",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "device_id"],
            ["facility_devices.tenant_id", "facility_devices.park_id", "facility_devices.id"],
            name="fk_inspection_task_device",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "template_version_id"],
            ["inspection_template_versions.tenant_id", "inspection_template_versions.id"],
            name="fk_inspection_task_template_version",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "assignee_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_inspection_task_assignee",
        ),
        Index("ix_inspection_task_queue", "tenant_id", "park_id", "status", "window_due_at"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    schedule_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    device_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    template_version_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    template_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    assignee_user_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    window_due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)


class InspectionTaskEvent(Base, PrimaryKeyMixin):
    __tablename__ = "inspection_task_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_inspection_task_event_key"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "task_id"],
            ["inspection_tasks.tenant_id", "inspection_tasks.park_id", "inspection_tasks.id"],
            name="fk_inspection_task_event_task",
        ),
        Index("ix_inspection_task_event_timeline", "tenant_id", "task_id", "occurred_at"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    task_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    detail_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class InspectionResult(Base, PrimaryKeyMixin):
    __tablename__ = "inspection_results"
    __table_args__ = (
        UniqueConstraint("tenant_id", "task_id", "item_code", name="uk_inspection_result_item"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "task_id"],
            ["inspection_tasks.tenant_id", "inspection_tasks.park_id", "inspection_tasks.id"],
            name="fk_inspection_result_task",
        ),
        CheckConstraint("length(item_code) > 0", name="ck_inspection_result_item_code"),
        CheckConstraint("position > 0", name="ck_inspection_result_position"),
        CheckConstraint(
            "result_type IN ('BOOLEAN','NUMBER','TEXT','SELECT')",
            name="ck_inspection_result_type",
        ),
        Index("ix_inspection_result_task", "tenant_id", "task_id", "position"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    task_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    item_code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    result_type: Mapped[str] = mapped_column(String(16), nullable=False)
    text_value: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    number_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    critical: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evidence_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    remark: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    recorded_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class InspectionException(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "inspection_exceptions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "task_id", "item_code", name="uk_inspection_exception_item"),
        UniqueConstraint("tenant_id", "id", name="uk_inspection_exceptions_tenant_id_id"),
        CheckConstraint(
            "status IN ('OPEN','PROMOTED','RESOLVED')", name="ck_inspection_exception_status"
        ),
        CheckConstraint(
            "severity IN ('INFO','WARNING','HIGH','CRITICAL')",
            name="ck_inspection_exception_severity",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "task_id"],
            ["inspection_tasks.tenant_id", "inspection_tasks.park_id", "inspection_tasks.id"],
            name="fk_inspection_exception_task",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "work_order_id"],
            ["work_orders.tenant_id", "work_orders.park_id", "work_orders.id"],
            name="fk_inspection_exception_work_order",
        ),
        Index("ix_inspection_exception_queue", "tenant_id", "park_id", "status", "created_at"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    task_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    item_code: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="OPEN")
    work_order_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    promoted_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class IoTProvider(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "iot_providers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uk_iot_provider_code"),
        UniqueConstraint("tenant_id", "id", name="uk_iot_providers_tenant_id_id"),
        CheckConstraint(
            "status IN ('NOT_CONNECTED','SANDBOX','CONNECTED','DEGRADED')",
            name="ck_iot_provider_status",
        ),
        CheckConstraint(
            "adapter_kind IN ('LOCAL','SANDBOX','HTTP')", name="ck_iot_provider_adapter_kind"
        ),
        CheckConstraint(
            "correlation_minutes > 0 AND correlation_minutes <= 10080",
            name="ck_iot_provider_correlation_minutes",
        ),
        CheckConstraint("lock_version > 0", name="ck_iot_provider_lock_version"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    adapter_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    environment: Mapped[str] = mapped_column(String(16), nullable=False, default="LOCAL")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="NOT_CONNECTED")
    credential_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    severity_mapping_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    correlation_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    last_health_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_health_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class IoTDeviceBinding(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "iot_device_bindings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uk_iot_device_bindings_tenant_id_id"),
        CheckConstraint("status IN ('ACTIVE','RETIRED')", name="ck_iot_binding_status"),
        CheckConstraint("lock_version > 0", name="ck_iot_binding_lock_version"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "device_id"],
            ["facility_devices.tenant_id", "facility_devices.park_id", "facility_devices.id"],
            name="fk_iot_binding_device",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "provider_id"],
            ["iot_providers.tenant_id", "iot_providers.id"],
            name="fk_iot_binding_provider",
        ),
        Index(
            "uk_iot_binding_external_active",
            "tenant_id",
            "provider_id",
            "external_device_key",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
        Index(
            "uk_iot_binding_device_active",
            "tenant_id",
            "provider_id",
            "device_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    provider_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    device_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    external_device_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    activated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    changed_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    change_reason: Mapped[str] = mapped_column(String(1000), nullable=False)


class IoTBindingHistory(Base, PrimaryKeyMixin):
    __tablename__ = "iot_binding_history"
    __table_args__ = (
        UniqueConstraint("tenant_id", "binding_id", "version_no", name="uk_iot_binding_history_version"),
        ForeignKeyConstraint(
            ["tenant_id", "binding_id"],
            ["iot_device_bindings.tenant_id", "iot_device_bindings.id"],
            name="fk_iot_binding_history_binding",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    binding_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    changed_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class IoTAlarm(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "iot_alarms"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uk_iot_alarms_tenant_id_id"),
        UniqueConstraint("tenant_id", "park_id", "id", name="uk_iot_alarms_tenant_park_id"),
        CheckConstraint(
            "severity IN ('INFO','WARNING','HIGH','CRITICAL')", name="ck_iot_alarm_severity"
        ),
        CheckConstraint(
            "status IN ('OPEN','ACKNOWLEDGED','RESOLVED','CLOSED')", name="ck_iot_alarm_status"
        ),
        CheckConstraint("occurrence_count > 0", name="ck_iot_alarm_occurrences"),
        CheckConstraint("lock_version > 0", name="ck_iot_alarm_lock_version"),
        ForeignKeyConstraint(
            ["tenant_id", "binding_id"],
            ["iot_device_bindings.tenant_id", "iot_device_bindings.id"],
            name="fk_iot_alarm_binding",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "device_id"],
            ["facility_devices.tenant_id", "facility_devices.park_id", "facility_devices.id"],
            name="fk_iot_alarm_device",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "work_order_id"],
            ["work_orders.tenant_id", "work_orders.park_id", "work_orders.id"],
            name="fk_iot_alarm_work_order",
        ),
        Index(
            "uk_iot_alarm_active_correlation",
            "tenant_id",
            "binding_id",
            "alarm_type",
            unique=True,
            postgresql_where=text("status IN ('OPEN','ACKNOWLEDGED')"),
            sqlite_where=text("status IN ('OPEN','ACKNOWLEDGED')"),
        ),
        Index("ix_iot_alarm_queue", "tenant_id", "park_id", "status", "severity", "last_seen_at"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    binding_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    device_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    alarm_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="OPEN")
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    work_order_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    resolution_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class IoTAlarmEvent(Base, PrimaryKeyMixin):
    __tablename__ = "iot_alarm_events"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "provider_id", "source_event_id", name="uk_iot_alarm_source_event"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "provider_id"],
            ["iot_providers.tenant_id", "iot_providers.id"],
            name="fk_iot_alarm_event_provider",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "binding_id"],
            ["iot_device_bindings.tenant_id", "iot_device_bindings.id"],
            name="fk_iot_alarm_event_binding",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "alarm_id"],
            ["iot_alarms.tenant_id", "iot_alarms.park_id", "iot_alarms.id"],
            name="fk_iot_alarm_event_alarm",
        ),
        Index("ix_iot_alarm_event_timeline", "tenant_id", "alarm_id", "source_time"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    provider_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    binding_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    alarm_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    raw_severity: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_severity: Mapped[str] = mapped_column(String(16), nullable=False)
    alarm_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    safe_payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class IoTAlarmEscalation(Base, PrimaryKeyMixin):
    __tablename__ = "iot_alarm_escalations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "alarm_id", "level", name="uk_iot_alarm_escalation_level"),
        CheckConstraint("level >= 1 AND level <= 4", name="ck_iot_alarm_escalation_level"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "alarm_id"],
            ["iot_alarms.tenant_id", "iot_alarms.park_id", "iot_alarms.id"],
            name="fk_iot_alarm_escalation_alarm",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    alarm_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

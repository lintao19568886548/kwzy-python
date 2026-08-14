"""Workforce, roster, attendance, performance and qualification evidence models."""

from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, TimestampMixin


class WorkforceEmployee(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workforce_employees"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE','SUSPENDED','LEFT')", name="ck_workforce_employee_status"
        ),
        CheckConstraint("lock_version > 0", name="ck_workforce_employee_lock"),
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date", name="ck_workforce_employee_dates"
        ),
        UniqueConstraint("tenant_id", "employee_no", name="uk_workforce_employee_no"),
        UniqueConstraint("tenant_id", "id", name="uk_workforce_employee_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_workforce_employee_park",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_workforce_employee_user",
        ),
        Index("ix_workforce_employee_scope", "tenant_id", "park_id", "status"),
        Index(
            "uk_workforce_employee_active_user",
            "tenant_id",
            "user_id",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL AND status <> 'LEFT'"),
            sqlite_where=text("user_id IS NOT NULL AND status <> 'LEFT'"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    employee_no: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    department_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    position_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    mobile_masked: Mapped[str | None] = mapped_column(String(16), nullable=True)
    mobile_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    identity_masked: Mapped[str | None] = mapped_column(String(16), nullable=True)
    identity_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)


class WorkforceEmployeeEvent(Base, PrimaryKeyMixin):
    __tablename__ = "workforce_employee_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "employee_id"],
            ["workforce_employees.tenant_id", "workforce_employees.id"],
            name="fk_workforce_employee_event_employee",
        ),
        Index("ix_workforce_employee_event_timeline", "tenant_id", "employee_id", "occurred_at"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    employee_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ShiftTemplate(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workforce_shift_templates"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE','RETIRED')", name="ck_workforce_shift_template_status"
        ),
        CheckConstraint("lock_version > 0", name="ck_workforce_shift_template_lock"),
        UniqueConstraint("tenant_id", "park_id", "code", name="uk_workforce_shift_template_code"),
        UniqueConstraint("tenant_id", "id", name="uk_workforce_shift_template_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_workforce_shift_template_park",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)


class ShiftTemplateVersion(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workforce_shift_template_versions"
    __table_args__ = (
        CheckConstraint("version_no > 0", name="ck_workforce_shift_version_no"),
        CheckConstraint("break_minutes BETWEEN 0 AND 480", name="ck_workforce_shift_break"),
        UniqueConstraint(
            "tenant_id", "template_id", "version_no", name="uk_workforce_shift_version"
        ),
        UniqueConstraint("tenant_id", "id", name="uk_workforce_shift_version_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "template_id"],
            ["workforce_shift_templates.tenant_id", "workforce_shift_templates.id"],
            name="fk_workforce_shift_version_template",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    template_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    cross_day: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    break_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    late_grace_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    early_grace_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    published_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)


class ShiftAssignment(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workforce_shift_assignments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE','CANCELLED')", name="ck_workforce_shift_assignment_status"
        ),
        CheckConstraint("lock_version > 0", name="ck_workforce_shift_assignment_lock"),
        UniqueConstraint("tenant_id", "id", name="uk_workforce_shift_assignment_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "employee_id"],
            ["workforce_employees.tenant_id", "workforce_employees.id"],
            name="fk_workforce_shift_assignment_employee",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "shift_version_id"],
            ["workforce_shift_template_versions.tenant_id", "workforce_shift_template_versions.id"],
            name="fk_workforce_shift_assignment_version",
        ),
        Index(
            "uk_workforce_shift_assignment_active",
            "tenant_id",
            "employee_id",
            "work_date",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
        Index("ix_workforce_roster_scope", "tenant_id", "park_id", "work_date"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    employee_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    shift_version_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    assigned_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)


class AttendancePolicy(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workforce_attendance_policies"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE','RETIRED')", name="ck_workforce_attendance_policy_status"
        ),
        CheckConstraint(
            "geofence_radius_m BETWEEN 10 AND 5000", name="ck_workforce_attendance_radius"
        ),
        UniqueConstraint(
            "tenant_id", "park_id", "code", name="uk_workforce_attendance_policy_code"
        ),
        UniqueConstraint("tenant_id", "id", name="uk_workforce_attendance_policy_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_workforce_attendance_policy_park",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    geofence_radius_m: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    allow_manual: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )


class AttendanceLocation(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workforce_attendance_locations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE','RETIRED')", name="ck_workforce_attendance_location_status"
        ),
        CheckConstraint(
            "radius_m BETWEEN 10 AND 5000", name="ck_workforce_attendance_location_radius"
        ),
        UniqueConstraint(
            "tenant_id", "park_id", "code", name="uk_workforce_attendance_location_code"
        ),
        UniqueConstraint("tenant_id", "id", name="uk_workforce_attendance_location_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_workforce_attendance_location_park",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    config_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    radius_m: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")


class AttendancePunch(Base, PrimaryKeyMixin):
    __tablename__ = "workforce_attendance_punches"
    __table_args__ = (
        CheckConstraint("punch_type IN ('IN','OUT')", name="ck_workforce_punch_type"),
        CheckConstraint("source IN ('MANUAL','DEVICE','MOBILE')", name="ck_workforce_punch_source"),
        CheckConstraint(
            "location_result IN ('INSIDE','OUTSIDE','NOT_CHECKED')",
            name="ck_workforce_punch_location_result",
        ),
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_workforce_punch_key"),
        ForeignKeyConstraint(
            ["tenant_id", "employee_id"],
            ["workforce_employees.tenant_id", "workforce_employees.id"],
            name="fk_workforce_punch_employee",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "location_id"],
            ["workforce_attendance_locations.tenant_id", "workforce_attendance_locations.id"],
            name="fk_workforce_punch_location",
        ),
        Index("ix_workforce_punch_day", "tenant_id", "employee_id", "punched_at"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    employee_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    location_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    punch_type: Mapped[str] = mapped_column(String(8), nullable=False)
    punched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    location_result: Mapped[str] = mapped_column(String(16), nullable=False)
    distance_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    device_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AttendanceDailySummary(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workforce_attendance_summaries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('NORMAL','LATE','EARLY','ABSENT','LEAVE','ANOMALY','ADJUSTED')",
            name="ck_workforce_attendance_summary_status",
        ),
        CheckConstraint("lock_version > 0", name="ck_workforce_attendance_summary_lock"),
        UniqueConstraint(
            "tenant_id", "employee_id", "work_date", name="uk_workforce_attendance_summary_day"
        ),
        UniqueConstraint("tenant_id", "id", name="uk_workforce_attendance_summary_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "employee_id"],
            ["workforce_employees.tenant_id", "workforce_employees.id"],
            name="fk_workforce_attendance_summary_employee",
        ),
        Index(
            "ix_workforce_attendance_summary_scope", "tenant_id", "park_id", "work_date", "status"
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    employee_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    worked_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_in_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_out_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    anomaly_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    adjustment_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    adjusted_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )


class WorkforceLeaveRequest(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workforce_leave_requests"
    __table_args__ = (
        CheckConstraint(
            "leave_type IN ('ANNUAL','SICK','PERSONAL','MATERNITY','PATERNITY','OTHER')",
            name="ck_workforce_leave_type",
        ),
        CheckConstraint(
            "status IN ('DRAFT','PENDING_APPROVAL','APPROVED','REJECTED','RETURNED','CANCELLED')",
            name="ck_workforce_leave_status",
        ),
        CheckConstraint("end_at > start_at", name="ck_workforce_leave_dates"),
        CheckConstraint("lock_version > 0", name="ck_workforce_leave_lock"),
        UniqueConstraint("tenant_id", "request_key", name="uk_workforce_leave_key"),
        UniqueConstraint("tenant_id", "id", name="uk_workforce_leave_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "employee_id"],
            ["workforce_employees.tenant_id", "workforce_employees.id"],
            name="fk_workforce_leave_employee",
        ),
        Index("ix_workforce_leave_scope", "tenant_id", "park_id", "status", "start_at"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    employee_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    leave_type: Mapped[str] = mapped_column(String(16), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    approval_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("approval_requests.id"), nullable=True
    )
    request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_by: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=False)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PerformanceCycle(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workforce_performance_cycles"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','ACTIVE','CLOSED')", name="ck_workforce_performance_cycle_status"
        ),
        CheckConstraint("end_date >= start_date", name="ck_workforce_performance_cycle_dates"),
        CheckConstraint("lock_version > 0", name="ck_workforce_performance_cycle_lock"),
        UniqueConstraint(
            "tenant_id", "park_id", "code", name="uk_workforce_performance_cycle_code"
        ),
        UniqueConstraint("tenant_id", "id", name="uk_workforce_performance_cycle_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_workforce_performance_cycle_park",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )


class PerformanceGoal(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workforce_performance_goals"
    __table_args__ = (
        CheckConstraint(
            "weight > 0 AND weight <= 100", name="ck_workforce_performance_goal_weight"
        ),
        CheckConstraint(
            "status IN ('DRAFT','LOCKED')", name="ck_workforce_performance_goal_status"
        ),
        UniqueConstraint(
            "tenant_id",
            "cycle_id",
            "employee_id",
            "code",
            name="uk_workforce_performance_goal_code",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "cycle_id"],
            ["workforce_performance_cycles.tenant_id", "workforce_performance_cycles.id"],
            name="fk_workforce_performance_goal_cycle",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "employee_id"],
            ["workforce_employees.tenant_id", "workforce_employees.id"],
            name="fk_workforce_performance_goal_employee",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    cycle_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    employee_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)
    target_value: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")


class PerformanceReview(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workforce_performance_reviews"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','ACKNOWLEDGED')",
            name="ck_workforce_performance_review_status",
        ),
        CheckConstraint(
            "rating >= 0 AND rating <= 100", name="ck_workforce_performance_review_rating"
        ),
        CheckConstraint(
            "reviewer_user_id <> employee_user_id OR employee_user_id IS NULL",
            name="ck_workforce_performance_review_no_self",
        ),
        CheckConstraint("lock_version > 0", name="ck_workforce_performance_review_lock"),
        UniqueConstraint(
            "tenant_id", "cycle_id", "employee_id", name="uk_workforce_performance_review_subject"
        ),
        UniqueConstraint("tenant_id", "id", name="uk_workforce_performance_review_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "cycle_id"],
            ["workforce_performance_cycles.tenant_id", "workforce_performance_cycles.id"],
            name="fk_workforce_performance_review_cycle",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "employee_id"],
            ["workforce_employees.tenant_id", "workforce_employees.id"],
            name="fk_workforce_performance_review_employee",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    cycle_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    employee_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    employee_user_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True
    )
    reviewer_user_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(String(2000), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledgement: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )


class QualificationType(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workforce_qualification_types"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE','RETIRED')", name="ck_workforce_qualification_type_status"
        ),
        CheckConstraint(
            "validity_months IS NULL OR validity_months > 0",
            name="ck_workforce_qualification_type_validity",
        ),
        CheckConstraint(
            "reminder_days BETWEEN 0 AND 3650", name="ck_workforce_qualification_type_reminder"
        ),
        UniqueConstraint("tenant_id", "code", name="uk_workforce_qualification_type_code"),
        UniqueConstraint("tenant_id", "id", name="uk_workforce_qualification_type_tenant_id"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    validity_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reminder_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")


class EmployeeQualification(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workforce_employee_qualifications"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','VERIFIED','EXPIRED','REVOKED')",
            name="ck_workforce_employee_qualification_status",
        ),
        CheckConstraint(
            "expires_on IS NULL OR expires_on >= effective_on",
            name="ck_workforce_employee_qualification_dates",
        ),
        CheckConstraint("lock_version > 0", name="ck_workforce_employee_qualification_lock"),
        UniqueConstraint(
            "tenant_id",
            "employee_id",
            "qualification_type_id",
            "credential_fingerprint",
            name="uk_workforce_employee_qualification_credential",
        ),
        UniqueConstraint("tenant_id", "id", name="uk_workforce_employee_qualification_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "employee_id"],
            ["workforce_employees.tenant_id", "workforce_employees.id"],
            name="fk_workforce_employee_qualification_employee",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "qualification_type_id"],
            ["workforce_qualification_types.tenant_id", "workforce_qualification_types.id"],
            name="fk_workforce_employee_qualification_type",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "attachment_id"],
            ["attachments.tenant_id", "attachments.id"],
            name="fk_workforce_employee_qualification_attachment",
        ),
        Index("ix_workforce_qualification_expiry", "tenant_id", "status", "expires_on"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    employee_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    qualification_type_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    attachment_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    credential_masked: Mapped[str] = mapped_column(String(16), nullable=False)
    credential_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    issuer: Mapped[str] = mapped_column(String(255), nullable=False)
    effective_on: Mapped[date] = mapped_column(Date, nullable=False)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    verified_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )


class QualificationEvent(Base, PrimaryKeyMixin):
    __tablename__ = "workforce_qualification_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "qualification_id"],
            ["workforce_employee_qualifications.tenant_id", "workforce_employee_qualifications.id"],
            name="fk_workforce_qualification_event_credential",
        ),
        Index(
            "ix_workforce_qualification_event_timeline",
            "tenant_id",
            "qualification_id",
            "occurred_at",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    qualification_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

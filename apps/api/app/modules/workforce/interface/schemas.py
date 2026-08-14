"""Strict workforce request contracts."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmployeeCreate(StrictBody):
    park_id: int = Field(gt=0)
    employee_no: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    display_name: str = Field(min_length=1, max_length=128)
    department_name: str | None = Field(default=None, max_length=128)
    position_name: str | None = Field(default=None, max_length=128)
    user_id: int | None = Field(default=None, gt=0)
    mobile: str | None = Field(default=None, min_length=4, max_length=32)
    identity_number: str | None = Field(default=None, min_length=4, max_length=64)
    start_date: date
    end_date: date | None = None


class EmployeeUpdate(StrictBody):
    expected_version: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1000)
    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    department_name: str | None = Field(default=None, max_length=128)
    position_name: str | None = Field(default=None, max_length=128)
    user_id: int | None = Field(default=None, gt=0)
    mobile: str | None = Field(default=None, min_length=4, max_length=32)
    identity_number: str | None = Field(default=None, min_length=4, max_length=64)
    end_date: date | None = None


class EmployeeStatus(StrictBody):
    expected_version: int = Field(gt=0)
    status: Literal["ACTIVE", "SUSPENDED", "LEFT"]
    reason: str = Field(min_length=1, max_length=1000)
    end_date: date | None = None


class ShiftCreate(StrictBody):
    park_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=128)
    start_time: time
    end_time: time
    cross_day: bool = False
    break_minutes: int = Field(default=0, ge=0, le=480)
    late_grace_minutes: int = Field(default=0, ge=0, le=240)
    early_grace_minutes: int = Field(default=0, ge=0, le=240)


class ShiftVersionCreate(StrictBody):
    expected_version: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1000)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    start_time: time
    end_time: time
    cross_day: bool = False
    break_minutes: int = Field(default=0, ge=0, le=480)
    late_grace_minutes: int = Field(default=0, ge=0, le=240)
    early_grace_minutes: int = Field(default=0, ge=0, le=240)


class AssignmentCreate(StrictBody):
    employee_id: int = Field(gt=0)
    shift_version_id: int = Field(gt=0)
    work_date: date
    reason: str | None = Field(default=None, max_length=500)


class ExpectedReason(StrictBody):
    expected_version: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1000)


class PolicyCreate(StrictBody):
    park_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=128)
    geofence_radius_m: int = Field(default=300, ge=10, le=5000)
    allow_manual: bool = True


class LocationCreate(StrictBody):
    park_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=128)
    config_ref: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z][A-Za-z0-9_.:/-]*$")
    radius_m: int = Field(ge=10, le=5000)


class PunchCreate(StrictBody):
    employee_id: int = Field(gt=0)
    punch_type: Literal["IN", "OUT"]
    punched_at: datetime
    source: Literal["MANUAL", "DEVICE", "MOBILE"]
    location_id: int | None = Field(default=None, gt=0)
    distance_m: int | None = Field(default=None, ge=0, le=100000)
    device_id: str | None = Field(default=None, max_length=128)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def coordinates_are_pair(self) -> PunchCreate:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude/longitude 必须同时提供")
        return self


class SummaryGenerate(StrictBody):
    employee_id: int = Field(gt=0)
    work_date: date


class SummaryAdjust(StrictBody):
    expected_version: int = Field(gt=0)
    status: Literal["NORMAL", "LATE", "EARLY", "ABSENT", "LEAVE", "ANOMALY", "ADJUSTED"]
    worked_minutes: int = Field(ge=0, le=2880)
    reason: str = Field(min_length=1, max_length=1000)


class LeaveCreate(StrictBody):
    employee_id: int = Field(gt=0)
    leave_type: Literal["ANNUAL", "SICK", "PERSONAL", "MATERNITY", "PATERNITY", "OTHER"]
    start_at: datetime
    end_at: datetime
    reason: str = Field(min_length=1, max_length=1000)
    definition_code: str = Field(min_length=1, max_length=64)


class PerformanceCycleCreate(StrictBody):
    park_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=128)
    start_date: date
    end_date: date


class CycleStatus(StrictBody):
    expected_version: int = Field(gt=0)
    status: Literal["ACTIVE", "CLOSED"]
    reason: str = Field(min_length=1, max_length=1000)


class GoalCreate(StrictBody):
    employee_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    weight: int = Field(gt=0, le=100)
    target_value: str | None = Field(default=None, max_length=128)


class ReviewCreate(StrictBody):
    cycle_id: int = Field(gt=0)
    employee_id: int = Field(gt=0)
    rating: int = Field(ge=0, le=100)
    comment: str = Field(min_length=1, max_length=2000)


class ReviewPublish(ExpectedReason):
    pass


class ReviewAcknowledge(StrictBody):
    expected_version: int = Field(gt=0)
    acknowledgement: str = Field(min_length=1, max_length=1000)


class QualificationTypeCreate(StrictBody):
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=128)
    validity_months: int | None = Field(default=None, gt=0, le=1200)
    reminder_days: int = Field(default=30, ge=0, le=3650)


class QualificationCreate(StrictBody):
    employee_id: int = Field(gt=0)
    qualification_type_id: int = Field(gt=0)
    attachment_id: int = Field(gt=0)
    credential_number: str = Field(min_length=4, max_length=128)
    issuer: str = Field(min_length=1, max_length=255)
    effective_on: date
    expires_on: date | None = None


class QualificationRevoke(ExpectedReason):
    pass


class QualificationSweep(StrictBody):
    due_on: date

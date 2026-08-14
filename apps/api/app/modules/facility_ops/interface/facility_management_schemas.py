"""Strict request schemas for facility management APIs."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DeviceCreate(StrictBody):
    park_id: int = Field(gt=0)
    unit_id: int | None = Field(default=None, gt=0)
    device_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    device_type: Literal[
        "FIRE", "ELEVATOR", "TRANSFORMER", "ELECTRICAL", "HVAC", "WATER", "SECURITY", "CUSTOM"
    ]
    location: str = Field(min_length=1, max_length=255)
    criticality: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
    manufacturer: str | None = Field(default=None, max_length=128)
    model_no: str | None = Field(default=None, max_length=128)
    serial_no: str | None = Field(default=None, max_length=128)
    commissioned_on: datetime | None = None
    warranty_expires_on: datetime | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class DeviceUpdate(StrictBody):
    expected_version: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1000)
    unit_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    location: str | None = Field(default=None, min_length=1, max_length=255)
    criticality: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] | None = None
    status: Literal["ACTIVE", "MAINTENANCE"] | None = None
    manufacturer: str | None = Field(default=None, max_length=128)
    model_no: str | None = Field(default=None, max_length=128)
    serial_no: str | None = Field(default=None, max_length=128)
    properties: dict[str, Any] | None = None


class ExpectedReason(StrictBody):
    expected_version: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1000)


class InspectionTemplateItemBody(StrictBody):
    item_code: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=255)
    result_type: Literal["BOOLEAN", "NUMBER", "TEXT", "SELECT"]
    required: bool = True
    critical: bool = False
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    options: list[str] = Field(default_factory=list, max_length=30)


class InspectionTemplateCreate(StrictBody):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    device_type: Literal[
        "FIRE", "ELEVATOR", "TRANSFORMER", "ELECTRICAL", "HVAC", "WATER", "SECURITY", "CUSTOM"
    ] | None = None
    description: str | None = Field(default=None, max_length=1000)
    items: list[InspectionTemplateItemBody] = Field(min_length=1, max_length=100)


class InspectionTemplateVersionCreate(StrictBody):
    description: str | None = Field(default=None, max_length=1000)
    items: list[InspectionTemplateItemBody] = Field(min_length=1, max_length=100)


class ExpectedVersion(StrictBody):
    expected_version: int = Field(gt=0)


class InspectionScheduleCreate(StrictBody):
    park_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    device_id: int = Field(gt=0)
    template_version_id: int = Field(gt=0)
    assignee_user_id: int = Field(gt=0)
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=64)
    weekday: int = Field(ge=1, le=7)
    local_due_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    completion_window_minutes: int = Field(default=1440, gt=0, le=10080)
    missed_work_order: bool = False


class SweepRequest(StrictBody):
    as_of: datetime | None = None


class InspectionReassign(ExpectedReason):
    assignee_user_id: int = Field(gt=0)


class InspectionResultBody(StrictBody):
    item_code: str = Field(min_length=1, max_length=64)
    value: bool | Decimal | str
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    remark: str | None = Field(default=None, max_length=1000)


class InspectionSubmit(ExpectedVersion):
    results: list[InspectionResultBody] = Field(min_length=1, max_length=100)


class ReasonBody(StrictBody):
    reason: str = Field(min_length=1, max_length=1000)


class IoTProviderCreate(StrictBody):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    adapter_kind: Literal["LOCAL", "SANDBOX", "HTTP"] = "SANDBOX"
    environment: str = Field(default="LOCAL", min_length=1, max_length=16)
    credential_ref: str | None = Field(default=None, max_length=128)
    severity_mapping: dict[str, Literal["INFO", "WARNING", "HIGH", "CRITICAL"]] = Field(
        default_factory=dict
    )
    correlation_minutes: int = Field(default=30, gt=0, le=10080)


class IoTBindingCreate(StrictBody):
    provider_id: int = Field(gt=0)
    device_id: int = Field(gt=0)
    external_device_key: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=1000)


class IoTAlarmIngest(StrictBody):
    provider_id: int = Field(gt=0)
    external_device_key: str = Field(min_length=1, max_length=128)
    source_event_id: str = Field(min_length=1, max_length=128)
    source_time: datetime
    alarm_type: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    severity: str = Field(min_length=1, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)


class AlarmTransition(ExpectedVersion):
    reason: str | None = Field(default=None, max_length=1000)

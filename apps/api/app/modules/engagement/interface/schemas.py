"""Strict engagement request contracts."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ApprovalSubmit(StrictModel):
    expected_version: int = Field(ge=1)
    definition_code: str = Field(min_length=2, max_length=48)
    priority: Literal["LOW", "MEDIUM", "HIGH", "URGENT"] = "MEDIUM"


class ExpectedVersion(StrictModel):
    expected_version: int = Field(ge=1)


class LifecycleAction(ExpectedVersion):
    reason: str = Field(min_length=1, max_length=1000)


class PolicyExpirySweep(StrictModel):
    due_on: date
    limit: int = Field(default=200, ge=1, le=1000)


class OperationalSweep(StrictModel):
    due_at: datetime
    limit: int = Field(default=200, ge=1, le=1000)


class ApplicabilityRule(StrictModel):
    field: Literal[
        "park_id",
        "region_code",
        "party_role",
        "industry_code",
        "enterprise_scale",
        "tag_code",
    ]
    operator: Literal["EQ", "IN", "CONTAINS_ANY"]
    values: list[str] = Field(min_length=1, max_length=64)


class PolicyCreate(StrictModel):
    park_id: int | None = Field(default=None, ge=1)
    code: str = Field(min_length=2, max_length=48)
    title: str = Field(min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=1000)
    content_text: str = Field(min_length=1, max_length=50000)
    category: str = Field(min_length=2, max_length=48)
    region_code: str | None = Field(default=None, max_length=32)
    source_type: Literal["LOCAL", "LEGACY", "EXTERNAL"]
    source_system: str | None = Field(default=None, max_length=64)
    source_identifier: str | None = Field(default=None, max_length=128)
    source_publisher: str = Field(min_length=1, max_length=255)
    source_url: str | None = Field(default=None, max_length=1000)
    allowed_hosts: list[str] = Field(default_factory=list, max_length=32)
    source_published_at: datetime | None = None
    effective_on: date | None = None
    expires_on: date | None = None
    attachment_ids: list[int] = Field(default_factory=list, max_length=32)
    applicability: list[ApplicabilityRule] = Field(default_factory=list, max_length=32)


class PolicyRevision(PolicyCreate):
    expected_version: int = Field(ge=1)


class PolicyConsultationCreate(StrictModel):
    park_id: int | None = Field(default=None, ge=1)
    subject: str = Field(min_length=1, max_length=255)
    question: str = Field(min_length=1, max_length=5000)


class ServiceCreate(StrictModel):
    park_id: int = Field(ge=1)
    code: str = Field(min_length=2, max_length=48)
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=50000)
    category: str = Field(min_length=2, max_length=48)
    provider_type: Literal["INTERNAL", "EXTERNAL"]
    provider_name: str = Field(min_length=1, max_length=255)
    provider_state: Literal["LOCAL", "NOT_CONNECTED"]
    sla_hours: int = Field(ge=1, le=8760)
    appointment_required: bool = False
    eligibility: list[ApplicabilityRule] = Field(default_factory=list, max_length=32)
    evidence_rules: list[dict[str, str]] = Field(default_factory=list, max_length=32)
    price_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    currency: str = Field(default="CNY", pattern=r"^[A-Z]{3}$")


class ServiceRevision(ServiceCreate):
    expected_version: int = Field(ge=1)


class ServiceCaseCreate(StrictModel):
    catalog_id: int = Field(ge=1)
    priority: Literal["LOW", "MEDIUM", "HIGH", "URGENT"] = "MEDIUM"
    subject: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=10000)
    contact_last4: str | None = Field(default=None, pattern=r"^[0-9]{4}$")


class StaffServiceCaseCreate(ServiceCaseCreate):
    party_id: int = Field(ge=1)


class ServiceCaseTransition(StrictModel):
    expected_version: int = Field(ge=1)
    target_status: Literal[
        "ACCEPTED",
        "ASSIGNED",
        "APPOINTED",
        "IN_PROGRESS",
        "RESULT_READY",
        "DISPUTED",
        "CONFIRMED",
        "CANCELLED",
    ]
    assigned_to: int | None = Field(default=None, ge=1)
    appointment_at: datetime | None = None
    result_summary: str | None = Field(default=None, max_length=10000)
    work_order_id: int | None = Field(default=None, ge=1)
    note: str | None = Field(default=None, max_length=1000)
    evidence: list[dict[str, str]] | None = Field(default=None, max_length=32)


class FeedbackCreate(StrictModel):
    score: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ActivityCreate(StrictModel):
    park_id: int = Field(ge=1)
    code: str = Field(min_length=2, max_length=48)
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=50000)
    location: str = Field(min_length=1, max_length=255)
    starts_at: datetime
    ends_at: datetime
    registration_opens_at: datetime
    registration_closes_at: datetime
    capacity: int = Field(ge=1, le=100000)
    attendee_rules: list[ApplicabilityRule] = Field(default_factory=list, max_length=32)
    audience: list[ApplicabilityRule] = Field(default_factory=list, max_length=32)
    attachment_ids: list[int] = Field(default_factory=list, max_length=32)
    cancellation_terms: str = Field(min_length=1, max_length=1000)


class ActivityRevision(ActivityCreate):
    expected_version: int = Field(ge=1)


class RegistrationCreate(StrictModel):
    attendee_count: int = Field(default=1, ge=1, le=100)


class RegistrationCancel(StrictModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


class CheckIn(StrictModel):
    expected_version: int = Field(ge=1)
    evidence_note: str = Field(min_length=1, max_length=1000)


class ActivityLifecycle(LifecycleAction):
    target_status: Literal[
        "REGISTRATION_CLOSED", "IN_PROGRESS", "COMPLETED", "CANCELLED"
    ]


class AudienceRule(StrictModel):
    type: Literal["USER", "ROLE", "PARTY", "PARK", "TENANT_PRINCIPAL"]
    ids: list[int] = Field(default_factory=list, max_length=1000)
    codes: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("ids")
    @classmethod
    def positive_ids(cls, values: list[int]) -> list[int]:
        if any(value <= 0 for value in values):
            raise ValueError("ids must be positive")
        return values


class AnnouncementCreate(StrictModel):
    park_id: int | None = Field(default=None, ge=1)
    code: str = Field(min_length=2, max_length=48)
    title: str = Field(min_length=1, max_length=255)
    content_text: str = Field(min_length=1, max_length=50000)
    priority: Literal["NORMAL", "IMPORTANT", "URGENT"] = "NORMAL"
    pin_from: datetime | None = None
    pin_to: datetime | None = None
    publish_at: datetime | None = None
    expires_at: datetime | None = None
    attachment_ids: list[int] = Field(default_factory=list, max_length=32)
    audience: list[AudienceRule] = Field(min_length=1, max_length=32)


class AnnouncementRevision(AnnouncementCreate):
    expected_version: int = Field(ge=1)


class FanoutRequest(StrictModel):
    limit: int = Field(default=200, ge=1, le=1000)

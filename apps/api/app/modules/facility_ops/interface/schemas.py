from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkOrderCreate(StrictBody):
    park_id: int = Field(gt=0)
    party_id: int | None = Field(default=None, gt=0)
    contact_id: int | None = Field(default=None, gt=0)
    contact_name: str | None = Field(default=None, max_length=64)
    contact_phone: str | None = Field(default=None, max_length=32)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    category: str = Field(default="GENERAL", min_length=1, max_length=64)
    priority: Literal["LOW", "MEDIUM", "HIGH", "URGENT"] = "MEDIUM"
    unit_id: int | None = Field(default=None, gt=0)
    quote_required: bool = False
    request_source: Literal["PROPERTY_STAFF", "PHONE", "FRONT_DESK", "OTHER"] = (
        "PROPERTY_STAFF"
    )


class TenantServiceRequestCreate(StrictBody):
    park_id: int = Field(gt=0)
    contact_id: int | None = Field(default=None, gt=0)
    contact_name: str | None = Field(default=None, max_length=64)
    contact_phone: str | None = Field(default=None, max_length=32)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    category: str = Field(default="GENERAL", min_length=1, max_length=64)
    priority: Literal["LOW", "MEDIUM", "HIGH", "URGENT"] = "MEDIUM"
    unit_id: int | None = Field(default=None, gt=0)
    quote_required: bool = False


class TenantServicePrincipalGrant(StrictBody):
    user_id: int = Field(gt=0)
    party_id: int = Field(gt=0)
    park_ids: list[int] = Field(min_length=1, max_length=100)


class AssignmentRuleCreate(StrictBody):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$")
    name: str = Field(min_length=1, max_length=128)
    park_id: int | None = Field(default=None, gt=0)
    category: str | None = Field(default=None, max_length=64)
    priority: Literal["LOW", "MEDIUM", "HIGH", "URGENT"] | None = None
    assignee_user_id: int = Field(gt=0)
    response_minutes: int = Field(gt=0, le=60 * 24 * 30)
    resolution_minutes: int = Field(gt=0, le=60 * 24 * 365)
    sort_order: int = Field(default=100, ge=0, le=100000)


class AssignmentRuleRetire(StrictBody):
    reason: str = Field(min_length=1, max_length=1000)


class ExpectedVersion(StrictBody):
    expected_version: int = Field(gt=0)


class DispatchRequest(ExpectedVersion):
    assignee_user_id: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1000)


class CancelRequest(ExpectedVersion):
    reason: str = Field(min_length=1, max_length=1000)


class QuoteLine(StrictBody):
    line_type: Literal["LABOR", "MATERIAL", "OUTSOURCE", "OTHER"]
    description: str = Field(min_length=1, max_length=255)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=4)
    unit: str = Field(min_length=1, max_length=32)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)


class QuoteCreate(ExpectedVersion):
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    total_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    remark: str | None = Field(default=None, max_length=1000)
    lines: list[QuoteLine] = Field(min_length=1, max_length=100)


class QuoteDecision(ExpectedVersion):
    decision: Literal["ACCEPT", "REJECT"]
    remark: str | None = Field(default=None, max_length=1000)


class CostCreate(ExpectedVersion):
    entry_type: Literal["LABOR", "MATERIAL", "OUTSOURCE", "OTHER"]
    description: str = Field(min_length=1, max_length=255)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=4)
    unit: str = Field(min_length=1, max_length=32)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class CostReverse(ExpectedVersion):
    reason: str = Field(min_length=1, max_length=1000)


class CompletionSubmit(ExpectedVersion):
    resolution_summary: str = Field(min_length=1, max_length=2000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    no_evidence_reason: str | None = Field(default=None, max_length=512)


class AcceptanceDecision(ExpectedVersion):
    decision: Literal["ACCEPTED", "REWORK"]
    comment: str | None = Field(default=None, max_length=1000)


class RatingCreate(StrictBody):
    score: int = Field(ge=1, le=5)
    tags: list[str] = Field(default_factory=list, max_length=10)
    comment: str | None = Field(default=None, max_length=1000)


class SlaSweepRequest(StrictBody):
    as_of: datetime | None = None

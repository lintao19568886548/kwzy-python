"""功能说明：Lead 请求体。"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LeadCreate(BaseModel):
    park_id: int
    name: str = Field(..., min_length=1, max_length=128)
    contact_phone: str = Field(..., min_length=5, max_length=32)
    contact_name: Optional[str] = None
    agent_name: Optional[str] = None
    intent_level: Optional[str] = None
    intent_area: Optional[Any] = None
    desired_usage: Optional[str] = None
    budget_unit_price: Optional[Any] = None
    remark: Optional[str] = None
    owner_user_id: Optional[int] = None
    pool_status: str = "PRIVATE"
    source_type: str = "MANUAL"
    source_ref: Optional[str] = None
    duplicate_override_reason: Optional[str] = None
    next_follow_up_at: Optional[str] = None
    auto_assign: bool = True


class LeadUpdate(BaseModel):
    expected_version: int = Field(..., ge=1)
    name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_name: Optional[str] = None
    agent_name: Optional[str] = None
    intent_level: Optional[str] = None
    intent_area: Optional[Any] = None
    desired_usage: Optional[str] = None
    budget_unit_price: Optional[Any] = None
    remark: Optional[str] = None
    status: Optional[str] = None
    stage_reason: Optional[str] = None


class LeadLoseBody(BaseModel):
    expected_version: int = Field(..., ge=1)
    reason: str = Field(..., min_length=1, max_length=255)


class LeadConvertBody(BaseModel):
    expected_version: int = Field(..., ge=1)
    unit_ids: list[int] = Field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    party_type: str = "ORGANIZATION"
    occupied_area: Optional[Any] = None
    unit_rent_price: Optional[Any] = None
    deposit_amount: Optional[Any] = None


class LeadDuplicateQuery(BaseModel):
    park_id: int
    name: str = Field(..., min_length=1, max_length=128)
    contact_phone: str = Field(..., min_length=5, max_length=32)
    source_type: str = "MANUAL"
    source_ref: Optional[str] = None


class LeadActivityCreate(BaseModel):
    expected_version: int = Field(..., ge=1)
    activity_type: str
    content: str = Field(..., min_length=1)
    next_follow_up_at: Optional[str] = None
    stage_to: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class LeadAssignBody(BaseModel):
    expected_version: int = Field(..., ge=1)
    owner_user_id: int
    reason: Optional[str] = None


class LeadVersionBody(BaseModel):
    expected_version: int = Field(..., ge=1)
    reason: Optional[str] = None


class LeadReopenBody(BaseModel):
    expected_version: int = Field(..., ge=1)
    reason: str = Field(..., min_length=1, max_length=255)
    target_status: str = "CONTACTING"


class LeadMergeBody(BaseModel):
    expected_version: int = Field(..., ge=1)
    target_lead_id: int
    target_expected_version: int = Field(..., ge=1)
    reason: str = Field(..., min_length=1, max_length=255)


class LeadUnitLockCreate(BaseModel):
    expected_version: int = Field(..., ge=1)
    unit_id: int
    intent_id: int
    duration_hours: int = Field(48, ge=1, le=168)


class LeadUnitLockCommand(BaseModel):
    expected_version: int = Field(..., ge=1)
    duration_hours: int = Field(48, ge=1, le=168)
    intent_id: Optional[int] = None


class AssignmentMemberIn(StrictBody):
    user_id: int = Field(..., ge=1)
    capacity: int = Field(..., ge=1, le=10000)
    weight: int = Field(1, ge=1, le=100)
    member_order: int = Field(..., ge=1)


class AssignmentRuleCreate(StrictBody):
    park_id: int = Field(..., ge=1)
    code: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    trigger: str
    description: Optional[str] = Field(None, max_length=2000)
    recycle_after_hours: int = Field(72, ge=1, le=8760)
    members: list[AssignmentMemberIn] = Field(..., min_length=1, max_length=100)


class AssignmentRuleDraftUpdate(StrictBody):
    expected_lock_version: int = Field(..., ge=0)
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = Field(None, max_length=2000)
    recycle_after_hours: Optional[int] = Field(None, ge=1, le=8760)
    members: Optional[list[AssignmentMemberIn]] = Field(None, min_length=1, max_length=100)


class ExpectedLockVersion(StrictBody):
    expected_lock_version: int = Field(..., ge=0)


class ViewingCreate(StrictBody):
    starts_at: str
    ends_at: str
    unit_ids: list[int] = Field(..., min_length=1, max_length=20)
    owner_user_id: Optional[int] = Field(None, ge=1)
    visitor_name: Optional[str] = Field(None, max_length=64)
    visitor_count: int = Field(1, ge=1, le=100)
    notes: Optional[str] = Field(None, max_length=2000)


class ViewingReschedule(StrictBody):
    expected_version: int = Field(..., ge=1)
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    unit_ids: Optional[list[int]] = Field(None, min_length=1, max_length=20)
    owner_user_id: Optional[int] = Field(None, ge=1)
    visitor_name: Optional[str] = Field(None, max_length=64)
    visitor_count: Optional[int] = Field(None, ge=1, le=100)
    notes: Optional[str] = Field(None, max_length=2000)


class ViewingTransition(StrictBody):
    expected_version: int = Field(..., ge=1)
    status: str
    outcome: Optional[str] = Field(None, max_length=1000)
    next_follow_up_at: Optional[str] = None
    reason: Optional[str] = Field(None, max_length=255)
    idempotency_key: Optional[str] = Field(None, min_length=8, max_length=64)


class IntentUnitIn(StrictBody):
    unit_id: int = Field(..., ge=1)
    requested_area: Any


class IntentCreate(StrictBody):
    starts_on: str
    ends_on: str
    valid_until: str
    proposed_unit_price: Any
    currency: str = Field("CNY", min_length=3, max_length=3)
    remark: Optional[str] = Field(None, max_length=2000)
    units: list[IntentUnitIn] = Field(..., min_length=1, max_length=20)


class IntentVersionCreate(IntentCreate):
    expected_version: int = Field(..., ge=1)


class IntentSubmit(StrictBody):
    expected_version: int = Field(..., ge=1)
    definition_code: str = Field(..., min_length=1, max_length=64)
    idempotency_key: str = Field(..., min_length=8, max_length=64)
    priority: str = "HIGH"
    remark: Optional[str] = Field(None, max_length=2000)


class ChannelCreate(StrictBody):
    park_id: int = Field(..., ge=1)
    code: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    secret_env_key: str = Field(..., min_length=3, max_length=128)
    previous_secret_env_key: Optional[str] = Field(None, max_length=128)
    enabled: bool = False
    max_clock_skew_seconds: int = Field(300, ge=30, le=900)
    allow_auto_assign: bool = True
    mapping: Optional[dict[str, str]] = None


class ChannelUpdate(StrictBody):
    expected_version: int = Field(..., ge=1)
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    secret_env_key: Optional[str] = Field(None, min_length=3, max_length=128)
    previous_secret_env_key: Optional[str] = Field(None, max_length=128)
    enabled: Optional[bool] = None
    max_clock_skew_seconds: Optional[int] = Field(None, ge=30, le=900)
    allow_auto_assign: Optional[bool] = None
    mapping: Optional[dict[str, str]] = None

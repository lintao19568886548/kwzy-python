"""功能说明：Lead 请求体。"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


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
    duration_hours: int = Field(48, ge=1, le=168)


class LeadUnitLockCommand(BaseModel):
    expected_version: int = Field(..., ge=1)
    duration_hours: int = Field(48, ge=1, le=168)

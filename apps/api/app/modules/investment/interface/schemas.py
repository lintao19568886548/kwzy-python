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
    remark: Optional[str] = None
    owner_user_id: Optional[int] = None


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_name: Optional[str] = None
    agent_name: Optional[str] = None
    intent_level: Optional[str] = None
    intent_area: Optional[Any] = None
    remark: Optional[str] = None
    owner_user_id: Optional[int] = None
    status: Optional[str] = None


class LeadLoseBody(BaseModel):
    reason: Optional[str] = None


class LeadConvertBody(BaseModel):
    unit_ids: list[int] = Field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    party_type: str = "ORGANIZATION"
    occupied_area: Optional[Any] = None
    unit_rent_price: Optional[Any] = None
    deposit_amount: Optional[Any] = None

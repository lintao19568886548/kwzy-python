"""功能说明：Payment 请求体。"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class AllocationIn(BaseModel):
    bill_id: int
    amount: Any


class PaymentCreate(BaseModel):
    park_id: int
    party_id: int
    amount: Any
    method: str = "TRANSFER"
    paid_at: str  # required per OpenAPI / design
    payment_no: Optional[str] = None
    remark: Optional[str] = None
    allocations: list[AllocationIn] = Field(default_factory=list)

"""功能说明：Bill 请求体。"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class BillLineIn(BaseModel):
    fee_code: str = "OTHER"
    description: str = ""
    quantity: Any = "0"
    unit_price: Any = "0"
    amount: Optional[Any] = None
    sort_order: int = 0


class BillCreate(BaseModel):
    park_id: int
    party_id: int
    period_start: str
    period_end: str
    contract_id: Optional[int] = None
    bill_no: Optional[str] = None
    title: Optional[str] = None
    due_date: Optional[str] = None
    remark: Optional[str] = None
    lines: list[BillLineIn] = Field(default_factory=list)


class BillUpdate(BaseModel):
    title: Optional[str] = None
    due_date: Optional[str] = None
    remark: Optional[str] = None
    lines: Optional[list[BillLineIn]] = None

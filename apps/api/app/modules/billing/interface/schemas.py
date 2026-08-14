"""功能说明：Bill 请求体。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BillLineIn(StrictBody):
    fee_code: str = "OTHER"
    description: str = ""
    quantity: Any = "0"
    unit_price: Any = "0"
    amount: Any | None = None
    sort_order: int = 0


class BillCreate(StrictBody):
    park_id: int
    party_id: int
    period_start: str
    period_end: str
    contract_id: int | None = None
    bill_no: str | None = None
    title: str | None = None
    due_date: str | None = None
    remark: str | None = None
    lines: list[BillLineIn] = Field(default_factory=list)


class BillUpdate(StrictBody):
    title: str | None = None
    due_date: str | None = None
    remark: str | None = None
    lines: list[BillLineIn] | None = None


class ScheduleBillingRun(StrictBody):
    as_of: str
    park_id: int | None = Field(default=None, gt=0)

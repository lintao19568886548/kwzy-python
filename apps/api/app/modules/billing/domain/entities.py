"""功能说明：Billing 领域实体。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


@dataclass
class BillEntity:
    """功能说明：账单聚合根。"""

    tenant_id: int
    park_id: int
    party_id: int
    bill_no: str
    period_start: date
    period_end: date
    status: str = "DRAFT"
    total_amount: Decimal = Decimal("0")
    paid_amount: Decimal = Decimal("0")
    currency: str = "CNY"
    source: str = "MANUAL"
    contract_id: Optional[int] = None
    title: Optional[str] = None
    project_name: Optional[str] = None
    due_date: Optional[date] = None
    overdue_since: Optional[date] = None
    source_ref: Optional[str] = None
    remark: Optional[str] = None
    issued_at: Optional[datetime] = None
    created_by: Optional[int] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class BillLineEntity:
    """功能说明：账单明细行。"""

    tenant_id: int
    bill_id: int
    fee_code: str
    description: str = ""
    quantity: Decimal = Decimal("0")
    unit_price: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")
    meter_reading_from: Optional[Decimal] = None
    meter_reading_to: Optional[Decimal] = None
    multiplier: Optional[Decimal] = None
    sort_order: int = 0
    id: Optional[int] = None

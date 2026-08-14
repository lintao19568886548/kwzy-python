"""功能说明：Billing 领域实体。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


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
    total_amount: Decimal = Decimal(0)
    paid_amount: Decimal = Decimal(0)
    waiver_amount: Decimal = Decimal(0)
    bad_debt_amount: Decimal = Decimal(0)
    currency: str = "CNY"
    source: str = "MANUAL"
    contract_id: int | None = None
    title: str | None = None
    project_name: str | None = None
    due_date: date | None = None
    overdue_since: date | None = None
    deferred_due_date: date | None = None
    collection_hold: bool = False
    dispute_status: str = "NONE"
    lock_version: int = 1
    source_ref: str | None = None
    remark: str | None = None
    issued_at: datetime | None = None
    created_by: int | None = None
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class BillLineEntity:
    """功能说明：账单明细行。"""

    tenant_id: int
    bill_id: int
    fee_code: str
    source_schedule_id: int | None = None
    description: str = ""
    quantity: Decimal = Decimal(0)
    unit_price: Decimal = Decimal(0)
    amount: Decimal = Decimal(0)
    meter_reading_from: Decimal | None = None
    meter_reading_to: Decimal | None = None
    multiplier: Decimal | None = None
    sort_order: int = 0
    id: int | None = None

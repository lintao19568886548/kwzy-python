"""功能说明：
    Lease 领域实体（无 SQLAlchemy / FastAPI）。

业务职责：
    Domain 层；合同、占用行、条款行数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


@dataclass
class LeaseContractEntity:
    """功能说明：
        租赁合同聚合根领域实体。

    业务职责：
        Domain 模型；合同带 park_id，不依赖 Party 主档 park_id。

    业务规则：
        1. tenant 隔离；contract_no 租户内唯一。
        2. deposit_amount 仅字段存储，无退还流水。
    """

    tenant_id: int
    park_id: int
    party_id: int
    contract_no: str
    start_date: date
    end_date: date
    status: str = "DRAFT"
    deposit_amount: Decimal = Decimal("0")
    increase_date: Optional[date] = None
    increase_rate: Optional[Decimal] = None
    remark: Optional[str] = None
    created_by: Optional[int] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class LeaseContractUnitEntity:
    """功能说明：
        合同占用单元行。

    业务职责：
        Domain 模型；unit + occupied_area + unit_rent_price。
    """

    tenant_id: int
    contract_id: int
    unit_id: int
    occupied_area: Decimal = Decimal("0")
    unit_rent_price: Decimal = Decimal("0")
    id: Optional[int] = None


@dataclass
class LeaseTermEntity:
    """功能说明：
        合同条款行（递增/免租/其他）。

    业务职责：
        Domain 模型；不驱动自动出账（Bill change）。
    """

    tenant_id: int
    contract_id: int
    term_type: str
    effective_date: Optional[date] = None
    end_date: Optional[date] = None
    rate: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    description: Optional[str] = None
    sort_order: int = 0
    id: Optional[int] = None
    created_at: Optional[datetime] = None

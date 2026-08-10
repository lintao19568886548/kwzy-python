"""功能说明：
    Lease HTTP 请求体 Schema。

业务职责：
    Interface 层入参校验。
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class LeaseUnitLine(BaseModel):
    """功能说明：合同占用单元行。"""

    unit_id: int
    occupied_area: Any = "0"
    unit_rent_price: Any = "0"


class LeaseTermLine(BaseModel):
    """功能说明：合同条款行。"""

    term_type: str = "OTHER"
    effective_date: Optional[str] = None
    end_date: Optional[str] = None
    rate: Optional[Any] = None
    amount: Optional[Any] = None
    description: Optional[str] = None
    sort_order: int = 0


class LeaseCreate(BaseModel):
    """功能说明：创建合同请求体。"""

    park_id: int
    party_id: int
    start_date: str
    end_date: str
    contract_no: Optional[str] = None
    deposit_amount: Any = "0"
    remark: Optional[str] = None
    units: list[LeaseUnitLine] = Field(default_factory=list)
    terms: list[LeaseTermLine] = Field(default_factory=list)


class LeaseUpdate(BaseModel):
    """功能说明：更新合同请求体。"""

    start_date: Optional[str] = None
    end_date: Optional[str] = None
    deposit_amount: Optional[Any] = None
    remark: Optional[str] = None
    units: Optional[list[LeaseUnitLine]] = None
    terms: Optional[list[LeaseTermLine]] = None

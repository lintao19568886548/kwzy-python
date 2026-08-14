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
    charges: Optional[list["LeaseChargeLine"]] = None


class LeaseUpdate(BaseModel):
    """功能说明：更新合同请求体。"""

    expected_version: int = Field(ge=1)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    deposit_amount: Optional[Any] = None
    remark: Optional[str] = None
    units: Optional[list[LeaseUnitLine]] = None
    terms: Optional[list[LeaseTermLine]] = None
    charges: Optional[list["LeaseChargeLine"]] = None


class LeaseChargeLine(BaseModel):
    charge_code: str = Field(min_length=1, max_length=64)
    charge_type: str = Field(min_length=1, max_length=32)
    calculation_method: str = Field(min_length=1, max_length=32)
    billing_cycle: str = Field(min_length=1, max_length=32)
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    start_date: str
    end_date: str
    due_day: int = Field(default=1, ge=1, le=31)
    amount: Optional[Any] = None
    unit_price: Optional[Any] = None
    tax_rate: Any = "0"
    rules: list[dict[str, Any]] = Field(default_factory=list)
    sort_order: int = 0


LeaseCreate.model_rebuild()
LeaseUpdate.model_rebuild()


class LeaseVersionCommand(BaseModel):
    expected_version: int = Field(ge=1)
    remark: Optional[str] = Field(default=None, max_length=1000)


class LeaseApprovalCommand(LeaseVersionCommand):
    approval_id: int = Field(gt=0)
    override_reason: Optional[str] = Field(default=None, max_length=1000)


class LeaseChargeReplace(BaseModel):
    expected_version: int = Field(ge=1)
    charges: list[LeaseChargeLine]


class LeaseSchedulePreview(BaseModel):
    expected_version: int = Field(ge=1)
    charges: Optional[list[LeaseChargeLine]] = None


class LeaseDocumentCreate(BaseModel):
    expected_version: int = Field(ge=1)
    attachment_id: int = Field(gt=0)
    document_type: str = Field(min_length=1, max_length=32)
    checksum: str = Field(min_length=64, max_length=64)
    is_main: bool = False
    exit_settlement_id: Optional[int] = Field(default=None, gt=0)


class LeaseDocumentCommand(BaseModel):
    expected_version: int = Field(ge=1)


class LeaseChangeCreate(BaseModel):
    expected_version: int = Field(ge=1)
    change_type: str = Field(min_length=1, max_length=32)
    effective_date: str
    reason: str = Field(min_length=1, max_length=2000)
    proposed_snapshot: dict[str, Any]
    target_party_eligible: Optional[bool] = None


class LeaseChangeEdit(LeaseChangeCreate):
    """Replace a DRAFT change proposal while preserving its identity."""


class LeaseApplyDue(BaseModel):
    as_of: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=200)


class LeaseChangeDecision(BaseModel):
    expected_version: int = Field(ge=1)
    remark: Optional[str] = Field(default=None, max_length=1000)
    override_reason: Optional[str] = Field(default=None, max_length=1000)


class LeaseChangeApply(BaseModel):
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=160)
    as_of: Optional[str] = None


class LeaseExitCreate(BaseModel):
    expected_version: int = Field(ge=1)
    handover_date: str
    inspection_summary: Optional[str] = Field(default=None, max_length=4000)


class LeaseExitItemLine(BaseModel):
    item_type: str = Field(min_length=1, max_length=32)
    amount: Any
    description: str = Field(min_length=1, max_length=255)
    approved: bool = True
    evidence_attachment_id: Optional[int] = Field(default=None, gt=0)
    source_type: Optional[str] = Field(default=None, max_length=32)
    source_ref: Optional[str] = Field(default=None, max_length=128)
    sort_order: int = 0


class LeaseExitEdit(BaseModel):
    expected_version: int = Field(ge=1)
    inspection_summary: Optional[str] = Field(default=None, max_length=4000)
    meter_readings: list[dict[str, Any]] = Field(default_factory=list)
    items: list[LeaseExitItemLine] = Field(default_factory=list)


class LeaseExitSubmit(BaseModel):
    expected_version: int = Field(ge=1)
    contract_expected_version: int = Field(ge=1)
    remark: Optional[str] = Field(default=None, max_length=1000)


class LeaseExitWithdraw(LeaseExitSubmit):
    """Applicant withdrawal requires both settlement and contract versions."""


class LeaseExitDecision(BaseModel):
    expected_version: int = Field(ge=1)
    remark: Optional[str] = Field(default=None, max_length=1000)
    override_reason: Optional[str] = Field(default=None, max_length=1000)


class LeaseExitClearance(BaseModel):
    expected_version: int = Field(ge=1)
    evidence_attachment_id: int = Field(gt=0)
    reference: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=2000)


class LeaseExitClose(BaseModel):
    expected_version: int = Field(ge=1)
    contract_expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=160)
    breached: bool = False

"""功能说明：Payment 请求体。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AllocationIn(StrictBody):
    bill_id: int = Field(gt=0)
    amount: Any


class PaymentCreate(StrictBody):
    park_id: int = Field(gt=0)
    party_id: int = Field(gt=0)
    amount: Any
    method: str = "TRANSFER"
    paid_at: str  # required per OpenAPI / design
    payment_no: str | None = None
    remark: str | None = None
    allocations: list[AllocationIn] = Field(default_factory=list)


class PaymentAllocate(StrictBody):
    allocations: list[AllocationIn] = Field(min_length=1, max_length=200)


class ReceiptCreate(StrictBody):
    park_id: int = Field(gt=0)
    party_id: int | None = Field(default=None, gt=0)
    amount: Any
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    received_at: str
    channel: Literal[
        "BANK_IMPORT",
        "BANK_API",
        "OFFLINE_TRANSFER",
        "PAYMENT_LINK",
        "WECHAT",
        "ALIPAY",
        "AGGREGATE",
        "CASH",
        "POS",
    ]
    source_provider: str = Field(default="MANUAL", min_length=1, max_length=64)
    source_ref: str = Field(min_length=1, max_length=128)
    payer_name: str | None = Field(default=None, max_length=128)
    payer_account: str | None = Field(default=None, max_length=128)
    bank_reference: str | None = Field(default=None, max_length=128)
    purpose: str | None = Field(default=None, max_length=512)


class ReceiptImport(StrictBody):
    rows: list[ReceiptCreate] = Field(min_length=1, max_length=500)


class VersionCommand(StrictBody):
    expected_version: int = Field(ge=1)


class ReceiptConfirm(VersionCommand):
    party_id: int | None = Field(default=None, gt=0)
    allocations: list[AllocationIn] | None = Field(default=None, max_length=200)
    remark: str | None = Field(default=None, max_length=1000)


class ReceiptException(VersionCommand):
    code: str = Field(min_length=1, max_length=64)
    remark: str = Field(min_length=1, max_length=1000)


class ReceiptDispute(VersionCommand):
    reason: str = Field(min_length=1, max_length=1000)


class ReceiptDisputeDecision(VersionCommand):
    decision: Literal["RETURN_TO_FINANCE", "REJECT_RECEIPT"]
    remark: str = Field(min_length=1, max_length=1000)


class DunningRun(StrictBody):
    as_of: str
    park_id: int | None = Field(default=None, gt=0)


class CollectionRecordCreate(StrictBody):
    action_type: Literal["CALL", "VISIT", "SMS", "WECHAT", "EMAIL", "NOTICE", "NOTE"]
    channel: str | None = Field(default=None, max_length=24)
    note: str | None = Field(default=None, max_length=2000)
    source_ref: str | None = Field(default=None, max_length=128)
    next_follow_up_at: str | None = None


class ReceivableAdjustmentCreate(StrictBody):
    bill_id: int = Field(gt=0)
    adjustment_type: Literal["WAIVER", "EXTENSION", "BAD_DEBT", "DISPUTE", "DISPUTE_RESOLUTION"]
    amount: Any | None = None
    requested_due_date: str | None = None
    reason: str = Field(min_length=1, max_length=1000)

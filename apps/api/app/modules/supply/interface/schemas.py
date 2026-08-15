"""Strict supply request contracts."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SupplierCreate(StrictModel):
    party_id: int = Field(gt=0)
    code: str = Field(min_length=2, max_length=32)
    display_name: str | None = Field(default=None, max_length=128)


class SupplierStatus(StrictModel):
    status: Literal["ACTIVE", "SUSPENDED", "RETIRED"]
    expected_version: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=500)


class SupplierScopeCreate(StrictModel):
    park_id: int = Field(gt=0)
    service_type: str = Field(default="GENERAL", min_length=2, max_length=32)


class SupplierQualificationCreate(StrictModel):
    qualification_type: str = Field(min_length=2, max_length=32)
    credential_number: str = Field(
        min_length=1,
        max_length=128,
        json_schema_extra={"writeOnly": True},
    )
    issuer: str = Field(min_length=1, max_length=128)
    effective_on: date
    expires_on: date | None = None
    attachment_id: int | None = Field(default=None, gt=0)


class SupplierEvaluationCreate(StrictModel):
    park_id: int = Field(gt=0)
    source_type: str = Field(min_length=2, max_length=32)
    source_id: int = Field(gt=0)
    score: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class MaterialCreate(StrictModel):
    code: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    category: str = Field(min_length=1, max_length=64)
    unit: str = Field(min_length=1, max_length=16)
    reorder_point: Decimal = Field(default=Decimal(0), ge=0, max_digits=18, decimal_places=4)


class WarehouseCreate(StrictModel):
    park_id: int = Field(gt=0)
    code: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=1, max_length=128)


class ProcurementLineCreate(StrictModel):
    material_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    estimated_unit_price: Decimal = Field(default=Decimal(0), ge=0, max_digits=18, decimal_places=4)
    purpose: str | None = Field(default=None, max_length=255)


class ProcurementCreate(StrictModel):
    park_id: int = Field(gt=0)
    purpose: str = Field(min_length=1, max_length=500)
    lines: list[ProcurementLineCreate] = Field(min_length=1, max_length=100)

    @field_validator("lines")
    @classmethod
    def unique_materials(cls, value: list[ProcurementLineCreate]) -> list[ProcurementLineCreate]:
        if len({line.material_id for line in value}) != len(value):
            raise ValueError("material_id must be unique")
        return value


class ProcurementDraftUpdate(ProcurementCreate):
    expected_version: int = Field(gt=0)


class ApprovalSubmit(StrictModel):
    expected_version: int = Field(gt=0)
    definition_code: str = Field(min_length=2, max_length=64)
    priority: Literal["LOW", "MEDIUM", "HIGH", "URGENT"] = "MEDIUM"


class SupplyExpectedReason(StrictModel):
    expected_version: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=500)


class PurchaseOrderPrice(StrictModel):
    requisition_line_id: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=4)


class PurchaseOrderCreate(StrictModel):
    requisition_id: int = Field(gt=0)
    supplier_id: int = Field(gt=0)
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    truth_mode: Literal["LOCAL", "EXTERNAL_PENDING"] = "LOCAL"
    required_qualification: str | None = Field(default=None, max_length=32)
    lines: list[PurchaseOrderPrice] = Field(min_length=1, max_length=100)


class PurchaseOrderAcknowledge(StrictModel):
    expected_version: int = Field(gt=0)
    accepted: bool
    reason: str | None = Field(default=None, max_length=500)


class ReceiptLineCreate(StrictModel):
    order_line_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    batch_no: str | None = Field(default=None, max_length=64)


class ReceiptCreate(StrictModel):
    warehouse_id: int = Field(gt=0)
    lines: list[ReceiptLineCreate] = Field(min_length=1, max_length=100)

    @field_validator("lines")
    @classmethod
    def unique_lines(cls, value: list[ReceiptLineCreate]) -> list[ReceiptLineCreate]:
        if len({line.order_line_id for line in value}) != len(value):
            raise ValueError("order_line_id must be unique")
        return value


class InventoryLineCreate(StrictModel):
    warehouse_id: int = Field(gt=0)
    material_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)


class InventoryRequisitionCreate(StrictModel):
    park_id: int = Field(gt=0)
    purpose: str = Field(min_length=1, max_length=500)
    work_order_id: int | None = Field(default=None, gt=0)
    lines: list[InventoryLineCreate] = Field(min_length=1, max_length=100)


class InventoryIssueLine(StrictModel):
    line_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)


class InventoryIssue(StrictModel):
    lines: list[InventoryIssueLine] = Field(min_length=1, max_length=100)

    @field_validator("lines")
    @classmethod
    def unique_lines(cls, value: list[InventoryIssueLine]) -> list[InventoryIssueLine]:
        if len({line.line_id for line in value}) != len(value):
            raise ValueError("line_id must be unique")
        return value


class InventoryReturn(StrictModel):
    line_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)


class StocktakeCount(StrictModel):
    material_id: int = Field(gt=0)
    counted_qty: Decimal = Field(ge=0, max_digits=18, decimal_places=4)


class StocktakeCreate(StrictModel):
    warehouse_id: int = Field(gt=0)
    lines: list[StocktakeCount] = Field(min_length=1, max_length=500)


class MovementReverse(StrictModel):
    reason: str = Field(min_length=1, max_length=500)


class DeliverableCreate(StrictModel):
    code: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    required: bool = True


class OutsourcingCreate(StrictModel):
    park_id: int = Field(gt=0)
    supplier_id: int = Field(gt=0)
    work_order_id: int | None = Field(default=None, gt=0)
    title: str = Field(min_length=1, max_length=200)
    deliverables: list[DeliverableCreate] = Field(min_length=1, max_length=100)
    sla_due_at: datetime
    amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    required_qualification: str | None = Field(default=None, max_length=32)


class OutsourcingSubmit(ApprovalSubmit):
    required_qualification: str | None = Field(default=None, max_length=32)


class EvidenceItem(StrictModel):
    type: str = Field(min_length=1, max_length=32)
    reference: str = Field(min_length=1, max_length=255)


class OutsourcingEventCreate(StrictModel):
    event_type: Literal["STARTED", "PROGRESS", "COMPLETED", "CANCELLED"]
    note: str | None = Field(default=None, max_length=2000)
    evidence: list[EvidenceItem] | None = Field(default=None, max_length=100)


class OutsourcingAcceptance(StrictModel):
    accepted: bool
    reason: str | None = Field(default=None, max_length=1000)
    score: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)

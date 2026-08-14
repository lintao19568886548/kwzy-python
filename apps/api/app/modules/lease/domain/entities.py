"""Lease contract lifecycle domain entities.

These dataclasses intentionally contain no FastAPI or SQLAlchemy dependencies.
They model the aggregate root, immutable versions, pricing projections, governed
changes, documents and exit settlement facts used by the application layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional


@dataclass
class LeaseContractEntity:
    """Stable lease aggregate root and its mutable current projection."""

    tenant_id: int
    park_id: int
    party_id: int
    contract_no: str
    start_date: date
    end_date: date
    status: str = "DRAFT"
    contract_type: str = "LEASE"
    currency: str = "CNY"
    approval_status: Optional[str] = None
    signed_at: Optional[datetime] = None
    effective_at: Optional[datetime] = None
    terminated_at: Optional[datetime] = None
    current_version_no: int = 0
    lock_version: int = 1
    source_system: Optional[str] = None
    source_ref: Optional[str] = None
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
    """Current Unit occupancy projection for a contract."""

    tenant_id: int
    contract_id: int
    unit_id: int
    occupied_area: Decimal = Decimal("0")
    unit_rent_price: Decimal = Decimal("0")
    id: Optional[int] = None


@dataclass
class LeaseTermEntity:
    """Legacy compatibility term; it is not an authoritative V2 charge."""

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


@dataclass(frozen=True)
class LeaseContractVersionEntity:
    """Append-only canonical contract evidence."""

    tenant_id: int
    contract_id: int
    version_no: int
    schema_version: int
    snapshot: dict[str, Any]
    checksum: str
    effective_at: Optional[datetime]
    reason: str
    created_by: Optional[int] = None
    change_order_id: Optional[int] = None
    exit_settlement_id: Optional[int] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None


@dataclass
class LeaseChargeItemEntity:
    """Structured current pricing input."""

    tenant_id: int
    contract_id: int
    charge_code: str
    charge_type: str
    calculation_method: str
    billing_cycle: str
    currency: str
    start_date: date
    end_date: date
    due_day: int = 1
    amount: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    tax_rate: Decimal = Decimal("0")
    sort_order: int = 0
    rule_config: dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None


@dataclass(frozen=True)
class LeasePerformanceScheduleEntity:
    """Version-bound, read-only upstream obligation for Billing."""

    tenant_id: int
    contract_id: int
    contract_version_no: int
    charge_item_id: Optional[int]
    charge_code: str
    schedule_key: str
    period_start: date
    period_end: date
    due_date: date
    currency: str
    area: Decimal
    unit_price: Optional[Decimal]
    net_amount: Decimal
    tax_amount: Decimal
    gross_amount: Decimal
    status: str = "PLANNED"
    rule_refs: tuple[str, ...] = ()
    id: Optional[int] = None


@dataclass
class LeaseChangeOrderEntity:
    """Governed proposal against one immutable base version."""

    tenant_id: int
    contract_id: int
    change_no: str
    change_type: str
    reason: str
    effective_date: date
    base_version_no: int
    proposed_snapshot: dict[str, Any]
    status: str = "DRAFT"
    schema_version: int = 1
    lock_version: int = 1
    approval_request_id: Optional[int] = None
    applied_version_no: Optional[int] = None
    idempotency_key: Optional[str] = None
    created_by: Optional[int] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass(frozen=True)
class LeaseContractDocumentEntity:
    """Append-only attachment metadata and signature-readiness fact."""

    tenant_id: int
    contract_id: int
    attachment_id: int
    document_type: str
    document_version: int
    status: str
    checksum: str
    is_main: bool = False
    contract_version_no: Optional[int] = None
    change_order_id: Optional[int] = None
    exit_settlement_id: Optional[int] = None
    signature_provider: Optional[str] = None
    signature_ref: Optional[str] = None
    signed_at: Optional[datetime] = None
    live_verified: bool = False
    created_by: Optional[int] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None


@dataclass
class LeaseExitItemEntity:
    """A non-negative settlement calculation input."""

    item_type: str
    amount: Decimal
    description: str
    evidence_ref: Optional[str] = None
    approved: bool = True
    sort_order: int = 0
    tenant_id: Optional[int] = None
    settlement_id: Optional[int] = None
    evidence_attachment_id: Optional[int] = None
    source_type: Optional[str] = None
    source_ref: Optional[str] = None
    id: Optional[int] = None


@dataclass
class LeaseExitSettlementEntity:
    """Exit handover, external financial facts and deterministic totals."""

    tenant_id: int
    contract_id: int
    settlement_no: str
    contract_version_no: int
    planned_handover_date: Optional[date]
    held_deposit_amount: Decimal
    outstanding_amount: Decimal
    change_order_id: Optional[int] = None
    outstanding_source: str = "BILLING_SCOPED_READ"
    outstanding_as_of: Optional[datetime] = None
    status: str = "DRAFT"
    lock_version: int = 1
    inspection_summary: Optional[str] = None
    meter_readings: list[dict[str, Any]] = field(default_factory=list)
    items: list[LeaseExitItemEntity] = field(default_factory=list)
    receivable_total: Decimal = Decimal("0")
    deduction_total: Decimal = Decimal("0")
    refund_adjustment_total: Decimal = Decimal("0")
    net_due_from_party: Decimal = Decimal("0")
    net_due_to_party: Decimal = Decimal("0")
    calculation_checksum: Optional[str] = None
    financial_clearance_status: str = "NOT_REQUIRED"
    financial_clearance_ref: Optional[str] = None
    financial_clearance_reason: Optional[str] = None
    approval_request_id: Optional[int] = None
    idempotency_key: Optional[str] = None
    created_by: Optional[int] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

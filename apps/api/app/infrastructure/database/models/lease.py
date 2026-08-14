"""功能说明：
    Lease ORM 模型：合同当前投影、版本、费用计划、变更、文档与退租结算。

业务职责：
    Infrastructure 持久化；业务状态与权限规则位于 Domain/Application。
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import (
    FK_TYPE,
    Base,
    PrimaryKeyMixin,
    TimestampMixin,
)


class LeaseContract(Base, PrimaryKeyMixin, TimestampMixin):
    """稳定合同聚合根与当前有效投影。"""

    __tablename__ = "lease_contracts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "contract_no", name="uk_lease_contract_no"),
        Index(
            "uk_lease_contract_source_ref",
            "tenant_id",
            "source_system",
            "source_ref",
            unique=True,
            postgresql_where=text("source_ref IS NOT NULL"),
            sqlite_where=text("source_ref IS NOT NULL"),
        ),
        Index(
            "ix_lease_contract_scope_status_end",
            "tenant_id",
            "park_id",
            "status",
            "end_date",
        ),
        Index(
            "ix_lease_contract_scope_party",
            "tenant_id",
            "party_id",
            "status",
        ),
        Index("idx_lease_park_status", "tenant_id", "park_id", "status"),
        Index("idx_lease_party", "tenant_id", "party_id"),
        Index("idx_lease_end_date", "tenant_id", "end_date"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    party_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parties.id"), nullable=False)
    contract_no: Mapped[str] = mapped_column(String(64), nullable=False)
    contract_type: Mapped[str] = mapped_column(String(32), nullable=False, default="LEASE")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    approval_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    effective_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    terminated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    increase_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    increase_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    deposit_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0")
    )
    current_version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_system: Mapped[str] = mapped_column(String(32), nullable=False, default="MANUAL")
    source_ref: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, nullable=True)


class LeaseContractUnit(Base, PrimaryKeyMixin):
    """合同当前占用单元投影。"""

    __tablename__ = "lease_contract_units"
    __table_args__ = (
        UniqueConstraint("contract_id", "unit_id", name="uk_lcu_contract_unit"),
        Index("idx_lcu_unit", "unit_id"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    contract_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("lease_contracts.id"), nullable=False
    )
    unit_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("units.id"), nullable=False)
    occupied_area: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )
    unit_rent_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )


class LeaseTerm(Base, PrimaryKeyMixin):
    """V1 兼容条款；V2 新写使用 LeaseChargeItem.rules_json。"""

    __tablename__ = "lease_terms"
    __table_args__ = (Index("idx_lease_terms_contract", "tenant_id", "contract_id"),)

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    contract_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("lease_contracts.id"), nullable=False
    )
    term_type: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class LeaseChangeOrder(Base, PrimaryKeyMixin, TimestampMixin):
    """已生效合同的类型化变更提议与审批/应用状态。"""

    __tablename__ = "lease_change_orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "change_no", name="uk_lease_change_no"),
        Index(
            "uk_lease_change_inflight",
            "tenant_id",
            "contract_id",
            unique=True,
            postgresql_where=text("status IN ('SUBMITTED', 'APPROVED')"),
            sqlite_where=text("status IN ('SUBMITTED', 'APPROVED')"),
        ),
        Index(
            "uk_lease_change_idempotency",
            "tenant_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
            sqlite_where=text("idempotency_key IS NOT NULL"),
        ),
        Index(
            "ix_lease_change_due",
            "tenant_id",
            "status",
            "effective_date",
        ),
        Index("ix_lease_change_contract_id", "contract_id"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    contract_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("lease_contracts.id"), nullable=False
    )
    change_no: Mapped[str] = mapped_column(String(64), nullable=False)
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    base_version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    applied_version_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    proposal_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    proposal_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    proposal_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    approval_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("approval_requests.id"), nullable=True
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)


class LeaseExitSettlement(Base, PrimaryKeyMixin, TimestampMixin):
    """退租交接与财务清算事实快照；不执行资金操作。"""

    __tablename__ = "lease_exit_settlements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "settlement_no", name="uk_lease_exit_settlement_no"),
        Index(
            "uk_lease_exit_open",
            "tenant_id",
            "contract_id",
            unique=True,
            postgresql_where=text("status IN ('DRAFT', 'SUBMITTED', 'APPROVED')"),
            sqlite_where=text("status IN ('DRAFT', 'SUBMITTED', 'APPROVED')"),
        ),
        Index(
            "uk_lease_exit_idempotency",
            "tenant_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
            sqlite_where=text("idempotency_key IS NOT NULL"),
        ),
        Index("ix_lease_exit_scope_status", "tenant_id", "park_id", "status"),
        Index("ix_lease_exit_contract_id", "contract_id"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    contract_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("lease_contracts.id"), nullable=False
    )
    change_order_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("lease_change_orders.id"), nullable=True, unique=True
    )
    settlement_no: Mapped[str] = mapped_column(String(64), nullable=False)
    contract_version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    handover_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    inspection_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meter_readings_json: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    held_deposit_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    outstanding_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    outstanding_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="BILLING_SCOPED_READ"
    )
    outstanding_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    receivable_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    deduction_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    refund_adjustment_total: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    net_due_from_party: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    net_due_to_party: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    financial_clearance_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNCONFIRMED"
    )
    clearance_evidence_attachment_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("attachments.id"), nullable=True
    )
    clearance_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    clearance_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    clearance_by: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True
    )
    clearance_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    approval_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("approval_requests.id"), nullable=True
    )
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)


class LeaseContractVersion(Base, PrimaryKeyMixin, TimestampMixin):
    """合同不可变规范快照。"""

    __tablename__ = "lease_contract_versions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "contract_id", "version_no", name="uk_lease_contract_version"
        ),
        Index("ix_lease_version_timeline", "tenant_id", "contract_id", "version_no"),
        Index("ix_lease_version_contract_id", "contract_id"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    contract_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("lease_contracts.id"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    base_version_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    change_order_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("lease_change_orders.id"), nullable=True
    )
    exit_settlement_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("lease_exit_settlements.id"), nullable=True
    )
    approval_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("approval_requests.id"), nullable=True
    )
    effective_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)


class LeaseChargeItem(Base, PrimaryKeyMixin, TimestampMixin):
    """合同当前结构化费用项。"""

    __tablename__ = "lease_charge_items"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "contract_id", "charge_code", name="uk_lease_charge_code"
        ),
        Index("ix_lease_charge_contract", "tenant_id", "contract_id", "sort_order", "id"),
        Index("ix_lease_charge_contract_id", "contract_id"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    contract_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("lease_contracts.id"), nullable=False
    )
    charge_code: Mapped[str] = mapped_column(String(64), nullable=False)
    charge_type: Mapped[str] = mapped_column(String(32), nullable=False)
    calculation_method: Mapped[str] = mapped_column(String(32), nullable=False)
    billing_cycle: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, default=0)
    rules_json: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    source_term_id: Mapped[Optional[int]] = mapped_column(FK_TYPE, nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="CONFIRMED")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class LeasePerformanceSchedule(Base, PrimaryKeyMixin, TimestampMixin):
    """合同版本绑定的履约计划，不是 Bill。"""

    __tablename__ = "lease_performance_schedules"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "deterministic_key", name="uk_lease_schedule_deterministic"
        ),
        Index(
            "ix_lease_schedule_contract_period",
            "tenant_id",
            "contract_id",
            "contract_version_no",
            "period_start",
        ),
        Index("ix_lease_schedule_contract_id", "contract_id"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    contract_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("lease_contracts.id"), nullable=False
    )
    charge_item_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("lease_charge_items.id", ondelete="SET NULL"), nullable=True
    )
    contract_version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    charge_code: Mapped[str] = mapped_column(String(64), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    area: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    rule_refs_json: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    deterministic_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PLANNED")


class LeaseContractDocument(Base, PrimaryKeyMixin, TimestampMixin):
    """附件之上的合同业务版本与签署状态。"""

    __tablename__ = "lease_contract_documents"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "contract_id",
            "document_type",
            "document_version",
            name="uk_lease_document_version",
        ),
        Index("ix_lease_document_contract", "tenant_id", "contract_id", "status", "id"),
        Index("ix_lease_document_contract_id", "contract_id"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    contract_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("lease_contracts.id"), nullable=False
    )
    contract_version_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    change_order_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("lease_change_orders.id"), nullable=True
    )
    exit_settlement_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("lease_exit_settlements.id"), nullable=True
    )
    attachment_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("attachments.id"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    document_version: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    is_main: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    signature_provider: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    signature_ref: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    live_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)


class LeaseExitItem(Base, PrimaryKeyMixin, TimestampMixin):
    """退租结算的应收、扣减与应退明细。"""

    __tablename__ = "lease_exit_items"
    __table_args__ = (
        Index("ix_lease_exit_item_settlement", "tenant_id", "settlement_id", "sort_order", "id"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    settlement_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("lease_exit_settlements.id"), nullable=False
    )
    item_type: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    evidence_attachment_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("attachments.id"), nullable=True
    )
    source_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    source_ref: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

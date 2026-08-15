"""Governed supplier, procurement, inventory, and outsourcing persistence models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, TimestampMixin


class SupplySupplier(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "supply_suppliers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE','SUSPENDED','RETIRED')", name="ck_supply_supplier_status"
        ),
        CheckConstraint("lock_version > 0", name="ck_supply_supplier_lock"),
        UniqueConstraint("tenant_id", "code", name="uk_supply_supplier_code"),
        UniqueConstraint("tenant_id", "party_id", name="uk_supply_supplier_party"),
        UniqueConstraint("tenant_id", "id", name="uk_supply_supplier_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_supply_supplier_party",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_supply_supplier_creator",
        ),
        Index("ix_supply_supplier_status", "tenant_id", "status"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    party_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)


class SupplierParkScope(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "supply_supplier_park_scopes"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE','SUSPENDED','RETIRED')", name="ck_supply_supplier_scope_status"
        ),
        UniqueConstraint(
            "tenant_id", "supplier_id", "park_id", "service_type", name="uk_supply_supplier_scope"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "supplier_id"],
            ["supply_suppliers.tenant_id", "supply_suppliers.id"],
            name="fk_supply_supplier_scope_supplier",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_supply_supplier_scope_park",
        ),
        Index("ix_supply_supplier_scope_park", "tenant_id", "park_id", "status"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    supplier_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    service_type: Mapped[str] = mapped_column(String(64), nullable=False, default="GENERAL")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")


class SupplierQualification(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "supply_supplier_qualifications"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE','EXPIRED','REVOKED')",
            name="ck_supply_supplier_qualification_status",
        ),
        CheckConstraint(
            "expires_on IS NULL OR expires_on >= effective_on",
            name="ck_supply_supplier_qualification_dates",
        ),
        UniqueConstraint(
            "tenant_id",
            "supplier_id",
            "qualification_type",
            "credential_fingerprint",
            name="uk_supply_supplier_qualification",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "supplier_id"],
            ["supply_suppliers.tenant_id", "supply_suppliers.id"],
            name="fk_supply_supplier_qualification_supplier",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "attachment_id"],
            ["attachments.tenant_id", "attachments.id"],
            name="fk_supply_supplier_qualification_attachment",
        ),
        Index("ix_supply_supplier_qualification_expiry", "tenant_id", "expires_on", "status"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    supplier_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    qualification_type: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_masked: Mapped[str] = mapped_column(String(32), nullable=False)
    credential_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    issuer: Mapped[str] = mapped_column(String(128), nullable=False)
    effective_on: Mapped[date] = mapped_column(Date, nullable=False)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    attachment_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)


class SupplierEvaluation(Base, PrimaryKeyMixin):
    __tablename__ = "supply_supplier_evaluations"
    __table_args__ = (
        CheckConstraint("score BETWEEN 1 AND 5", name="ck_supply_supplier_evaluation_score"),
        ForeignKeyConstraint(
            ["tenant_id", "supplier_id"],
            ["supply_suppliers.tenant_id", "supply_suppliers.id"],
            name="fk_supply_supplier_evaluation_supplier",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_supply_supplier_evaluation_park",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "evaluated_by"],
            ["users.tenant_id", "users.id"],
            name="fk_supply_supplier_evaluation_user",
        ),
        Index("ix_supply_supplier_evaluation_timeline", "tenant_id", "supplier_id", "evaluated_at"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    supplier_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    evaluated_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SupplyMaterial(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "supply_materials"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','RETIRED')", name="ck_supply_material_status"),
        CheckConstraint("reorder_point >= 0", name="ck_supply_material_reorder"),
        UniqueConstraint("tenant_id", "code", name="uk_supply_material_code"),
        UniqueConstraint("tenant_id", "id", name="uk_supply_material_tenant_id"),
        Index("ix_supply_material_category", "tenant_id", "category", "status"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    reorder_point: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal(0), server_default="0"
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")


class SupplyWarehouse(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "supply_warehouses"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','RETIRED')", name="ck_supply_warehouse_status"),
        UniqueConstraint("tenant_id", "park_id", "code", name="uk_supply_warehouse_code"),
        UniqueConstraint("tenant_id", "park_id", "id", name="uk_supply_warehouse_tenant_park_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_supply_warehouse_park",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")


class StockBalance(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "supply_stock_balances"
    __table_args__ = (
        CheckConstraint("on_hand_qty >= 0", name="ck_supply_stock_on_hand_nonnegative"),
        CheckConstraint(
            "reserved_qty >= 0 AND reserved_qty <= on_hand_qty",
            name="ck_supply_stock_reserved_valid",
        ),
        CheckConstraint("lock_version > 0", name="ck_supply_stock_balance_lock"),
        UniqueConstraint(
            "tenant_id", "park_id", "warehouse_id", "material_id", name="uk_supply_stock_balance"
        ),
        UniqueConstraint("tenant_id", "id", name="uk_supply_stock_balance_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "warehouse_id"],
            ["supply_warehouses.tenant_id", "supply_warehouses.park_id", "supply_warehouses.id"],
            name="fk_supply_stock_balance_warehouse",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "material_id"],
            ["supply_materials.tenant_id", "supply_materials.id"],
            name="fk_supply_stock_balance_material",
        ),
        Index("ix_supply_stock_balance_scope", "tenant_id", "park_id", "warehouse_id"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    material_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    on_hand_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal(0), server_default="0"
    )
    reserved_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal(0), server_default="0"
    )
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )


class StockMovement(Base, PrimaryKeyMixin):
    __tablename__ = "supply_stock_movements"
    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('RECEIPT','ISSUE','RETURN','ADJUSTMENT','REVERSAL')",
            name="ck_supply_stock_movement_type",
        ),
        CheckConstraint("quantity <> 0", name="ck_supply_stock_movement_quantity"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_supply_stock_movement_key"),
        UniqueConstraint("tenant_id", "id", name="uk_supply_stock_movement_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "balance_id"],
            ["supply_stock_balances.tenant_id", "supply_stock_balances.id"],
            name="fk_supply_stock_movement_balance",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reverses_movement_id"],
            ["supply_stock_movements.tenant_id", "supply_stock_movements.id"],
            name="fk_supply_stock_movement_reversal",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "actor_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_supply_stock_movement_actor",
        ),
        Index(
            "ix_supply_stock_movement_timeline", "tenant_id", "park_id", "balance_id", "occurred_at"
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    balance_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    material_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    movement_type: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reference_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reference_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    reverses_movement_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ProcurementRequisition(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "supply_procurement_requisitions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','PENDING_APPROVAL','APPROVED','REJECTED','CANCELLED','ORDERED')",
            name="ck_supply_procurement_requisition_status",
        ),
        CheckConstraint("lock_version > 0", name="ck_supply_procurement_requisition_lock"),
        UniqueConstraint("tenant_id", "request_no", name="uk_supply_procurement_requisition_no"),
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uk_supply_procurement_requisition_key"
        ),
        UniqueConstraint("tenant_id", "id", name="uk_supply_procurement_requisition_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_supply_procurement_requisition_park",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "approval_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_supply_procurement_requisition_approval",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "requested_by"],
            ["users.tenant_id", "users.id"],
            name="fk_supply_procurement_requisition_requester",
        ),
        Index("ix_supply_procurement_requisition_scope", "tenant_id", "park_id", "status"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    request_no: Mapped[str] = mapped_column(String(40), nullable=False)
    purpose: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT")
    approval_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    requested_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ProcurementRequisitionLine(Base, PrimaryKeyMixin):
    __tablename__ = "supply_procurement_requisition_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_supply_procurement_requisition_line_qty"),
        CheckConstraint(
            "estimated_unit_price >= 0", name="ck_supply_procurement_requisition_line_price"
        ),
        UniqueConstraint(
            "tenant_id", "requisition_id", "line_no", name="uk_supply_procurement_requisition_line"
        ),
        UniqueConstraint(
            "tenant_id", "id", name="uk_supply_procurement_requisition_line_tenant_id"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "requisition_id"],
            ["supply_procurement_requisitions.tenant_id", "supply_procurement_requisitions.id"],
            name="fk_supply_procurement_requisition_line_header",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "material_id"],
            ["supply_materials.tenant_id", "supply_materials.id"],
            name="fk_supply_procurement_requisition_line_material",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    requisition_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    material_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    estimated_unit_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal(0), server_default="0"
    )
    purpose: Mapped[str | None] = mapped_column(String(255), nullable=True)


class PurchaseOrder(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "supply_purchase_orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ISSUED','ACK_PENDING','ACKNOWLEDGED','PARTIALLY_RECEIVED','RECEIVED','REJECTED','CANCELLED')",
            name="ck_supply_purchase_order_status",
        ),
        CheckConstraint(
            "truth_mode IN ('LOCAL','EXTERNAL_PENDING')", name="ck_supply_purchase_order_truth"
        ),
        CheckConstraint("total_amount >= 0", name="ck_supply_purchase_order_total"),
        CheckConstraint("lock_version > 0", name="ck_supply_purchase_order_lock"),
        UniqueConstraint("tenant_id", "order_no", name="uk_supply_purchase_order_no"),
        UniqueConstraint(
            "tenant_id", "requisition_id", name="uk_supply_purchase_order_requisition"
        ),
        UniqueConstraint("tenant_id", "id", name="uk_supply_purchase_order_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_supply_purchase_order_park",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "requisition_id"],
            ["supply_procurement_requisitions.tenant_id", "supply_procurement_requisitions.id"],
            name="fk_supply_purchase_order_requisition",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "supplier_id"],
            ["supply_suppliers.tenant_id", "supply_suppliers.id"],
            name="fk_supply_purchase_order_supplier",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "ordered_by"],
            ["users.tenant_id", "users.id"],
            name="fk_supply_purchase_order_buyer",
        ),
        Index("ix_supply_purchase_order_scope", "tenant_id", "park_id", "status"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    requisition_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    supplier_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    order_no: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ISSUED")
    truth_mode: Mapped[str] = mapped_column(String(24), nullable=False, default="LOCAL")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal(0), server_default="0"
    )
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    ordered_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PurchaseOrderLine(Base, PrimaryKeyMixin):
    __tablename__ = "supply_purchase_order_lines"
    __table_args__ = (
        CheckConstraint("ordered_qty > 0", name="ck_supply_purchase_order_line_qty"),
        CheckConstraint("unit_price >= 0", name="ck_supply_purchase_order_line_price"),
        CheckConstraint(
            "received_qty >= 0 AND received_qty <= ordered_qty",
            name="ck_supply_purchase_order_line_received",
        ),
        UniqueConstraint("tenant_id", "order_id", "line_no", name="uk_supply_purchase_order_line"),
        UniqueConstraint("tenant_id", "id", name="uk_supply_purchase_order_line_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["supply_purchase_orders.tenant_id", "supply_purchase_orders.id"],
            name="fk_supply_purchase_order_line_header",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "requisition_line_id"],
            [
                "supply_procurement_requisition_lines.tenant_id",
                "supply_procurement_requisition_lines.id",
            ],
            name="fk_supply_purchase_order_line_request",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "material_id"],
            ["supply_materials.tenant_id", "supply_materials.id"],
            name="fk_supply_purchase_order_line_material",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    order_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    requisition_line_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    material_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    ordered_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    received_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal(0), server_default="0"
    )


class GoodsReceipt(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "supply_goods_receipts"
    __table_args__ = (
        CheckConstraint("status IN ('POSTED','REVERSED')", name="ck_supply_goods_receipt_status"),
        UniqueConstraint("tenant_id", "receipt_no", name="uk_supply_goods_receipt_no"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_supply_goods_receipt_key"),
        UniqueConstraint("tenant_id", "id", name="uk_supply_goods_receipt_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["supply_purchase_orders.tenant_id", "supply_purchase_orders.id"],
            name="fk_supply_goods_receipt_order",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "warehouse_id"],
            ["supply_warehouses.tenant_id", "supply_warehouses.park_id", "supply_warehouses.id"],
            name="fk_supply_goods_receipt_warehouse",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "received_by"],
            ["users.tenant_id", "users.id"],
            name="fk_supply_goods_receipt_receiver",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    order_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    receipt_no: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="POSTED")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    received_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class GoodsReceiptLine(Base, PrimaryKeyMixin):
    __tablename__ = "supply_goods_receipt_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_supply_goods_receipt_line_qty"),
        UniqueConstraint(
            "tenant_id", "receipt_id", "order_line_id", name="uk_supply_goods_receipt_line"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "receipt_id"],
            ["supply_goods_receipts.tenant_id", "supply_goods_receipts.id"],
            name="fk_supply_goods_receipt_line_header",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "order_line_id"],
            ["supply_purchase_order_lines.tenant_id", "supply_purchase_order_lines.id"],
            name="fk_supply_goods_receipt_line_order",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "movement_id"],
            ["supply_stock_movements.tenant_id", "supply_stock_movements.id"],
            name="fk_supply_goods_receipt_line_movement",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    receipt_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    order_line_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    batch_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    movement_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)


class InventoryRequisition(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "supply_inventory_requisitions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','PENDING_APPROVAL','APPROVED','PARTIALLY_ISSUED','ISSUED','CANCELLED','REJECTED')",
            name="ck_supply_inventory_requisition_status",
        ),
        CheckConstraint("lock_version > 0", name="ck_supply_inventory_requisition_lock"),
        UniqueConstraint("tenant_id", "request_no", name="uk_supply_inventory_requisition_no"),
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uk_supply_inventory_requisition_key"
        ),
        UniqueConstraint("tenant_id", "id", name="uk_supply_inventory_requisition_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_supply_inventory_requisition_park",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "work_order_id"],
            ["work_orders.tenant_id", "work_orders.park_id", "work_orders.id"],
            name="fk_supply_inventory_requisition_work_order",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "approval_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_supply_inventory_requisition_approval",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "requested_by"],
            ["users.tenant_id", "users.id"],
            name="fk_supply_inventory_requisition_requester",
        ),
        Index("ix_supply_inventory_requisition_scope", "tenant_id", "park_id", "status"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    request_no: Mapped[str] = mapped_column(String(40), nullable=False)
    purpose: Mapped[str] = mapped_column(String(500), nullable=False)
    work_order_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT")
    approval_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    requested_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)


class InventoryRequisitionLine(Base, PrimaryKeyMixin):
    __tablename__ = "supply_inventory_requisition_lines"
    __table_args__ = (
        CheckConstraint("requested_qty > 0", name="ck_supply_inventory_requisition_line_qty"),
        CheckConstraint(
            "reserved_qty >= 0 AND issued_qty >= 0 AND returned_qty >= 0",
            name="ck_supply_inventory_requisition_line_progress",
        ),
        CheckConstraint(
            "reserved_qty <= requested_qty AND issued_qty <= requested_qty AND returned_qty <= issued_qty",
            name="ck_supply_inventory_requisition_line_bounds",
        ),
        UniqueConstraint(
            "tenant_id", "requisition_id", "line_no", name="uk_supply_inventory_requisition_line"
        ),
        UniqueConstraint("tenant_id", "id", name="uk_supply_inventory_requisition_line_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "requisition_id"],
            ["supply_inventory_requisitions.tenant_id", "supply_inventory_requisitions.id"],
            name="fk_supply_inventory_requisition_line_header",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "material_id"],
            ["supply_materials.tenant_id", "supply_materials.id"],
            name="fk_supply_inventory_requisition_line_material",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "warehouse_id"],
            ["supply_warehouses.tenant_id", "supply_warehouses.park_id", "supply_warehouses.id"],
            name="fk_supply_inventory_requisition_line_warehouse",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    requisition_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    material_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    requested_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reserved_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal(0), server_default="0"
    )
    issued_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal(0), server_default="0"
    )
    returned_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal(0), server_default="0"
    )


class Stocktake(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "supply_stocktakes"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','PENDING_APPROVAL','APPROVED','POSTED','REJECTED','CANCELLED')",
            name="ck_supply_stocktake_status",
        ),
        CheckConstraint("lock_version > 0", name="ck_supply_stocktake_lock"),
        UniqueConstraint("tenant_id", "stocktake_no", name="uk_supply_stocktake_no"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_supply_stocktake_key"),
        UniqueConstraint("tenant_id", "id", name="uk_supply_stocktake_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "warehouse_id"],
            ["supply_warehouses.tenant_id", "supply_warehouses.park_id", "supply_warehouses.id"],
            name="fk_supply_stocktake_warehouse",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "approval_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_supply_stocktake_approval",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "counted_by"],
            ["users.tenant_id", "users.id"],
            name="fk_supply_stocktake_counter",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    stocktake_no: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT")
    approval_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    counted_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)


class StocktakeLine(Base, PrimaryKeyMixin):
    __tablename__ = "supply_stocktake_lines"
    __table_args__ = (
        CheckConstraint(
            "expected_qty >= 0 AND counted_qty >= 0", name="ck_supply_stocktake_line_qty"
        ),
        UniqueConstraint(
            "tenant_id", "stocktake_id", "material_id", name="uk_supply_stocktake_line"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "stocktake_id"],
            ["supply_stocktakes.tenant_id", "supply_stocktakes.id"],
            name="fk_supply_stocktake_line_header",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "material_id"],
            ["supply_materials.tenant_id", "supply_materials.id"],
            name="fk_supply_stocktake_line_material",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "adjustment_movement_id"],
            ["supply_stock_movements.tenant_id", "supply_stock_movements.id"],
            name="fk_supply_stocktake_line_movement",
        ),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    stocktake_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    material_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    expected_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    counted_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    adjustment_movement_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)


class OutsourcingOrder(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "supply_outsourcing_orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','PENDING_APPROVAL','APPROVED','IN_PROGRESS','WAITING_ACCEPTANCE','REWORK','ACCEPTED','REJECTED','CANCELLED')",
            name="ck_supply_outsourcing_order_status",
        ),
        CheckConstraint("amount >= 0", name="ck_supply_outsourcing_order_amount"),
        CheckConstraint("lock_version > 0", name="ck_supply_outsourcing_order_lock"),
        UniqueConstraint("tenant_id", "order_no", name="uk_supply_outsourcing_order_no"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_supply_outsourcing_order_key"),
        UniqueConstraint("tenant_id", "id", name="uk_supply_outsourcing_order_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_supply_outsourcing_order_park",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "supplier_id"],
            ["supply_suppliers.tenant_id", "supply_suppliers.id"],
            name="fk_supply_outsourcing_order_supplier",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "work_order_id"],
            ["work_orders.tenant_id", "work_orders.park_id", "work_orders.id"],
            name="fk_supply_outsourcing_order_work_order",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "approval_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_supply_outsourcing_order_approval",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "requested_by"],
            ["users.tenant_id", "users.id"],
            name="fk_supply_outsourcing_order_requester",
        ),
        Index("ix_supply_outsourcing_order_scope", "tenant_id", "park_id", "status"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    supplier_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    work_order_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    order_no: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    deliverables_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    sla_due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT")
    approval_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    settlement_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="NOT_INTEGRATED"
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    requested_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)


class OutsourcingEvent(Base, PrimaryKeyMixin):
    __tablename__ = "supply_outsourcing_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('SUBMITTED','APPROVED','STARTED','PROGRESS','COMPLETED','ACCEPTED','REWORK','CANCELLED')",
            name="ck_supply_outsourcing_event_type",
        ),
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_supply_outsourcing_event_key"),
        ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["supply_outsourcing_orders.tenant_id", "supply_outsourcing_orders.id"],
            name="fk_supply_outsourcing_event_order",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "actor_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_supply_outsourcing_event_actor",
        ),
        Index("ix_supply_outsourcing_event_timeline", "tenant_id", "order_id", "occurred_at"),
    )
    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    order_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

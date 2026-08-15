"""Tenant- and park-scoped supply persistence boundary."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any, TypeVar

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.models.attachment import Attachment
from app.infrastructure.database.models.facility_ops import WorkOrder
from app.infrastructure.database.models.park_property import Park
from app.infrastructure.database.models.party import Party, PartyRole
from app.infrastructure.database.models.supply import (
    GoodsReceipt,
    GoodsReceiptLine,
    InventoryRequisition,
    InventoryRequisitionLine,
    OutsourcingEvent,
    OutsourcingOrder,
    ProcurementRequisition,
    ProcurementRequisitionLine,
    PurchaseOrder,
    PurchaseOrderLine,
    StockBalance,
    StockMovement,
    Stocktake,
    StocktakeLine,
    SupplierEvaluation,
    SupplierParkScope,
    SupplierQualification,
    SupplyMaterial,
    SupplySupplier,
    SupplyWarehouse,
)
from app.infrastructure.database.models.workflow import ApprovalRequest
from app.shared.tenant_context import ParkScopeMode, TenantContext

T = TypeVar("T")


class SupplyRepository:
    """The only supply layer that imports ORM models."""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    @property
    def tenant_id(self) -> int:
        return int(self.ctx.tenant_id)

    def _scope(self, stmt, model):  # type: ignore[no-untyped-def]
        stmt = stmt.where(model.tenant_id == self.tenant_id)
        if hasattr(model, "park_id"):
            if self.ctx.park_scope_mode == ParkScopeMode.ALL:
                return stmt
            if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
                return stmt.where(model.park_id.in_(list(self.ctx.park_ids)))
            return stmt.where(False)
        return stmt

    def _lock(self, stmt, enabled: bool):  # type: ignore[no-untyped-def]
        if (
            enabled
            and self.session.bind is not None
            and self.session.bind.dialect.name == "postgresql"
        ):
            return stmt.with_for_update()
        return stmt

    def add(self, row: T) -> T:
        row.tenant_id = self.tenant_id
        if hasattr(row, "park_id") and not self.ctx.allows_park(int(row.park_id)):
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        self.session.add(row)
        self.session.flush()
        return row

    def save(self, row: T) -> T:
        if int(row.tenant_id) != self.tenant_id:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        self.session.add(row)
        self.session.flush()
        return row

    def park(self, park_id: int) -> Park | None:
        if not self.ctx.allows_park(int(park_id)):
            return None
        return self.session.scalar(
            select(Park).where(
                Park.tenant_id == self.tenant_id,
                Park.id == int(park_id),
                Park.is_deleted.is_(False),
            )
        )

    def supplier_party(self, party_id: int) -> Party | None:
        return self.session.scalar(
            select(Party)
            .join(PartyRole, PartyRole.party_id == Party.id)
            .where(
                Party.tenant_id == self.tenant_id,
                Party.id == int(party_id),
                Party.party_type == "ORGANIZATION",
                Party.status == "ACTIVE",
                PartyRole.tenant_id == self.tenant_id,
                PartyRole.role_code == "SUPPLIER",
                PartyRole.status == "ACTIVE",
            )
        )

    def attachment(self, attachment_id: int) -> Attachment | None:
        return self.session.scalar(
            select(Attachment).where(
                Attachment.tenant_id == self.tenant_id, Attachment.id == int(attachment_id)
            )
        )

    def work_order(self, work_order_id: int, park_id: int) -> WorkOrder | None:
        return self.session.scalar(
            select(WorkOrder).where(
                WorkOrder.tenant_id == self.tenant_id,
                WorkOrder.park_id == int(park_id),
                WorkOrder.id == int(work_order_id),
            )
        )

    def list_suppliers(
        self, *, status: str | None, keyword: str | None, offset: int, limit: int
    ) -> Sequence[SupplySupplier]:
        stmt = select(SupplySupplier).where(SupplySupplier.tenant_id == self.tenant_id)
        if status:
            stmt = stmt.where(SupplySupplier.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            stmt = stmt.where(
                or_(SupplySupplier.code.ilike(pattern), SupplySupplier.display_name.ilike(pattern))
            )
        return list(
            self.session.scalars(
                stmt.order_by(SupplySupplier.code).offset(offset).limit(limit)
            ).all()
        )

    def count_suppliers(self, *, status: str | None, keyword: str | None) -> int:
        stmt = (
            select(func.count())
            .select_from(SupplySupplier)
            .where(SupplySupplier.tenant_id == self.tenant_id)
        )
        if status:
            stmt = stmt.where(SupplySupplier.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            stmt = stmt.where(
                or_(SupplySupplier.code.ilike(pattern), SupplySupplier.display_name.ilike(pattern))
            )
        return int(self.session.scalar(stmt) or 0)

    def supplier(self, supplier_id: int, *, for_update: bool = False) -> SupplySupplier | None:
        return self.session.scalar(
            self._lock(
                select(SupplySupplier).where(
                    SupplySupplier.tenant_id == self.tenant_id,
                    SupplySupplier.id == int(supplier_id),
                ),
                for_update,
            )
        )

    def supplier_scopes(self, supplier_id: int) -> Sequence[SupplierParkScope]:
        stmt = self._scope(
            select(SupplierParkScope).where(SupplierParkScope.supplier_id == int(supplier_id)),
            SupplierParkScope,
        )
        return list(
            self.session.scalars(
                stmt.order_by(SupplierParkScope.park_id, SupplierParkScope.service_type)
            ).all()
        )

    def supplier_qualifications(self, supplier_id: int) -> Sequence[SupplierQualification]:
        return list(
            self.session.scalars(
                select(SupplierQualification)
                .where(
                    SupplierQualification.tenant_id == self.tenant_id,
                    SupplierQualification.supplier_id == int(supplier_id),
                )
                .order_by(SupplierQualification.expires_on)
            ).all()
        )

    def supplier_evaluations(self, supplier_id: int) -> Sequence[SupplierEvaluation]:
        stmt = self._scope(
            select(SupplierEvaluation).where(SupplierEvaluation.supplier_id == int(supplier_id)),
            SupplierEvaluation,
        )
        return list(
            self.session.scalars(stmt.order_by(SupplierEvaluation.evaluated_at.desc())).all()
        )

    def supplier_eligible(
        self,
        supplier_id: int,
        park_id: int,
        service_type: str,
        required_qualification: str | None = None,
    ) -> bool:
        supplier = self.supplier(supplier_id)
        if (
            supplier is None
            or supplier.status != "ACTIVE"
            or not self.ctx.allows_park(int(park_id))
        ):
            return False
        scope = self.session.scalar(
            select(SupplierParkScope.id).where(
                SupplierParkScope.tenant_id == self.tenant_id,
                SupplierParkScope.supplier_id == int(supplier_id),
                SupplierParkScope.park_id == int(park_id),
                SupplierParkScope.service_type.in_([service_type, "GENERAL"]),
                SupplierParkScope.status == "ACTIVE",
            )
        )
        if not scope:
            return False
        if required_qualification:
            today = datetime.now(timezone.utc).date()
            qualification = self.session.scalar(
                select(SupplierQualification.id).where(
                    SupplierQualification.tenant_id == self.tenant_id,
                    SupplierQualification.supplier_id == int(supplier_id),
                    SupplierQualification.qualification_type == required_qualification,
                    SupplierQualification.status == "ACTIVE",
                    SupplierQualification.effective_on <= today,
                    or_(
                        SupplierQualification.expires_on.is_(None),
                        SupplierQualification.expires_on >= today,
                    ),
                )
            )
            return bool(qualification)
        return True

    def list_materials(
        self,
        *,
        status: str | None = None,
        keyword: str | None = None,
        offset: int = 0,
        limit: int = 200,
    ) -> Sequence[SupplyMaterial]:
        stmt = select(SupplyMaterial).where(SupplyMaterial.tenant_id == self.tenant_id)
        if status:
            stmt = stmt.where(SupplyMaterial.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    SupplyMaterial.code.ilike(pattern),
                    SupplyMaterial.name.ilike(pattern),
                    SupplyMaterial.category.ilike(pattern),
                )
            )
        return list(
            self.session.scalars(
                stmt.order_by(SupplyMaterial.code, SupplyMaterial.id).offset(offset).limit(limit)
            ).all()
        )

    def material(self, material_id: int) -> SupplyMaterial | None:
        return self.session.scalar(
            select(SupplyMaterial).where(
                SupplyMaterial.tenant_id == self.tenant_id, SupplyMaterial.id == int(material_id)
            )
        )

    def list_warehouses(
        self,
        park_id: int | None = None,
        *,
        status: str | None = None,
        keyword: str | None = None,
        offset: int = 0,
        limit: int = 200,
    ) -> Sequence[SupplyWarehouse]:
        stmt = self._scope(select(SupplyWarehouse), SupplyWarehouse)
        if park_id is not None:
            stmt = stmt.where(SupplyWarehouse.park_id == int(park_id))
        if status:
            stmt = stmt.where(SupplyWarehouse.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            stmt = stmt.where(
                or_(SupplyWarehouse.code.ilike(pattern), SupplyWarehouse.name.ilike(pattern))
            )
        return list(
            self.session.scalars(
                stmt.order_by(SupplyWarehouse.code, SupplyWarehouse.id).offset(offset).limit(limit)
            ).all()
        )

    def warehouse(self, warehouse_id: int) -> SupplyWarehouse | None:
        return self.session.scalar(
            self._scope(
                select(SupplyWarehouse).where(SupplyWarehouse.id == int(warehouse_id)),
                SupplyWarehouse,
            )
        )

    def balance(
        self, *, park_id: int, warehouse_id: int, material_id: int, for_update: bool = False
    ) -> StockBalance | None:
        stmt = self._scope(
            select(StockBalance).where(
                StockBalance.park_id == int(park_id),
                StockBalance.warehouse_id == int(warehouse_id),
                StockBalance.material_id == int(material_id),
            ),
            StockBalance,
        )
        return self.session.scalar(self._lock(stmt, for_update))

    def balances(
        self, *, park_id: int | None = None, warehouse_id: int | None = None
    ) -> Sequence[StockBalance]:
        stmt = self._scope(select(StockBalance), StockBalance)
        if park_id is not None:
            stmt = stmt.where(StockBalance.park_id == int(park_id))
        if warehouse_id is not None:
            stmt = stmt.where(StockBalance.warehouse_id == int(warehouse_id))
        return list(
            self.session.scalars(
                stmt.order_by(
                    StockBalance.park_id, StockBalance.warehouse_id, StockBalance.material_id
                )
            ).all()
        )

    def movements(
        self, *, balance_id: int | None = None, limit: int = 200
    ) -> Sequence[StockMovement]:
        stmt = self._scope(select(StockMovement), StockMovement)
        if balance_id is not None:
            stmt = stmt.where(StockMovement.balance_id == int(balance_id))
        return list(
            self.session.scalars(
                stmt.order_by(StockMovement.occurred_at.desc(), StockMovement.id.desc()).limit(
                    limit
                )
            ).all()
        )

    def movement_by_key(self, key: str) -> StockMovement | None:
        return self.session.scalar(
            select(StockMovement).where(
                StockMovement.tenant_id == self.tenant_id, StockMovement.idempotency_key == key
            )
        )

    def requisition_by_key(self, key: str) -> ProcurementRequisition | None:
        return self.session.scalar(
            select(ProcurementRequisition).where(
                ProcurementRequisition.tenant_id == self.tenant_id,
                ProcurementRequisition.idempotency_key == key,
            )
        )

    def requisition(
        self, requisition_id: int, *, for_update: bool = False
    ) -> ProcurementRequisition | None:
        stmt = self._scope(
            select(ProcurementRequisition).where(ProcurementRequisition.id == int(requisition_id)),
            ProcurementRequisition,
        )
        return self.session.scalar(self._lock(stmt, for_update))

    def requisition_lines(self, requisition_id: int) -> Sequence[ProcurementRequisitionLine]:
        return list(
            self.session.scalars(
                select(ProcurementRequisitionLine)
                .where(
                    ProcurementRequisitionLine.tenant_id == self.tenant_id,
                    ProcurementRequisitionLine.requisition_id == int(requisition_id),
                )
                .order_by(ProcurementRequisitionLine.line_no)
            ).all()
        )

    def delete_requisition_lines(self, requisition_id: int) -> None:
        self.session.execute(
            delete(ProcurementRequisitionLine).where(
                ProcurementRequisitionLine.tenant_id == self.tenant_id,
                ProcurementRequisitionLine.requisition_id == int(requisition_id),
            )
        )

    def list_requisitions(self) -> Sequence[ProcurementRequisition]:
        return list(
            self.session.scalars(
                self._scope(select(ProcurementRequisition), ProcurementRequisition).order_by(
                    ProcurementRequisition.id.desc()
                )
            ).all()
        )

    def order(self, order_id: int, *, for_update: bool = False) -> PurchaseOrder | None:
        stmt = self._scope(
            select(PurchaseOrder).where(PurchaseOrder.id == int(order_id)), PurchaseOrder
        )
        return self.session.scalar(self._lock(stmt, for_update))

    def order_lines(
        self, order_id: int, *, for_update: bool = False
    ) -> Sequence[PurchaseOrderLine]:
        stmt = (
            select(PurchaseOrderLine)
            .where(
                PurchaseOrderLine.tenant_id == self.tenant_id,
                PurchaseOrderLine.order_id == int(order_id),
            )
            .order_by(PurchaseOrderLine.line_no)
        )
        if (
            for_update
            and self.session.bind is not None
            and self.session.bind.dialect.name == "postgresql"
        ):
            stmt = stmt.with_for_update()
        return list(self.session.scalars(stmt).all())

    def list_orders(self) -> Sequence[PurchaseOrder]:
        return list(
            self.session.scalars(
                self._scope(select(PurchaseOrder), PurchaseOrder).order_by(PurchaseOrder.id.desc())
            ).all()
        )

    def receipt_by_key(self, key: str) -> GoodsReceipt | None:
        return self.session.scalar(
            select(GoodsReceipt).where(
                GoodsReceipt.tenant_id == self.tenant_id, GoodsReceipt.idempotency_key == key
            )
        )

    def receipt_lines(self, receipt_id: int) -> Sequence[GoodsReceiptLine]:
        return list(
            self.session.scalars(
                select(GoodsReceiptLine).where(
                    GoodsReceiptLine.tenant_id == self.tenant_id,
                    GoodsReceiptLine.receipt_id == int(receipt_id),
                )
            ).all()
        )

    def inventory_by_key(self, key: str) -> InventoryRequisition | None:
        return self.session.scalar(
            select(InventoryRequisition).where(
                InventoryRequisition.tenant_id == self.tenant_id,
                InventoryRequisition.idempotency_key == key,
            )
        )

    def inventory(
        self, requisition_id: int, *, for_update: bool = False
    ) -> InventoryRequisition | None:
        stmt = self._scope(
            select(InventoryRequisition).where(InventoryRequisition.id == int(requisition_id)),
            InventoryRequisition,
        )
        return self.session.scalar(self._lock(stmt, for_update))

    def inventory_lines(
        self, requisition_id: int, *, for_update: bool = False
    ) -> Sequence[InventoryRequisitionLine]:
        stmt = (
            select(InventoryRequisitionLine)
            .where(
                InventoryRequisitionLine.tenant_id == self.tenant_id,
                InventoryRequisitionLine.requisition_id == int(requisition_id),
            )
            .order_by(InventoryRequisitionLine.line_no)
        )
        if (
            for_update
            and self.session.bind is not None
            and self.session.bind.dialect.name == "postgresql"
        ):
            stmt = stmt.with_for_update()
        return list(self.session.scalars(stmt).all())

    def list_inventory(self) -> Sequence[InventoryRequisition]:
        return list(
            self.session.scalars(
                self._scope(select(InventoryRequisition), InventoryRequisition).order_by(
                    InventoryRequisition.id.desc()
                )
            ).all()
        )

    def stocktake_by_key(self, key: str) -> Stocktake | None:
        return self.session.scalar(
            select(Stocktake).where(
                Stocktake.tenant_id == self.tenant_id, Stocktake.idempotency_key == key
            )
        )

    def stocktake(self, stocktake_id: int, *, for_update: bool = False) -> Stocktake | None:
        stmt = self._scope(select(Stocktake).where(Stocktake.id == int(stocktake_id)), Stocktake)
        return self.session.scalar(self._lock(stmt, for_update))

    def stocktake_lines(self, stocktake_id: int) -> Sequence[StocktakeLine]:
        return list(
            self.session.scalars(
                select(StocktakeLine).where(
                    StocktakeLine.tenant_id == self.tenant_id,
                    StocktakeLine.stocktake_id == int(stocktake_id),
                )
            ).all()
        )

    def list_stocktakes(self) -> Sequence[Stocktake]:
        return list(
            self.session.scalars(
                self._scope(select(Stocktake), Stocktake).order_by(Stocktake.id.desc())
            ).all()
        )

    def outsourcing_by_key(self, key: str) -> OutsourcingOrder | None:
        return self.session.scalar(
            select(OutsourcingOrder).where(
                OutsourcingOrder.tenant_id == self.tenant_id,
                OutsourcingOrder.idempotency_key == key,
            )
        )

    def outsourcing(self, order_id: int, *, for_update: bool = False) -> OutsourcingOrder | None:
        stmt = self._scope(
            select(OutsourcingOrder).where(OutsourcingOrder.id == int(order_id)), OutsourcingOrder
        )
        return self.session.scalar(self._lock(stmt, for_update))

    def outsourcing_events(self, order_id: int) -> Sequence[OutsourcingEvent]:
        return list(
            self.session.scalars(
                select(OutsourcingEvent)
                .where(
                    OutsourcingEvent.tenant_id == self.tenant_id,
                    OutsourcingEvent.order_id == int(order_id),
                )
                .order_by(OutsourcingEvent.occurred_at, OutsourcingEvent.id)
            ).all()
        )

    def event_by_key(self, key: str) -> OutsourcingEvent | None:
        return self.session.scalar(
            select(OutsourcingEvent).where(
                OutsourcingEvent.tenant_id == self.tenant_id,
                OutsourcingEvent.idempotency_key == key,
            )
        )

    def list_outsourcing(self) -> Sequence[OutsourcingOrder]:
        return list(
            self.session.scalars(
                self._scope(select(OutsourcingOrder), OutsourcingOrder).order_by(
                    OutsourcingOrder.id.desc()
                )
            ).all()
        )

    def approval(self, approval_id: int | None) -> ApprovalRequest | None:
        if approval_id is None:
            return None
        return self.session.scalar(
            select(ApprovalRequest).where(
                ApprovalRequest.tenant_id == self.tenant_id, ApprovalRequest.id == int(approval_id)
            )
        )

    # ORM construction is kept inside this infrastructure boundary.
    def create_supplier(self, **values: Any) -> SupplySupplier:
        return self.add(SupplySupplier(**values))

    def create_scope(self, **values: Any) -> SupplierParkScope:
        return self.add(SupplierParkScope(**values))

    def create_qualification(self, **values: Any) -> SupplierQualification:
        return self.add(SupplierQualification(**values))

    def create_evaluation(self, **values: Any) -> SupplierEvaluation:
        return self.add(SupplierEvaluation(**values))

    def create_material(self, **values: Any) -> SupplyMaterial:
        return self.add(SupplyMaterial(**values))

    def create_warehouse(self, **values: Any) -> SupplyWarehouse:
        return self.add(SupplyWarehouse(**values))

    def create_balance(self, **values: Any) -> StockBalance:
        return self.add(StockBalance(**values))

    def create_movement(self, **values: Any) -> StockMovement:
        return self.add(StockMovement(**values))

    def create_requisition(self, **values: Any) -> ProcurementRequisition:
        return self.add(ProcurementRequisition(**values))

    def create_requisition_line(self, **values: Any) -> ProcurementRequisitionLine:
        return self.add(ProcurementRequisitionLine(**values))

    def create_order(self, **values: Any) -> PurchaseOrder:
        return self.add(PurchaseOrder(**values))

    def create_order_line(self, **values: Any) -> PurchaseOrderLine:
        return self.add(PurchaseOrderLine(**values))

    def create_receipt(self, **values: Any) -> GoodsReceipt:
        return self.add(GoodsReceipt(**values))

    def create_receipt_line(self, **values: Any) -> GoodsReceiptLine:
        return self.add(GoodsReceiptLine(**values))

    def create_inventory(self, **values: Any) -> InventoryRequisition:
        return self.add(InventoryRequisition(**values))

    def create_inventory_line(self, **values: Any) -> InventoryRequisitionLine:
        return self.add(InventoryRequisitionLine(**values))

    def create_stocktake(self, **values: Any) -> Stocktake:
        return self.add(Stocktake(**values))

    def create_stocktake_line(self, **values: Any) -> StocktakeLine:
        return self.add(StocktakeLine(**values))

    def create_outsourcing(self, **values: Any) -> OutsourcingOrder:
        return self.add(OutsourcingOrder(**values))

    def create_outsourcing_event(self, **values: Any) -> OutsourcingEvent:
        return self.add(OutsourcingEvent(**values))

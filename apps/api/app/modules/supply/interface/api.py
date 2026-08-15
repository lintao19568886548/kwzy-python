"""Strict supplier, procurement, inventory, and outsourcing REST API."""

# FastAPI dependency defaults intentionally call Depends at import time.
# ruff: noqa: B008

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.supply.application.service import SupplyService
from app.modules.supply.interface.schemas import (
    ApprovalSubmit,
    InventoryIssue,
    InventoryRequisitionCreate,
    InventoryReturn,
    MaterialCreate,
    MovementReverse,
    OutsourcingAcceptance,
    OutsourcingCreate,
    OutsourcingEventCreate,
    OutsourcingSubmit,
    ProcurementCreate,
    ProcurementDraftUpdate,
    PurchaseOrderAcknowledge,
    PurchaseOrderCreate,
    ReceiptCreate,
    StocktakeCreate,
    SupplierCreate,
    SupplierEvaluationCreate,
    SupplierQualificationCreate,
    SupplierScopeCreate,
    SupplierStatus,
    SupplyExpectedReason,
    WarehouseCreate,
)
from app.shared.deps import get_tenant_context, require_permissions
from app.shared.response import ok
from app.shared.tenant_context import TenantContext

router = APIRouter(prefix="/supply", tags=["Supply"])
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


def _svc(
    db: Session = Depends(get_db), ctx: TenantContext = Depends(get_tenant_context)
) -> SupplyService:
    return SupplyService(db, ctx)


@router.get("/overview", dependencies=[Depends(require_permissions("supply:read"))])
def overview(svc: SupplyService = Depends(_svc)) -> dict:
    return ok(svc.overview())


@router.get("/suppliers", dependencies=[Depends(require_permissions("supply:read"))])
def suppliers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = None,
    keyword: str | None = Query(default=None, max_length=100),
    svc: SupplyService = Depends(_svc),
) -> dict:
    return ok(svc.list_suppliers(page=page, page_size=page_size, status=status, keyword=keyword))


@router.post("/suppliers", dependencies=[Depends(require_permissions("supplier:manage"))])
def create_supplier(body: SupplierCreate, svc: SupplyService = Depends(_svc)) -> dict:
    return ok(svc.create_supplier(body.model_dump()), message="created")


@router.get("/suppliers/{supplier_id}", dependencies=[Depends(require_permissions("supply:read"))])
def supplier_detail(supplier_id: int, svc: SupplyService = Depends(_svc)) -> dict:
    return ok(svc.supplier_detail(supplier_id))


@router.post(
    "/suppliers/{supplier_id}/status",
    dependencies=[Depends(require_permissions("supplier:manage"))],
)
def supplier_status(
    supplier_id: int, body: SupplierStatus, svc: SupplyService = Depends(_svc)
) -> dict:
    return ok(svc.change_supplier_status(supplier_id, body.model_dump()), message="updated")


@router.post(
    "/suppliers/{supplier_id}/scopes",
    dependencies=[Depends(require_permissions("supplier:manage"))],
)
def supplier_scope(
    supplier_id: int, body: SupplierScopeCreate, svc: SupplyService = Depends(_svc)
) -> dict:
    return ok(svc.add_supplier_scope(supplier_id, body.model_dump()), message="created")


@router.post(
    "/suppliers/{supplier_id}/qualifications",
    dependencies=[Depends(require_permissions("supplier:credential"))],
)
def supplier_qualification(
    supplier_id: int, body: SupplierQualificationCreate, svc: SupplyService = Depends(_svc)
) -> dict:
    return ok(svc.add_qualification(supplier_id, body.model_dump()), message="created")


@router.post(
    "/suppliers/{supplier_id}/evaluations",
    dependencies=[Depends(require_permissions("supplier:manage"))],
)
def supplier_evaluation(
    supplier_id: int, body: SupplierEvaluationCreate, svc: SupplyService = Depends(_svc)
) -> dict:
    return ok(svc.add_evaluation(supplier_id, body.model_dump()), message="created")


@router.get("/materials", dependencies=[Depends(require_permissions("supply:read"))])
def materials(
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=200),
    status: str | None = Query(default=None, pattern="^(ACTIVE|RETIRED)$"),
    keyword: str | None = Query(default=None, max_length=100),
    svc: SupplyService = Depends(_svc),
) -> dict:
    return ok(svc.list_materials(page=page, page_size=page_size, status=status, keyword=keyword))


@router.post("/materials", dependencies=[Depends(require_permissions("inventory:manage"))])
def create_material(body: MaterialCreate, svc: SupplyService = Depends(_svc)) -> dict:
    return ok(svc.create_material(body.model_dump()), message="created")


@router.get("/warehouses", dependencies=[Depends(require_permissions("supply:read"))])
def warehouses(
    park_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=200),
    status: str | None = Query(default=None, pattern="^(ACTIVE|RETIRED)$"),
    keyword: str | None = Query(default=None, max_length=100),
    svc: SupplyService = Depends(_svc),
) -> dict:
    return ok(
        svc.list_warehouses(park_id, page=page, page_size=page_size, status=status, keyword=keyword)
    )


@router.post("/warehouses", dependencies=[Depends(require_permissions("inventory:manage"))])
def create_warehouse(body: WarehouseCreate, svc: SupplyService = Depends(_svc)) -> dict:
    return ok(svc.create_warehouse(body.model_dump()), message="created")


@router.get("/inventory/balances", dependencies=[Depends(require_permissions("supply:read"))])
def balances(
    park_id: int | None = None, warehouse_id: int | None = None, svc: SupplyService = Depends(_svc)
) -> dict:
    return ok(svc.list_balances(park_id, warehouse_id))


@router.get("/inventory/movements", dependencies=[Depends(require_permissions("supply:read"))])
def movements(
    balance_id: int | None = None,
    limit: int = Query(200, ge=1, le=1000),
    svc: SupplyService = Depends(_svc),
) -> dict:
    return ok(svc.list_movements(balance_id, limit))


@router.post(
    "/inventory/movements/{movement_id}/reverse",
    dependencies=[Depends(require_permissions("inventory:adjust"))],
)
def reverse_movement(
    movement_id: int, body: MovementReverse, key: IdempotencyKey, svc: SupplyService = Depends(_svc)
) -> dict:
    return ok(svc.reverse_movement(movement_id, body.model_dump(), key=key), message="reversed")


@router.get("/procurement/requisitions", dependencies=[Depends(require_permissions("supply:read"))])
def requisitions(svc: SupplyService = Depends(_svc)) -> dict:
    return ok(svc.list_requisitions())


@router.post(
    "/procurement/requisitions", dependencies=[Depends(require_permissions("procurement:request"))]
)
def create_requisition(
    body: ProcurementCreate, key: IdempotencyKey, svc: SupplyService = Depends(_svc)
) -> dict:
    return ok(svc.create_requisition(body.model_dump(), key=key), message="created")


@router.put(
    "/procurement/requisitions/{requisition_id}/draft",
    dependencies=[Depends(require_permissions("procurement:request"))],
)
def update_requisition_draft(
    requisition_id: int,
    body: ProcurementDraftUpdate,
    svc: SupplyService = Depends(_svc),
) -> dict:
    return ok(svc.update_requisition_draft(requisition_id, body.model_dump()), message="updated")


@router.post(
    "/procurement/requisitions/{requisition_id}/submit",
    dependencies=[Depends(require_permissions("procurement:request", "approval:write"))],
)
def submit_requisition(
    requisition_id: int,
    body: ApprovalSubmit,
    key: IdempotencyKey,
    svc: SupplyService = Depends(_svc),
) -> dict:
    return ok(
        svc.submit_requisition(requisition_id, body.model_dump(), key=key), message="submitted"
    )


@router.post(
    "/procurement/requisitions/{requisition_id}/cancel",
    dependencies=[Depends(require_permissions("procurement:request"))],
)
def cancel_requisition(
    requisition_id: int,
    body: SupplyExpectedReason,
    key: IdempotencyKey,
    svc: SupplyService = Depends(_svc),
) -> dict:
    return ok(
        svc.cancel_requisition(requisition_id, body.model_dump(), key=key), message="cancelled"
    )


@router.post(
    "/procurement/requisitions/{requisition_id}/sync",
    dependencies=[Depends(require_permissions("procurement:request"))],
)
def sync_requisition(requisition_id: int, svc: SupplyService = Depends(_svc)) -> dict:
    return ok(svc.sync_requisition(requisition_id), message="synchronized")


@router.get("/procurement/orders", dependencies=[Depends(require_permissions("supply:read"))])
def orders(svc: SupplyService = Depends(_svc)) -> dict:
    return ok(svc.list_orders())


@router.post(
    "/procurement/orders", dependencies=[Depends(require_permissions("procurement:order"))]
)
def create_order(
    body: PurchaseOrderCreate, key: IdempotencyKey, svc: SupplyService = Depends(_svc)
) -> dict:
    return ok(svc.create_order(body.model_dump(), key=key), message="created")


@router.post(
    "/procurement/orders/{order_id}/acknowledge",
    dependencies=[Depends(require_permissions("procurement:order"))],
)
def acknowledge_order(
    order_id: int, body: PurchaseOrderAcknowledge, svc: SupplyService = Depends(_svc)
) -> dict:
    return ok(svc.acknowledge_order(order_id, body.model_dump()), message="updated")


@router.post(
    "/procurement/orders/{order_id}/receipts",
    dependencies=[Depends(require_permissions("inventory:manage"))],
)
def receive_order(
    order_id: int, body: ReceiptCreate, key: IdempotencyKey, svc: SupplyService = Depends(_svc)
) -> dict:
    return ok(svc.receive_order(order_id, body.model_dump(), key=key), message="received")


@router.get("/inventory/requisitions", dependencies=[Depends(require_permissions("supply:read"))])
def inventory_requisitions(svc: SupplyService = Depends(_svc)) -> dict:
    return ok(svc.list_inventory())


@router.post(
    "/inventory/requisitions", dependencies=[Depends(require_permissions("inventory:issue"))]
)
def create_inventory_requisition(
    body: InventoryRequisitionCreate, key: IdempotencyKey, svc: SupplyService = Depends(_svc)
) -> dict:
    return ok(svc.create_inventory_requisition(body.model_dump(), key=key), message="created")


@router.post(
    "/inventory/requisitions/{requisition_id}/submit",
    dependencies=[Depends(require_permissions("inventory:issue", "approval:write"))],
)
def submit_inventory(
    requisition_id: int,
    body: ApprovalSubmit,
    key: IdempotencyKey,
    svc: SupplyService = Depends(_svc),
) -> dict:
    return ok(
        svc.submit_inventory_requisition(requisition_id, body.model_dump(), key=key),
        message="submitted",
    )


@router.post(
    "/inventory/requisitions/{requisition_id}/sync",
    dependencies=[Depends(require_permissions("inventory:issue"))],
)
def sync_inventory(requisition_id: int, svc: SupplyService = Depends(_svc)) -> dict:
    return ok(svc.sync_inventory_requisition(requisition_id), message="synchronized")


@router.post(
    "/inventory/requisitions/{requisition_id}/issue",
    dependencies=[Depends(require_permissions("inventory:issue"))],
)
def issue_inventory(
    requisition_id: int,
    body: InventoryIssue,
    key: IdempotencyKey,
    svc: SupplyService = Depends(_svc),
) -> dict:
    return ok(svc.issue_inventory(requisition_id, body.model_dump(), key=key), message="issued")


@router.post(
    "/inventory/requisitions/{requisition_id}/return",
    dependencies=[Depends(require_permissions("inventory:issue"))],
)
def return_inventory(
    requisition_id: int,
    body: InventoryReturn,
    key: IdempotencyKey,
    svc: SupplyService = Depends(_svc),
) -> dict:
    return ok(svc.return_inventory(requisition_id, body.model_dump(), key=key), message="returned")


@router.get("/inventory/stocktakes", dependencies=[Depends(require_permissions("supply:read"))])
def stocktakes(svc: SupplyService = Depends(_svc)) -> dict:
    return ok(svc.list_stocktakes())


@router.post(
    "/inventory/stocktakes", dependencies=[Depends(require_permissions("inventory:adjust"))]
)
def create_stocktake(
    body: StocktakeCreate, key: IdempotencyKey, svc: SupplyService = Depends(_svc)
) -> dict:
    return ok(svc.create_stocktake(body.model_dump(), key=key), message="created")


@router.post(
    "/inventory/stocktakes/{stocktake_id}/submit",
    dependencies=[Depends(require_permissions("inventory:adjust", "approval:write"))],
)
def submit_stocktake(
    stocktake_id: int, body: ApprovalSubmit, key: IdempotencyKey, svc: SupplyService = Depends(_svc)
) -> dict:
    return ok(svc.submit_stocktake(stocktake_id, body.model_dump(), key=key), message="submitted")


@router.post(
    "/inventory/stocktakes/{stocktake_id}/post",
    dependencies=[Depends(require_permissions("inventory:adjust"))],
)
def post_stocktake(
    stocktake_id: int, key: IdempotencyKey, svc: SupplyService = Depends(_svc)
) -> dict:
    return ok(svc.post_stocktake(stocktake_id, key=key), message="posted")


@router.get("/outsourcing/orders", dependencies=[Depends(require_permissions("supply:read"))])
def outsourcing_orders(svc: SupplyService = Depends(_svc)) -> dict:
    return ok(svc.list_outsourcing())


@router.post(
    "/outsourcing/orders", dependencies=[Depends(require_permissions("outsourcing:manage"))]
)
def create_outsourcing(
    body: OutsourcingCreate, key: IdempotencyKey, svc: SupplyService = Depends(_svc)
) -> dict:
    return ok(svc.create_outsourcing(body.model_dump(), key=key), message="created")


@router.post(
    "/outsourcing/orders/{order_id}/submit",
    dependencies=[Depends(require_permissions("outsourcing:manage", "approval:write"))],
)
def submit_outsourcing(
    order_id: int, body: OutsourcingSubmit, key: IdempotencyKey, svc: SupplyService = Depends(_svc)
) -> dict:
    return ok(svc.submit_outsourcing(order_id, body.model_dump(), key=key), message="submitted")


@router.post(
    "/outsourcing/orders/{order_id}/sync",
    dependencies=[Depends(require_permissions("outsourcing:manage"))],
)
def sync_outsourcing(order_id: int, svc: SupplyService = Depends(_svc)) -> dict:
    return ok(svc.sync_outsourcing(order_id), message="synchronized")


@router.post(
    "/outsourcing/orders/{order_id}/events",
    dependencies=[Depends(require_permissions("outsourcing:manage"))],
)
def outsourcing_event(
    order_id: int,
    body: OutsourcingEventCreate,
    key: IdempotencyKey,
    svc: SupplyService = Depends(_svc),
) -> dict:
    return ok(svc.outsourcing_event(order_id, body.model_dump(), key=key), message="recorded")


@router.post(
    "/outsourcing/orders/{order_id}/acceptance",
    dependencies=[Depends(require_permissions("outsourcing:accept"))],
)
def accept_outsourcing(
    order_id: int,
    body: OutsourcingAcceptance,
    key: IdempotencyKey,
    svc: SupplyService = Depends(_svc),
) -> dict:
    return ok(
        svc.accept_outsourcing(order_id, body.model_dump(), key=key),
        message="accepted" if body.accepted else "rework",
    )

"""功能说明：WorkOrder REST。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.facility_ops.application.work_order_service import WorkOrderService
from app.modules.facility_ops.interface.schemas import WorkOrderCreate
from app.shared.deps import get_tenant_context, require_permissions
from app.shared.response import ok
from app.shared.tenant_context import TenantContext

router = APIRouter(tags=["WorkOrders"])


def _svc(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> WorkOrderService:
    return WorkOrderService(db, ctx)


@router.get("/work-orders", dependencies=[Depends(require_permissions("work_order:read"))])
def list_work_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
    park_id: Optional[int] = None,
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    return ok(svc.list_orders(page=page, page_size=page_size, status=status, park_id=park_id))


@router.post("/work-orders")
def create_work_order(body: WorkOrderCreate, svc: WorkOrderService = Depends(_svc)) -> dict:
    return ok(svc.create_order(body.model_dump()), message="created")


@router.get(
    "/work-orders/{work_order_id}",
    dependencies=[Depends(require_permissions("work_order:read"))],
)
def get_work_order(work_order_id: int, svc: WorkOrderService = Depends(_svc)) -> dict:
    return ok(svc.get_order(work_order_id))


@router.post("/work-orders/{work_order_id}/start")
def start_work_order(work_order_id: int, svc: WorkOrderService = Depends(_svc)) -> dict:
    return ok(svc.start_order(work_order_id), message="started")


@router.post("/work-orders/{work_order_id}/complete")
def complete_work_order(work_order_id: int, svc: WorkOrderService = Depends(_svc)) -> dict:
    return ok(svc.complete_order(work_order_id), message="completed")


@router.post("/work-orders/{work_order_id}/cancel")
def cancel_work_order(work_order_id: int, svc: WorkOrderService = Depends(_svc)) -> dict:
    return ok(svc.cancel_order(work_order_id), message="cancelled")

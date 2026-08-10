"""功能说明：Bill REST 路由。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.billing.application.bill_service import BillService
from app.modules.billing.interface.schemas import BillCreate, BillUpdate
from app.shared.deps import get_tenant_context, require_permissions
from app.shared.response import ok
from app.shared.tenant_context import TenantContext

router = APIRouter(tags=["Bills"])


def _svc(db: Session = Depends(get_db), ctx: TenantContext = Depends(get_tenant_context)) -> BillService:
    return BillService(db, ctx)


@router.get("/bills", dependencies=[Depends(require_permissions("bill:read"))])
def list_bills(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
    park_id: Optional[int] = None,
    party_id: Optional[int] = None,
    svc: BillService = Depends(_svc),
) -> dict:
    """功能说明：GET /bills 分页列表。"""

    return ok(
        svc.list_bills(page=page, page_size=page_size, status=status, park_id=park_id, party_id=party_id)
    )


@router.post("/bills")
def create_bill(body: BillCreate, svc: BillService = Depends(_svc)) -> dict:
    """功能说明：POST /bills 创建草稿。"""

    return ok(svc.create_bill(body.model_dump()), message="created")


@router.get("/bills/{bill_id}", dependencies=[Depends(require_permissions("bill:read"))])
def get_bill(bill_id: int, svc: BillService = Depends(_svc)) -> dict:
    """功能说明：GET /bills/{id} 详情。"""

    return ok(svc.get_bill(bill_id))


@router.patch("/bills/{bill_id}")
def update_bill(bill_id: int, body: BillUpdate, svc: BillService = Depends(_svc)) -> dict:
    """功能说明：PATCH 草稿。"""

    return ok(svc.update_bill(bill_id, body.model_dump(exclude_unset=True)), message="updated")


@router.post("/bills/{bill_id}/issue")
def issue_bill(bill_id: int, svc: BillService = Depends(_svc)) -> dict:
    """功能说明：签发账单。"""

    return ok(svc.issue(bill_id), message="issued")


@router.post("/bills/{bill_id}/void")
def void_bill(bill_id: int, svc: BillService = Depends(_svc)) -> dict:
    """功能说明：作废未收款账单。"""

    return ok(svc.void(bill_id), message="voided")


@router.post("/bills/{bill_id}/discard")
def discard_bill(bill_id: int, svc: BillService = Depends(_svc)) -> dict:
    """功能说明：废弃草稿。"""

    return ok(svc.discard(bill_id), message="discarded")

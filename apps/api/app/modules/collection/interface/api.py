"""功能说明：Payment REST 路由。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.collection.application.collection_case_service import CollectionCaseService
from app.modules.collection.application.payment_service import PaymentService
from app.modules.collection.interface.schemas import PaymentCreate
from app.shared.deps import get_tenant_context, require_permissions
from app.shared.response import ok
from app.shared.tenant_context import TenantContext
from pydantic import BaseModel

router = APIRouter(tags=["Payments"])


def _svc(db: Session = Depends(get_db), ctx: TenantContext = Depends(get_tenant_context)) -> PaymentService:
    return PaymentService(db, ctx)


def _case_svc(
    db: Session = Depends(get_db), ctx: TenantContext = Depends(get_tenant_context)
) -> CollectionCaseService:
    return CollectionCaseService(db, ctx)


class CollectionCaseCreateBody(BaseModel):
    park_id: int
    party_id: int
    bill_id: int
    level: str = "L1"
    assignee_id: int | None = None
    remark: str | None = None


class CollectionCaseUpdateBody(BaseModel):
    status: str | None = None
    level: str | None = None
    assignee_id: int | None = None
    remark: str | None = None


@router.get("/payments", dependencies=[Depends(require_permissions("payment:read"))])
def list_payments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    party_id: Optional[int] = None,
    park_id: Optional[int] = None,
    svc: PaymentService = Depends(_svc),
) -> dict:
    """功能说明：GET /payments 列表。"""

    return ok(
        svc.list_payments(page=page, page_size=page_size, party_id=party_id, park_id=park_id)
    )


@router.post("/payments")
def create_payment(
    body: PaymentCreate,
    svc: PaymentService = Depends(_svc),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    """功能说明：POST /payments 收款登记+核销。"""

    return ok(
        svc.create_payment(body.model_dump(), idempotency_key=idempotency_key),
        message="created",
    )


@router.get("/payments/{payment_id}", dependencies=[Depends(require_permissions("payment:read"))])
def get_payment(payment_id: int, svc: PaymentService = Depends(_svc)) -> dict:
    """功能说明：GET 收款详情。"""

    return ok(svc.get_payment(payment_id))


@router.post("/payments/{payment_id}/reverse")
def reverse_payment(payment_id: int, svc: PaymentService = Depends(_svc)) -> dict:
    """功能说明：冲正收款。"""

    return ok(svc.reverse_payment(payment_id), message="reversed")


@router.get(
    "/collection/cases",
    dependencies=[Depends(require_permissions("collection:read"))],
    tags=["Collection"],
)
def list_collection_cases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
    park_id: Optional[int] = None,
    bill_id: Optional[int] = None,
    svc: CollectionCaseService = Depends(_case_svc),
) -> dict:
    return ok(
        svc.list_cases(
            page=page, page_size=page_size, status=status, park_id=park_id, bill_id=bill_id
        )
    )


@router.post("/collection/cases", tags=["Collection"])
def create_collection_case(
    body: CollectionCaseCreateBody, svc: CollectionCaseService = Depends(_case_svc)
) -> dict:
    return ok(svc.create_case(body.model_dump()), message="created")


@router.get(
    "/collection/cases/{case_id}",
    dependencies=[Depends(require_permissions("collection:read"))],
    tags=["Collection"],
)
def get_collection_case(case_id: int, svc: CollectionCaseService = Depends(_case_svc)) -> dict:
    return ok(svc.get_case(case_id))


@router.patch("/collection/cases/{case_id}", tags=["Collection"])
def update_collection_case(
    case_id: int,
    body: CollectionCaseUpdateBody,
    svc: CollectionCaseService = Depends(_case_svc),
) -> dict:
    return ok(
        svc.update_case(case_id, body.model_dump(exclude_unset=True)),
        message="updated",
    )

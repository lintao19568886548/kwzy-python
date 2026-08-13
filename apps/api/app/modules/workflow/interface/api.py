"""功能说明：审批 REST。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.workflow.application.approval_service import ApprovalService
from app.shared.deps import get_tenant_context, require_permissions
from app.shared.response import ok
from app.shared.tenant_context import TenantContext

router = APIRouter(tags=["Approvals"])


class ApprovalCreate(BaseModel):
    biz_type: str = Field(min_length=1, max_length=64)
    biz_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    park_id: Optional[int] = None
    remark: Optional[str] = None


class ApprovalDecision(BaseModel):
    remark: Optional[str] = None


def _svc(
    db: Session = Depends(get_db), ctx: TenantContext = Depends(get_tenant_context)
) -> ApprovalService:
    return ApprovalService(db, ctx)


@router.get("/approvals", dependencies=[Depends(require_permissions("approval:read"))])
def list_approvals(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
    svc: ApprovalService = Depends(_svc),
) -> dict:
    return ok(svc.list_approvals(page=page, page_size=page_size, status=status))


@router.post("/approvals")
def create_approval(body: ApprovalCreate, svc: ApprovalService = Depends(_svc)) -> dict:
    return ok(svc.create(body.model_dump()), message="created")


@router.post("/approvals/{approval_id}/approve")
def approve(
    approval_id: int,
    body: ApprovalDecision | None = None,
    svc: ApprovalService = Depends(_svc),
) -> dict:
    return ok(
        svc.decide(approval_id, approve=True, remark=body.remark if body else None),
        message="approved",
    )


@router.post("/approvals/{approval_id}/reject")
def reject(
    approval_id: int,
    body: ApprovalDecision | None = None,
    svc: ApprovalService = Depends(_svc),
) -> dict:
    return ok(
        svc.decide(approval_id, approve=False, remark=body.remark if body else None),
        message="rejected",
    )

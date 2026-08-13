"""功能说明：Lead REST 路由。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.investment.application.lead_service import LeadService
from app.modules.investment.interface.schemas import (
    LeadConvertBody,
    LeadCreate,
    LeadLoseBody,
    LeadUpdate,
)
from app.shared.deps import get_tenant_context, require_permissions
from app.shared.response import ok
from app.shared.tenant_context import TenantContext

router = APIRouter(tags=["Leads"])


def _svc(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> LeadService:
    return LeadService(db, ctx)


@router.get("/leads", dependencies=[Depends(require_permissions("lead:read"))])
def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
    park_id: Optional[int] = None,
    keyword: Optional[str] = None,
    svc: LeadService = Depends(_svc),
) -> dict:
    return ok(
        svc.list_leads(
            page=page,
            page_size=page_size,
            status=status,
            park_id=park_id,
            keyword=keyword,
        )
    )


@router.post("/leads")
def create_lead(body: LeadCreate, svc: LeadService = Depends(_svc)) -> dict:
    return ok(svc.create_lead(body.model_dump()), message="created")


@router.get("/leads/{lead_id}", dependencies=[Depends(require_permissions("lead:read"))])
def get_lead(lead_id: int, svc: LeadService = Depends(_svc)) -> dict:
    return ok(svc.get_lead(lead_id))


@router.patch("/leads/{lead_id}")
def update_lead(lead_id: int, body: LeadUpdate, svc: LeadService = Depends(_svc)) -> dict:
    return ok(
        svc.update_lead(lead_id, body.model_dump(exclude_unset=True)),
        message="updated",
    )


@router.post("/leads/{lead_id}/lose")
def lose_lead(
    lead_id: int,
    body: LeadLoseBody | None = None,
    svc: LeadService = Depends(_svc),
) -> dict:
    reason = body.reason if body else None
    return ok(svc.mark_lost(lead_id, reason=reason), message="lost")


@router.post("/leads/{lead_id}/convert")
def convert_lead(
    lead_id: int,
    body: LeadConvertBody | None = None,
    svc: LeadService = Depends(_svc),
) -> dict:
    payload = body.model_dump() if body else {}
    return ok(svc.convert_lead(lead_id, payload), message="converted")

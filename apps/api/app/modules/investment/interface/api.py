"""功能说明：Lead REST 路由。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.investment.application.lead_service import LeadService
from app.modules.investment.interface.schemas import (
    LeadActivityCreate,
    LeadAssignBody,
    LeadConvertBody,
    LeadCreate,
    LeadDuplicateQuery,
    LeadLoseBody,
    LeadMergeBody,
    LeadReopenBody,
    LeadUpdate,
    LeadUnitLockCommand,
    LeadUnitLockCreate,
    LeadVersionBody,
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
    owner_user_id: Optional[int] = None,
    pool_status: Optional[str] = None,
    source_type: Optional[str] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    svc: LeadService = Depends(_svc),
) -> dict:
    return ok(
        svc.list_leads(
            page=page,
            page_size=page_size,
            status=status,
            park_id=park_id,
            keyword=keyword,
            owner_user_id=owner_user_id,
            pool_status=pool_status,
            source_type=source_type,
            created_from=created_from,
            created_to=created_to,
        )
    )


@router.post("/leads")
def create_lead(body: LeadCreate, svc: LeadService = Depends(_svc)) -> dict:
    return ok(svc.create_lead(body.model_dump()), message="created")


@router.post("/leads/duplicates/check")
def duplicate_candidates(body: LeadDuplicateQuery, svc: LeadService = Depends(_svc)) -> dict:
    return ok(svc.duplicate_candidates(body.model_dump()))


@router.get("/crm/assignees")
def list_assignees(svc: LeadService = Depends(_svc)) -> dict:
    return ok(svc.list_assignees())


@router.post("/crm/unit-locks/sweep")
def sweep_expired_unit_locks(
    park_id: Optional[int] = None,
    svc: LeadService = Depends(_svc),
) -> dict:
    return ok(svc.sweep_expired_unit_locks(park_id=park_id), message="swept")


@router.get("/crm/summary", dependencies=[Depends(require_permissions("lead:read"))])
def crm_summary(
    status: Optional[str] = None,
    park_id: Optional[int] = None,
    keyword: Optional[str] = None,
    owner_user_id: Optional[int] = None,
    pool_status: Optional[str] = None,
    source_type: Optional[str] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    svc: LeadService = Depends(_svc),
) -> dict:
    return ok(
        svc.crm_summary(
            status=status,
            park_id=park_id,
            keyword=keyword,
            owner_user_id=owner_user_id,
            pool_status=pool_status,
            source_type=source_type,
            created_from=created_from,
            created_to=created_to,
        )
    )


@router.get("/crm/board", dependencies=[Depends(require_permissions("lead:read"))])
def crm_board(
    status: Optional[str] = None,
    park_id: Optional[int] = None,
    keyword: Optional[str] = None,
    owner_user_id: Optional[int] = None,
    pool_status: Optional[str] = None,
    source_type: Optional[str] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    svc: LeadService = Depends(_svc),
) -> dict:
    return ok(
        svc.crm_board(
            status=status,
            park_id=park_id,
            keyword=keyword,
            owner_user_id=owner_user_id,
            pool_status=pool_status,
            source_type=source_type,
            created_from=created_from,
            created_to=created_to,
        )
    )


@router.get("/leads/{lead_id}", dependencies=[Depends(require_permissions("lead:read"))])
def get_lead(lead_id: int, svc: LeadService = Depends(_svc)) -> dict:
    return ok(svc.get_lead(lead_id))


@router.get("/leads/{lead_id}/unit-matches")
def match_units(
    lead_id: int,
    limit: int = Query(50, ge=1, le=200),
    svc: LeadService = Depends(_svc),
) -> dict:
    return ok(svc.match_units(lead_id, limit=limit))


@router.post("/leads/{lead_id}/unit-locks")
def acquire_unit_lock(
    lead_id: int,
    body: LeadUnitLockCreate,
    svc: LeadService = Depends(_svc),
) -> dict:
    return ok(
        svc.acquire_unit_lock(
            lead_id,
            unit_id=body.unit_id,
            expected_version=body.expected_version,
            duration_hours=body.duration_hours,
        ),
        message="locked",
    )


@router.post("/leads/{lead_id}/unit-locks/{lock_id}/release")
def release_unit_lock(
    lead_id: int,
    lock_id: int,
    body: LeadUnitLockCommand,
    svc: LeadService = Depends(_svc),
) -> dict:
    return ok(
        svc.release_unit_lock(
            lead_id,
            lock_id,
            expected_version=body.expected_version,
        ),
        message="released",
    )


@router.post("/leads/{lead_id}/unit-locks/{lock_id}/renew")
def renew_unit_lock(
    lead_id: int,
    lock_id: int,
    body: LeadUnitLockCommand,
    svc: LeadService = Depends(_svc),
) -> dict:
    return ok(
        svc.renew_unit_lock(
            lead_id,
            lock_id,
            expected_version=body.expected_version,
            duration_hours=body.duration_hours,
        ),
        message="renewed",
    )


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
    if body is None:
        return ok(
            svc.mark_lost(lead_id, reason=None, expected_version=None),
            message="lost",
        )
    return ok(
        svc.mark_lost(
            lead_id,
            reason=body.reason,
            expected_version=body.expected_version,
        ),
        message="lost",
    )


@router.post("/leads/{lead_id}/activities")
def add_activity(
    lead_id: int,
    body: LeadActivityCreate,
    svc: LeadService = Depends(_svc),
) -> dict:
    return ok(svc.add_activity(lead_id, body.model_dump()), message="activity_created")


@router.post("/leads/{lead_id}/assign")
def assign_lead(lead_id: int, body: LeadAssignBody, svc: LeadService = Depends(_svc)) -> dict:
    return ok(
        svc.assign_lead(
            lead_id,
            owner_user_id=body.owner_user_id,
            expected_version=body.expected_version,
            reason=body.reason,
        ),
        message="assigned",
    )


@router.post("/leads/{lead_id}/claim")
def claim_lead(lead_id: int, body: LeadVersionBody, svc: LeadService = Depends(_svc)) -> dict:
    return ok(svc.claim_lead(lead_id, expected_version=body.expected_version), message="claimed")


@router.post("/leads/{lead_id}/release")
def release_lead(lead_id: int, body: LeadVersionBody, svc: LeadService = Depends(_svc)) -> dict:
    return ok(
        svc.release_lead(
            lead_id,
            expected_version=body.expected_version,
            reason=body.reason,
        ),
        message="released",
    )


@router.post("/leads/{lead_id}/recycle")
def recycle_lead(lead_id: int, body: LeadVersionBody, svc: LeadService = Depends(_svc)) -> dict:
    return ok(svc.recycle_lead(lead_id, expected_version=body.expected_version), message="recycled")


@router.post("/leads/{lead_id}/reopen")
def reopen_lead(lead_id: int, body: LeadReopenBody, svc: LeadService = Depends(_svc)) -> dict:
    return ok(
        svc.reopen_lead(
            lead_id,
            expected_version=body.expected_version,
            reason=body.reason,
            target_status=body.target_status,
        ),
        message="reopened",
    )


@router.post("/leads/{lead_id}/merge")
def merge_lead(lead_id: int, body: LeadMergeBody, svc: LeadService = Depends(_svc)) -> dict:
    return ok(
        svc.merge_leads(
            lead_id,
            target_id=body.target_lead_id,
            source_version=body.expected_version,
            target_version=body.target_expected_version,
            reason=body.reason,
        ),
        message="merged",
    )


@router.post("/leads/{lead_id}/convert")
def convert_lead(
    lead_id: int,
    body: LeadConvertBody | None = None,
    svc: LeadService = Depends(_svc),
) -> dict:
    payload = body.model_dump() if body else {}
    return ok(svc.convert_lead(lead_id, payload), message="converted")

"""功能说明：Lead REST 路由。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.investment.application.lead_service import LeadService
from app.modules.investment.application.assignment_service import AssignmentRuleService
from app.modules.investment.application.channel_service import (
    MAX_CHANNEL_BODY_BYTES,
    ChannelService,
    PublicChannelIntake,
)
from app.modules.investment.application.intent_service import IntentService
from app.modules.investment.application.viewing_service import ViewingService
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
    AssignmentRuleCreate,
    AssignmentRuleDraftUpdate,
    ChannelCreate,
    ChannelUpdate,
    ExpectedLockVersion,
    IntentCreate,
    IntentSubmit,
    IntentVersionCreate,
    ViewingCreate,
    ViewingReschedule,
    ViewingTransition,
)
from app.core.errors import AppError
from app.shared.deps import get_tenant_context, require_permissions
from app.shared.response import ok
from app.shared.tenant_context import TenantContext

router = APIRouter(tags=["Leads"])


def _svc(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> LeadService:
    return LeadService(db, ctx)


def _assignment_svc(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> AssignmentRuleService:
    return AssignmentRuleService(db, ctx)


def _viewing_svc(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> ViewingService:
    return ViewingService(db, ctx)


def _intent_svc(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> IntentService:
    return IntentService(db, ctx)


def _channel_svc(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> ChannelService:
    return ChannelService(db, ctx)


@router.get("/crm/assignment-rules")
def list_assignment_rules(
    park_id: Optional[int] = None,
    svc: AssignmentRuleService = Depends(_assignment_svc),
) -> dict:
    return ok(svc.list_rules(park_id=park_id))


@router.get("/crm/assignment-rules/preview")
def preview_assignment_rule(
    park_id: int,
    trigger: str,
    svc: AssignmentRuleService = Depends(_assignment_svc),
) -> dict:
    return ok(svc.preview(park_id=park_id, trigger=trigger))


@router.post("/crm/assignment-rules")
def create_assignment_rule(
    body: AssignmentRuleCreate,
    svc: AssignmentRuleService = Depends(_assignment_svc),
) -> dict:
    return ok(svc.create_rule(body.model_dump()), message="created")


@router.get("/crm/assignment-rules/{rule_id}")
def get_assignment_rule(
    rule_id: int, svc: AssignmentRuleService = Depends(_assignment_svc)
) -> dict:
    return ok(svc.get_rule(rule_id))


@router.patch("/crm/assignment-rules/{rule_id}/draft")
def update_assignment_rule_draft(
    rule_id: int,
    body: AssignmentRuleDraftUpdate,
    svc: AssignmentRuleService = Depends(_assignment_svc),
) -> dict:
    return ok(svc.update_draft(rule_id, body.model_dump(exclude_unset=True)), message="updated")


@router.post("/crm/assignment-rules/{rule_id}/draft")
def create_assignment_rule_draft(
    rule_id: int,
    body: ExpectedLockVersion,
    svc: AssignmentRuleService = Depends(_assignment_svc),
) -> dict:
    return ok(
        svc.create_draft(rule_id, expected_lock_version=body.expected_lock_version),
        message="created",
    )


@router.post("/crm/assignment-rules/{rule_id}/publish")
def publish_assignment_rule(
    rule_id: int,
    body: ExpectedLockVersion,
    svc: AssignmentRuleService = Depends(_assignment_svc),
) -> dict:
    return ok(
        svc.publish(rule_id, expected_lock_version=body.expected_lock_version),
        message="published",
    )


@router.post("/crm/assignment-rules/{rule_id}/retire")
def retire_assignment_rule(
    rule_id: int,
    body: ExpectedLockVersion,
    svc: AssignmentRuleService = Depends(_assignment_svc),
) -> dict:
    return ok(
        svc.retire(rule_id, expected_lock_version=body.expected_lock_version),
        message="retired",
    )


@router.get("/leads/{lead_id}/viewings")
def list_lead_viewings(lead_id: int, svc: ViewingService = Depends(_viewing_svc)) -> dict:
    return ok(svc.list_for_lead(lead_id))


@router.post("/leads/{lead_id}/viewings")
def create_lead_viewing(
    lead_id: int, body: ViewingCreate, svc: ViewingService = Depends(_viewing_svc)
) -> dict:
    return ok(svc.create(lead_id, body.model_dump()), message="created")


@router.get("/crm/viewings/{viewing_id}")
def get_lead_viewing(viewing_id: int, svc: ViewingService = Depends(_viewing_svc)) -> dict:
    return ok(svc.get(viewing_id))


@router.patch("/crm/viewings/{viewing_id}")
def reschedule_lead_viewing(
    viewing_id: int,
    body: ViewingReschedule,
    svc: ViewingService = Depends(_viewing_svc),
) -> dict:
    return ok(
        svc.reschedule(viewing_id, body.model_dump(exclude_unset=True)), message="rescheduled"
    )


@router.post("/crm/viewings/{viewing_id}/transition")
def transition_lead_viewing(
    viewing_id: int,
    body: ViewingTransition,
    svc: ViewingService = Depends(_viewing_svc),
) -> dict:
    return ok(svc.transition(viewing_id, body.model_dump()), message="transitioned")


@router.get("/leads/{lead_id}/intent")
def get_lead_intent(lead_id: int, svc: IntentService = Depends(_intent_svc)) -> dict:
    return ok(svc.get_for_lead(lead_id))


@router.post("/leads/{lead_id}/intent")
def create_lead_intent(
    lead_id: int, body: IntentCreate, svc: IntentService = Depends(_intent_svc)
) -> dict:
    return ok(svc.create(lead_id, body.model_dump()), message="created")


@router.get("/crm/intents/{intent_id}")
def get_lead_intent_detail(intent_id: int, svc: IntentService = Depends(_intent_svc)) -> dict:
    return ok(svc.get(intent_id))


@router.post("/crm/intents/{intent_id}/versions")
def create_lead_intent_version(
    intent_id: int,
    body: IntentVersionCreate,
    svc: IntentService = Depends(_intent_svc),
) -> dict:
    return ok(svc.create_version(intent_id, body.model_dump()), message="created")


@router.post("/crm/intents/{intent_id}/submit")
def submit_lead_intent(
    intent_id: int,
    body: IntentSubmit,
    svc: IntentService = Depends(_intent_svc),
) -> dict:
    return ok(svc.submit(intent_id, body.model_dump()), message="submitted")


@router.get("/crm/channels")
def list_lead_channels(svc: ChannelService = Depends(_channel_svc)) -> dict:
    return ok(svc.list())


@router.post("/crm/channels")
def create_lead_channel(
    body: ChannelCreate, svc: ChannelService = Depends(_channel_svc)
) -> dict:
    return ok(svc.create(body.model_dump()), message="created")


@router.get("/crm/channels/{channel_id}")
def get_lead_channel(channel_id: int, svc: ChannelService = Depends(_channel_svc)) -> dict:
    return ok(svc.get(channel_id))


@router.patch("/crm/channels/{channel_id}")
def update_lead_channel(
    channel_id: int, body: ChannelUpdate, svc: ChannelService = Depends(_channel_svc)
) -> dict:
    return ok(svc.update(channel_id, body.model_dump(exclude_unset=True)), message="updated")


@router.get("/crm/channels/{channel_id}/events")
def list_lead_channel_events(
    channel_id: int,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=200),
    svc: ChannelService = Depends(_channel_svc),
) -> dict:
    return ok(svc.list_events(channel_id, status=status, limit=limit))


@router.post("/crm/channels/{channel_id}/events/{event_id}/replay")
def replay_lead_channel_event(
    channel_id: int,
    event_id: int,
    svc: ChannelService = Depends(_channel_svc),
) -> dict:
    return ok(svc.replay(channel_id, event_id), message="replayed")


@router.post("/public/lead-channels/{public_id}/events")
async def receive_lead_channel_event(
    public_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    content_lengths = request.headers.getlist("content-length")
    if len(content_lengths) > 1:
        raise AppError("渠道认证失败", code="CHANNEL_AUTH_FAILED", status_code=401)
    if content_lengths:
        try:
            if int(content_lengths[0]) > MAX_CHANNEL_BODY_BYTES:
                raise AppError("渠道认证失败", code="CHANNEL_AUTH_FAILED", status_code=401)
        except ValueError as exc:
            raise AppError("渠道认证失败", code="CHANNEL_AUTH_FAILED", status_code=401) from exc
    names = {
        "timestamp": request.headers.getlist("x-kwzy-timestamp"),
        "event": request.headers.getlist("x-kwzy-event-id"),
        "signature": request.headers.getlist("x-kwzy-signature"),
    }
    if any(len(values) != 1 for values in names.values()):
        raise AppError("渠道认证失败", code="CHANNEL_AUTH_FAILED", status_code=401)
    raw_body = await request.body()
    return ok(
        PublicChannelIntake(db).receive(
            public_id=public_id,
            raw_body=raw_body,
            timestamp=names["timestamp"][0],
            external_event_id=names["event"][0],
            signature=names["signature"][0],
        ),
        message="received",
    )


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
            intent_id=body.intent_id,
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
            intent_id=int(body.intent_id or 0),
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

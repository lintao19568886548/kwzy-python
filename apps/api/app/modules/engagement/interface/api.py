"""Strict staff and tenant-principal engagement REST API."""

# FastAPI dependency defaults intentionally call Depends at import time.
# ruff: noqa: B008

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.engagement.application.service import EngagementService
from app.modules.engagement.interface.schemas import (
    ActivityCreate,
    ActivityLifecycle,
    ActivityRevision,
    AnnouncementCreate,
    AnnouncementRevision,
    ApprovalSubmit,
    CheckIn,
    ExpectedVersion,
    FanoutRequest,
    FeedbackCreate,
    LifecycleAction,
    OperationalSweep,
    PolicyConsultationCreate,
    PolicyCreate,
    PolicyExpirySweep,
    PolicyRevision,
    RegistrationCancel,
    RegistrationCreate,
    ServiceCaseCreate,
    ServiceCaseTransition,
    ServiceCreate,
    ServiceRevision,
    StaffServiceCaseCreate,
)
from app.shared.deps import get_tenant_context, require_permissions
from app.shared.response import ok
from app.shared.tenant_context import TenantContext

router = APIRouter(prefix="/engagement", tags=["Engagement"])
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


def _svc(
    db: Session = Depends(get_db), ctx: TenantContext = Depends(get_tenant_context)
) -> EngagementService:
    return EngagementService(db, ctx)


@router.get("/overview", dependencies=[Depends(require_permissions("engagement:read"))])
def overview(svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.overview())


# Staff policy governance
@router.get("/staff/policies", dependencies=[Depends(require_permissions("engagement:read"))])
def staff_policies(svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.list_policies())


@router.post(
    "/staff/policies", dependencies=[Depends(require_permissions("engagement:policy_manage"))]
)
def create_policy(body: PolicyCreate, svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.create_policy(body.model_dump()), message="created")


@router.put(
    "/staff/policies/{policy_id}/draft",
    dependencies=[Depends(require_permissions("engagement:policy_manage"))],
)
def revise_policy(
    policy_id: int,
    body: PolicyRevision,
    key: IdempotencyKey,
    svc: EngagementService = Depends(_svc),
) -> dict:
    return ok(svc.revise_policy(policy_id, body.model_dump(), key=key), message="revised")


@router.get(
    "/staff/policies/{policy_id}", dependencies=[Depends(require_permissions("engagement:read"))]
)
def staff_policy(policy_id: int, svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.get_policy(policy_id))


@router.post(
    "/staff/policies/{policy_id}/submit",
    dependencies=[Depends(require_permissions("engagement:policy_manage"))],
)
def submit_policy(
    policy_id: int,
    body: ApprovalSubmit,
    key: IdempotencyKey,
    svc: EngagementService = Depends(_svc),
) -> dict:
    return ok(svc.submit_policy(policy_id, body.model_dump(), key=key), message="submitted")


@router.post(
    "/staff/policies/{policy_id}/publish",
    dependencies=[Depends(require_permissions("engagement:policy_manage"))],
)
def publish_policy(
    policy_id: int, body: ExpectedVersion, svc: EngagementService = Depends(_svc)
) -> dict:
    return ok(svc.publish_policy(policy_id, body.model_dump()), message="published")


@router.post(
    "/staff/policies/{policy_id}/withdraw",
    dependencies=[Depends(require_permissions("engagement:policy_manage"))],
)
def withdraw_policy(
    policy_id: int,
    body: LifecycleAction,
    key: IdempotencyKey,
    svc: EngagementService = Depends(_svc),
) -> dict:
    return ok(svc.withdraw_policy(policy_id, body.model_dump(), key=key), message="withdrawn")


@router.post(
    "/staff/policies/expire-due",
    dependencies=[Depends(require_permissions("engagement:policy_manage"))],
)
def expire_policies(body: PolicyExpirySweep, svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.expire_policies(due_on=body.due_on, limit=body.limit), message="processed")


# Tenant policy projection
@router.get("/tenant/policies", dependencies=[Depends(require_permissions("engagement:read"))])
def tenant_policies(svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.list_policies(tenant_view=True))


@router.get(
    "/tenant/policies/{policy_id}", dependencies=[Depends(require_permissions("engagement:read"))]
)
def tenant_policy(policy_id: int, svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.get_policy(policy_id, tenant_view=True))


@router.post(
    "/tenant/policies/{policy_id}/match",
    dependencies=[Depends(require_permissions("engagement:read"))],
)
def match_policy(
    policy_id: int, key: IdempotencyKey, svc: EngagementService = Depends(_svc)
) -> dict:
    return ok(svc.match_policy(policy_id, key=key))


@router.post(
    "/tenant/policies/{policy_id}/follow",
    dependencies=[Depends(require_permissions("engagement:read"))],
)
def follow_policy(policy_id: int, svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.follow_policy(policy_id, active=True), message="followed")


@router.post(
    "/tenant/policies/{policy_id}/unfollow",
    dependencies=[Depends(require_permissions("engagement:read"))],
)
def unfollow_policy(policy_id: int, svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.follow_policy(policy_id, active=False), message="unfollowed")


@router.post(
    "/tenant/policies/{policy_id}/consultations",
    dependencies=[Depends(require_permissions("engagement:read"))],
)
def create_consultation(
    policy_id: int,
    body: PolicyConsultationCreate,
    key: IdempotencyKey,
    svc: EngagementService = Depends(_svc),
) -> dict:
    return ok(svc.create_consultation(policy_id, body.model_dump(), key=key), message="created")


# Staff service catalogue and cases
@router.get("/staff/services", dependencies=[Depends(require_permissions("engagement:read"))])
def staff_services(svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.list_services())


@router.post(
    "/staff/services", dependencies=[Depends(require_permissions("engagement:service_manage"))]
)
def create_service(body: ServiceCreate, svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.create_service(body.model_dump()), message="created")


@router.put(
    "/staff/services/{catalog_id}/draft",
    dependencies=[Depends(require_permissions("engagement:service_manage"))],
)
def revise_service(
    catalog_id: int,
    body: ServiceRevision,
    key: IdempotencyKey,
    svc: EngagementService = Depends(_svc),
) -> dict:
    return ok(svc.revise_service(catalog_id, body.model_dump(), key=key), message="revised")


@router.post(
    "/staff/services/{catalog_id}/submit",
    dependencies=[Depends(require_permissions("engagement:service_manage"))],
)
def submit_service(
    catalog_id: int,
    body: ApprovalSubmit,
    key: IdempotencyKey,
    svc: EngagementService = Depends(_svc),
) -> dict:
    return ok(svc.submit_service(catalog_id, body.model_dump(), key=key), message="submitted")


@router.post(
    "/staff/services/{catalog_id}/publish",
    dependencies=[Depends(require_permissions("engagement:service_manage"))],
)
def publish_service(
    catalog_id: int, body: ExpectedVersion, svc: EngagementService = Depends(_svc)
) -> dict:
    return ok(svc.publish_service(catalog_id, body.model_dump()), message="published")


@router.get("/staff/service-cases", dependencies=[Depends(require_permissions("engagement:read"))])
def staff_cases(svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.list_cases())


@router.post(
    "/staff/service-cases",
    dependencies=[Depends(require_permissions("engagement:service_manage"))],
)
def create_case_on_behalf(
    body: StaffServiceCaseCreate,
    key: IdempotencyKey,
    svc: EngagementService = Depends(_svc),
) -> dict:
    return ok(svc.create_case(body.model_dump(), key=key, staff_on_behalf=True), message="created")


@router.post(
    "/staff/service-cases/{case_id}/transition",
    dependencies=[Depends(require_permissions("engagement:service_manage"))],
)
def transition_staff_case(
    case_id: int,
    body: ServiceCaseTransition,
    key: IdempotencyKey,
    svc: EngagementService = Depends(_svc),
) -> dict:
    return ok(svc.transition_case(case_id, body.model_dump(), key=key), message="transitioned")


@router.post(
    "/staff/service-cases/escalate-sla",
    dependencies=[Depends(require_permissions("engagement:service_manage"))],
)
def escalate_service_sla(
    body: OperationalSweep, svc: EngagementService = Depends(_svc)
) -> dict:
    return ok(
        svc.escalate_service_sla(due_at=body.due_at, limit=body.limit),
        message="processed",
    )


# Tenant service cases
@router.get("/tenant/services", dependencies=[Depends(require_permissions("engagement:read"))])
def tenant_services(svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.list_services(tenant_view=True))


@router.get("/tenant/service-cases", dependencies=[Depends(require_permissions("engagement:read"))])
def tenant_cases(svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.list_cases(tenant_view=True))


@router.post(
    "/tenant/service-cases",
    dependencies=[Depends(require_permissions("engagement:service_request"))],
)
def create_case(
    body: ServiceCaseCreate,
    key: IdempotencyKey,
    svc: EngagementService = Depends(_svc),
) -> dict:
    return ok(svc.create_case(body.model_dump(), key=key), message="created")


@router.post(
    "/tenant/service-cases/{case_id}/transition",
    dependencies=[Depends(require_permissions("engagement:service_request"))],
)
def transition_tenant_case(
    case_id: int,
    body: ServiceCaseTransition,
    key: IdempotencyKey,
    svc: EngagementService = Depends(_svc),
) -> dict:
    return ok(
        svc.transition_case(case_id, body.model_dump(), key=key, tenant_view=True),
        message="transitioned",
    )


@router.post(
    "/tenant/service-cases/{case_id}/feedback",
    dependencies=[Depends(require_permissions("engagement:service_request"))],
)
def feedback_case(
    case_id: int, body: FeedbackCreate, svc: EngagementService = Depends(_svc)
) -> dict:
    return ok(svc.feedback_case(case_id, body.model_dump()), message="created")


# Staff activities
@router.get("/staff/activities", dependencies=[Depends(require_permissions("engagement:read"))])
def staff_activities(svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.list_activities())


@router.post(
    "/staff/activities", dependencies=[Depends(require_permissions("engagement:activity_manage"))]
)
def create_activity(body: ActivityCreate, svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.create_activity(body.model_dump()), message="created")


@router.put(
    "/staff/activities/{activity_id}/draft",
    dependencies=[Depends(require_permissions("engagement:activity_manage"))],
)
def revise_activity(
    activity_id: int,
    body: ActivityRevision,
    key: IdempotencyKey,
    svc: EngagementService = Depends(_svc),
) -> dict:
    return ok(svc.revise_activity(activity_id, body.model_dump(), key=key), message="revised")


@router.post(
    "/staff/activities/{activity_id}/submit",
    dependencies=[Depends(require_permissions("engagement:activity_manage"))],
)
def submit_activity(
    activity_id: int,
    body: ApprovalSubmit,
    key: IdempotencyKey,
    svc: EngagementService = Depends(_svc),
) -> dict:
    return ok(svc.submit_activity(activity_id, body.model_dump(), key=key), message="submitted")


@router.post(
    "/staff/activities/{activity_id}/publish",
    dependencies=[Depends(require_permissions("engagement:activity_manage"))],
)
def publish_activity(
    activity_id: int, body: ExpectedVersion, svc: EngagementService = Depends(_svc)
) -> dict:
    return ok(svc.publish_activity(activity_id, body.model_dump()), message="published")


@router.post(
    "/staff/activities/{activity_id}/transition",
    dependencies=[Depends(require_permissions("engagement:activity_manage"))],
)
def transition_activity(
    activity_id: int,
    body: ActivityLifecycle,
    key: IdempotencyKey,
    svc: EngagementService = Depends(_svc),
) -> dict:
    return ok(
        svc.transition_activity(activity_id, body.model_dump(), key=key),
        message="transitioned",
    )


@router.get(
    "/staff/activity-registrations",
    dependencies=[Depends(require_permissions("engagement:read"))],
)
def staff_registrations(svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.list_registrations())


@router.post(
    "/staff/activity-registrations/{registration_id}/check-in",
    dependencies=[Depends(require_permissions("engagement:activity_manage"))],
)
def check_in(
    registration_id: int,
    body: CheckIn,
    key: IdempotencyKey,
    svc: EngagementService = Depends(_svc),
) -> dict:
    return ok(svc.check_in(registration_id, body.model_dump(), key=key), message="checked_in")


# Tenant activities
@router.get("/tenant/activities", dependencies=[Depends(require_permissions("engagement:read"))])
def tenant_activities(svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.list_activities(tenant_view=True))


@router.get(
    "/tenant/activity-registrations",
    dependencies=[Depends(require_permissions("engagement:read"))],
)
def tenant_registrations(svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.list_registrations(tenant_view=True))


@router.post(
    "/tenant/activities/{activity_id}/registrations",
    dependencies=[Depends(require_permissions("engagement:activity_register"))],
)
def register_activity(
    activity_id: int,
    body: RegistrationCreate,
    key: IdempotencyKey,
    svc: EngagementService = Depends(_svc),
) -> dict:
    return ok(svc.register_activity(activity_id, body.model_dump(), key=key), message="registered")


@router.post(
    "/tenant/activity-registrations/{registration_id}/cancel",
    dependencies=[Depends(require_permissions("engagement:activity_register"))],
)
def cancel_registration(
    registration_id: int,
    body: RegistrationCancel,
    key: IdempotencyKey,
    svc: EngagementService = Depends(_svc),
) -> dict:
    return ok(
        svc.cancel_registration(registration_id, body.model_dump(), key=key),
        message="cancelled",
    )


@router.post(
    "/tenant/activity-registrations/{registration_id}/feedback",
    dependencies=[Depends(require_permissions("engagement:activity_register"))],
)
def feedback_activity(
    registration_id: int, body: FeedbackCreate, svc: EngagementService = Depends(_svc)
) -> dict:
    return ok(svc.feedback_activity(registration_id, body.model_dump()), message="created")


# Announcements
@router.get("/staff/announcements", dependencies=[Depends(require_permissions("engagement:read"))])
def staff_announcements(svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.list_announcements())


@router.post(
    "/staff/announcements",
    dependencies=[Depends(require_permissions("engagement:announcement_manage"))],
)
def create_announcement(body: AnnouncementCreate, svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.create_announcement(body.model_dump()), message="created")


@router.put(
    "/staff/announcements/{announcement_id}/draft",
    dependencies=[Depends(require_permissions("engagement:announcement_manage"))],
)
def revise_announcement(
    announcement_id: int,
    body: AnnouncementRevision,
    key: IdempotencyKey,
    svc: EngagementService = Depends(_svc),
) -> dict:
    return ok(
        svc.revise_announcement(announcement_id, body.model_dump(), key=key),
        message="revised",
    )


@router.post(
    "/staff/announcements/{announcement_id}/submit",
    dependencies=[Depends(require_permissions("engagement:announcement_manage"))],
)
def submit_announcement(
    announcement_id: int,
    body: ApprovalSubmit,
    key: IdempotencyKey,
    svc: EngagementService = Depends(_svc),
) -> dict:
    return ok(
        svc.submit_announcement(announcement_id, body.model_dump(), key=key),
        message="submitted",
    )


@router.post(
    "/staff/announcements/{announcement_id}/publish",
    dependencies=[Depends(require_permissions("engagement:announcement_manage"))],
)
def publish_announcement(
    announcement_id: int, body: ExpectedVersion, svc: EngagementService = Depends(_svc)
) -> dict:
    return ok(svc.publish_announcement(announcement_id, body.model_dump()), message="published")


@router.post(
    "/staff/announcements/{announcement_id}/withdraw",
    dependencies=[Depends(require_permissions("engagement:announcement_manage"))],
)
def withdraw_announcement(
    announcement_id: int,
    body: LifecycleAction,
    key: IdempotencyKey,
    svc: EngagementService = Depends(_svc),
) -> dict:
    return ok(
        svc.withdraw_announcement(announcement_id, body.model_dump(), key=key),
        message="withdrawn",
    )


@router.post(
    "/staff/announcements/process-due",
    dependencies=[Depends(require_permissions("engagement:announcement_manage"))],
)
def process_due_announcements(
    body: OperationalSweep, svc: EngagementService = Depends(_svc)
) -> dict:
    return ok(
        svc.process_due_announcements(due_at=body.due_at, limit=body.limit),
        message="processed",
    )


@router.post(
    "/staff/announcements/fanout",
    dependencies=[Depends(require_permissions("engagement:announcement_manage"))],
)
def fanout(body: FanoutRequest, svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.fanout_announcements(limit=body.limit), message="processed")


@router.get("/tenant/announcements", dependencies=[Depends(require_permissions("engagement:read"))])
def tenant_announcements(svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.list_announcements(tenant_view=True))


@router.get(
    "/tenant/announcement-inbox", dependencies=[Depends(require_permissions("engagement:read"))]
)
def announcement_inbox(svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.inbox())


@router.post(
    "/tenant/announcement-inbox/{delivery_id}/read",
    dependencies=[Depends(require_permissions("engagement:read"))],
)
def read_announcement(delivery_id: int, svc: EngagementService = Depends(_svc)) -> dict:
    return ok(svc.read_delivery(delivery_id), message="read")

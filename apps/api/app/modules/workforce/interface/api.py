"""Strict workforce REST API."""

# FastAPI dependency defaults intentionally call Depends at import time.
# ruff: noqa: B008

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.workforce.application.service import WorkforceService
from app.modules.workforce.interface.schemas import (
    AssignmentCreate,
    CycleStatus,
    EmployeeCreate,
    EmployeeStatus,
    EmployeeUpdate,
    ExpectedReason,
    GoalCreate,
    LeaveCreate,
    LocationCreate,
    PerformanceCycleCreate,
    PolicyCreate,
    PunchCreate,
    QualificationCreate,
    QualificationRevoke,
    QualificationSweep,
    QualificationTypeCreate,
    ReviewAcknowledge,
    ReviewCreate,
    ReviewPublish,
    ShiftCreate,
    ShiftVersionCreate,
    SummaryAdjust,
    SummaryGenerate,
)
from app.shared.deps import get_tenant_context, require_permissions
from app.shared.response import ok
from app.shared.tenant_context import TenantContext

router = APIRouter(prefix="/workforce", tags=["Workforce"])
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


def _svc(
    db: Session = Depends(get_db), ctx: TenantContext = Depends(get_tenant_context)
) -> WorkforceService:
    return WorkforceService(db, ctx)


@router.get("/overview", dependencies=[Depends(require_permissions("workforce:read"))])
def overview(svc: WorkforceService = Depends(_svc)) -> dict:
    return ok(svc.overview())


@router.get("/employees", dependencies=[Depends(require_permissions("workforce:read"))])
def list_employees(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    park_id: int | None = None,
    status: str | None = None,
    keyword: str | None = Query(default=None, max_length=100),
    svc: WorkforceService = Depends(_svc),
) -> dict:
    return ok(
        svc.list_employees(
            page=page, page_size=page_size, park_id=park_id, status=status, keyword=keyword
        )
    )


@router.post("/employees", dependencies=[Depends(require_permissions("workforce:manage"))])
def create_employee(body: EmployeeCreate, svc: WorkforceService = Depends(_svc)) -> dict:
    return ok(svc.create_employee(body.model_dump()), message="created")


@router.get(
    "/employees/{employee_id}", dependencies=[Depends(require_permissions("workforce:read"))]
)
def get_employee(employee_id: int, svc: WorkforceService = Depends(_svc)) -> dict:
    return ok(svc.get_employee(employee_id))


@router.patch(
    "/employees/{employee_id}", dependencies=[Depends(require_permissions("workforce:manage"))]
)
def update_employee(
    employee_id: int, body: EmployeeUpdate, svc: WorkforceService = Depends(_svc)
) -> dict:
    return ok(
        svc.update_employee(employee_id, body.model_dump(exclude_unset=True)), message="updated"
    )


@router.post(
    "/employees/{employee_id}/status",
    dependencies=[Depends(require_permissions("workforce:manage"))],
)
def employee_status(
    employee_id: int, body: EmployeeStatus, svc: WorkforceService = Depends(_svc)
) -> dict:
    return ok(svc.change_employee_status(employee_id, body.model_dump()), message="updated")


@router.get("/shifts", dependencies=[Depends(require_permissions("workforce:read"))])
def list_shifts(park_id: int | None = None, svc: WorkforceService = Depends(_svc)) -> dict:
    return ok(svc.list_shifts(park_id))


@router.post("/shifts", dependencies=[Depends(require_permissions("workforce:schedule"))])
def create_shift(body: ShiftCreate, svc: WorkforceService = Depends(_svc)) -> dict:
    return ok(svc.create_shift(body.model_dump()), message="created")


@router.post(
    "/shifts/{template_id}/versions",
    dependencies=[Depends(require_permissions("workforce:schedule"))],
)
def add_shift_version(
    template_id: int, body: ShiftVersionCreate, svc: WorkforceService = Depends(_svc)
) -> dict:
    return ok(svc.add_shift_version(template_id, body.model_dump()), message="published")


@router.get("/assignments", dependencies=[Depends(require_permissions("workforce:read"))])
def list_assignments(
    date_from: date,
    date_to: date,
    employee_id: int | None = None,
    svc: WorkforceService = Depends(_svc),
) -> dict:
    return ok(svc.list_assignments(employee_id=employee_id, date_from=date_from, date_to=date_to))


@router.post("/assignments", dependencies=[Depends(require_permissions("workforce:schedule"))])
def create_assignment(body: AssignmentCreate, svc: WorkforceService = Depends(_svc)) -> dict:
    return ok(svc.create_assignment(body.model_dump()), message="created")


@router.post(
    "/assignments/{assignment_id}/cancel",
    dependencies=[Depends(require_permissions("workforce:schedule"))],
)
def cancel_assignment(
    assignment_id: int, body: ExpectedReason, svc: WorkforceService = Depends(_svc)
) -> dict:
    return ok(svc.cancel_assignment(assignment_id, body.model_dump()), message="cancelled")


@router.get("/attendance/policies", dependencies=[Depends(require_permissions("workforce:read"))])
def list_policies(park_id: int | None = None, svc: WorkforceService = Depends(_svc)) -> dict:
    return ok(svc.list_policies(park_id))


@router.post(
    "/attendance/policies",
    dependencies=[Depends(require_permissions("workforce:attendance_admin"))],
)
def create_policy(body: PolicyCreate, svc: WorkforceService = Depends(_svc)) -> dict:
    return ok(svc.create_policy(body.model_dump()), message="created")


@router.get("/attendance/locations", dependencies=[Depends(require_permissions("workforce:read"))])
def list_locations(park_id: int | None = None, svc: WorkforceService = Depends(_svc)) -> dict:
    return ok(svc.list_locations(park_id))


@router.post(
    "/attendance/locations",
    dependencies=[Depends(require_permissions("workforce:attendance_admin"))],
)
def create_location(body: LocationCreate, svc: WorkforceService = Depends(_svc)) -> dict:
    return ok(svc.create_location(body.model_dump()), message="created")


@router.post(
    "/attendance/punches", dependencies=[Depends(require_permissions("workforce:attendance_punch"))]
)
def create_punch(
    body: PunchCreate, idempotency_key: IdempotencyKey, svc: WorkforceService = Depends(_svc)
) -> dict:
    return ok(
        svc.create_punch(body.model_dump(exclude={"latitude", "longitude"}), key=idempotency_key),
        message="recorded",
    )


@router.get("/attendance/summaries", dependencies=[Depends(require_permissions("workforce:read"))])
def list_summaries(
    date_from: date,
    date_to: date,
    employee_id: int | None = None,
    status: str | None = None,
    svc: WorkforceService = Depends(_svc),
) -> dict:
    return ok(
        svc.list_summaries(
            employee_id=employee_id, date_from=date_from, date_to=date_to, status=status
        )
    )


@router.post(
    "/attendance/summaries/generate",
    dependencies=[Depends(require_permissions("workforce:attendance_admin"))],
)
def generate_summary(body: SummaryGenerate, svc: WorkforceService = Depends(_svc)) -> dict:
    return ok(svc.generate_summary(body.model_dump()), message="generated")


@router.post(
    "/attendance/summaries/{summary_id}/adjust",
    dependencies=[Depends(require_permissions("workforce:attendance_adjust"))],
)
def adjust_summary(
    summary_id: int, body: SummaryAdjust, svc: WorkforceService = Depends(_svc)
) -> dict:
    return ok(svc.adjust_summary(summary_id, body.model_dump()), message="adjusted")


@router.get("/leaves", dependencies=[Depends(require_permissions("workforce:read"))])
def list_leaves(status: str | None = None, svc: WorkforceService = Depends(_svc)) -> dict:
    return ok(svc.list_leaves(status))


@router.post(
    "/leaves",
    dependencies=[Depends(require_permissions("workforce:leave_request", "approval:write"))],
)
def create_leave(
    body: LeaveCreate, idempotency_key: IdempotencyKey, svc: WorkforceService = Depends(_svc)
) -> dict:
    return ok(svc.create_leave(body.model_dump(), key=idempotency_key), message="submitted")


@router.post(
    "/leaves/{leave_id}/refresh-approval",
    dependencies=[Depends(require_permissions("workforce:leave_request"))],
)
def refresh_leave(leave_id: int, svc: WorkforceService = Depends(_svc)) -> dict:
    return ok(svc.refresh_leave(leave_id), message="refreshed")


@router.post(
    "/leaves/{leave_id}/cancel",
    dependencies=[Depends(require_permissions("workforce:leave_request"))],
)
def cancel_leave(
    leave_id: int, body: ExpectedReason, svc: WorkforceService = Depends(_svc)
) -> dict:
    return ok(svc.cancel_leave(leave_id, body.model_dump()), message="cancelled")


@router.get("/performance/cycles", dependencies=[Depends(require_permissions("workforce:read"))])
def list_cycles(park_id: int | None = None, svc: WorkforceService = Depends(_svc)) -> dict:
    return ok(svc.list_cycles(park_id))


@router.post(
    "/performance/cycles",
    dependencies=[Depends(require_permissions("workforce:performance_manage"))],
)
def create_cycle(body: PerformanceCycleCreate, svc: WorkforceService = Depends(_svc)) -> dict:
    return ok(svc.create_cycle(body.model_dump()), message="created")


@router.post(
    "/performance/cycles/{cycle_id}/status",
    dependencies=[Depends(require_permissions("workforce:performance_manage"))],
)
def cycle_status(cycle_id: int, body: CycleStatus, svc: WorkforceService = Depends(_svc)) -> dict:
    return ok(svc.change_cycle_status(cycle_id, body.model_dump()), message="updated")


@router.get(
    "/performance/cycles/{cycle_id}/goals",
    dependencies=[Depends(require_permissions("workforce:read"))],
)
def list_goals(
    cycle_id: int, employee_id: int | None = None, svc: WorkforceService = Depends(_svc)
) -> dict:
    return ok(svc.list_goals(cycle_id, employee_id))


@router.post(
    "/performance/cycles/{cycle_id}/goals",
    dependencies=[Depends(require_permissions("workforce:performance_manage"))],
)
def create_goal(cycle_id: int, body: GoalCreate, svc: WorkforceService = Depends(_svc)) -> dict:
    return ok(svc.create_goal(cycle_id, body.model_dump()), message="created")


@router.get("/performance/reviews", dependencies=[Depends(require_permissions("workforce:read"))])
def list_reviews(cycle_id: int | None = None, svc: WorkforceService = Depends(_svc)) -> dict:
    return ok(svc.list_reviews(cycle_id))


@router.post(
    "/performance/reviews",
    dependencies=[Depends(require_permissions("workforce:performance_review"))],
)
def create_review(body: ReviewCreate, svc: WorkforceService = Depends(_svc)) -> dict:
    return ok(svc.create_review(body.model_dump()), message="created")


@router.post(
    "/performance/reviews/{review_id}/publish",
    dependencies=[Depends(require_permissions("workforce:performance_review"))],
)
def publish_review(
    review_id: int, body: ReviewPublish, svc: WorkforceService = Depends(_svc)
) -> dict:
    return ok(svc.publish_review(review_id, body.model_dump()), message="published")


@router.post(
    "/performance/reviews/{review_id}/acknowledge",
    dependencies=[Depends(require_permissions("workforce:performance_acknowledge"))],
)
def acknowledge_review(
    review_id: int, body: ReviewAcknowledge, svc: WorkforceService = Depends(_svc)
) -> dict:
    return ok(svc.acknowledge_review(review_id, body.model_dump()), message="acknowledged")


@router.get("/qualification-types", dependencies=[Depends(require_permissions("workforce:read"))])
def list_qualification_types(
    include_retired: bool = False, svc: WorkforceService = Depends(_svc)
) -> dict:
    return ok(svc.list_qualification_types(include_retired))


@router.post(
    "/qualification-types",
    dependencies=[Depends(require_permissions("workforce:qualification_manage"))],
)
def create_qualification_type(
    body: QualificationTypeCreate, svc: WorkforceService = Depends(_svc)
) -> dict:
    return ok(svc.create_qualification_type(body.model_dump()), message="created")


@router.get("/qualifications", dependencies=[Depends(require_permissions("workforce:read"))])
def list_qualifications(
    employee_id: int | None = None, status: str | None = None, svc: WorkforceService = Depends(_svc)
) -> dict:
    return ok(svc.list_qualifications(employee_id, status))


@router.post(
    "/qualifications", dependencies=[Depends(require_permissions("workforce:qualification_manage"))]
)
def create_qualification(body: QualificationCreate, svc: WorkforceService = Depends(_svc)) -> dict:
    return ok(svc.create_qualification(body.model_dump()), message="created")


@router.post(
    "/qualifications/{qualification_id}/verify",
    dependencies=[Depends(require_permissions("workforce:qualification_verify"))],
)
def verify_qualification(
    qualification_id: int, body: ExpectedReason, svc: WorkforceService = Depends(_svc)
) -> dict:
    return ok(svc.verify_qualification(qualification_id, body.model_dump()), message="verified")


@router.post(
    "/qualifications/{qualification_id}/revoke",
    dependencies=[Depends(require_permissions("workforce:qualification_verify"))],
)
def revoke_qualification(
    qualification_id: int, body: QualificationRevoke, svc: WorkforceService = Depends(_svc)
) -> dict:
    return ok(svc.revoke_qualification(qualification_id, body.model_dump()), message="revoked")


@router.post(
    "/qualifications/sweep",
    dependencies=[Depends(require_permissions("workforce:qualification_verify"))],
)
def sweep_qualifications(body: QualificationSweep, svc: WorkforceService = Depends(_svc)) -> dict:
    return ok(svc.sweep_qualifications(body.due_on), message="swept")

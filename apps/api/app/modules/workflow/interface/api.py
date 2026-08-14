"""Approval definition/task/delegation and audit-center REST contracts."""

# FastAPI's declarative dependency defaults intentionally call Depends at import time.
# ruff: noqa: B008

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.workflow.application.approval_service import ApprovalService
from app.modules.workflow.application.audit_service import AuditService
from app.shared.deps import get_tenant_context
from app.shared.response import ok
from app.shared.tenant_context import TenantContext

router = APIRouter(tags=["Approvals"])


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApprovalCreate(StrictBody):
    biz_type: str = Field(min_length=1, max_length=64)
    biz_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    park_id: int | None = None
    remark: str | None = Field(default=None, max_length=2000)
    definition_code: str | None = Field(default=None, max_length=64)
    priority: Literal["LOW", "MEDIUM", "HIGH", "URGENT"] = "MEDIUM"
    snapshot: dict[str, Any] | None = None
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=64)


class ApprovalCommand(StrictBody):
    remark: str | None = Field(default=None, max_length=2000)
    expected_version: int | None = Field(default=None, ge=0)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=64)


class ApprovalResubmit(StrictBody):
    remark: str | None = Field(default=None, max_length=2000)
    expected_version: int = Field(ge=0)
    idempotency_key: str = Field(min_length=8, max_length=64)


class ApprovalTaskDecision(StrictBody):
    action: Literal["APPROVE", "REJECT", "RETURN"]
    remark: str | None = Field(default=None, max_length=2000)
    expected_version: int = Field(ge=0)
    idempotency_key: str = Field(min_length=8, max_length=64)
    override_reason: str | None = Field(default=None, max_length=1000)


class ApprovalAssigneeIn(StrictBody):
    user_id: int | None = Field(default=None, gt=0)
    role_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_exactly_one(self) -> ApprovalAssigneeIn:
        if (self.user_id is None) == (self.role_id is None):
            raise ValueError("user_id 与 role_id 必须且只能填写一个")
        return self


class ApprovalStepIn(StrictBody):
    step_order: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=128)
    approval_mode: Literal["ANY", "ALL"] = "ANY"
    min_approvals: int = Field(default=1, gt=0, le=100)
    sla_hours: int = Field(default=24, gt=0, le=24 * 365)
    assignees: list[ApprovalAssigneeIn] = Field(default_factory=list, max_length=100)


class ApprovalDefinitionCreate(StrictBody):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=128)
    biz_type: str = Field(min_length=1, max_length=64)
    park_id: int | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, max_length=2000)
    steps: list[ApprovalStepIn] = Field(default_factory=list, max_length=50)


class ApprovalDefinitionUpdate(StrictBody):
    expected_lock_version: int = Field(ge=0)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    steps: list[ApprovalStepIn] | None = Field(default=None, max_length=50)


class VersionCommand(StrictBody):
    expected_lock_version: int = Field(ge=0)


class PublishCommand(VersionCommand):
    version_id: int = Field(gt=0)


class DelegationCreate(StrictBody):
    delegate_user_id: int = Field(gt=0)
    biz_type: str | None = Field(default=None, min_length=1, max_length=64)
    starts_at: datetime
    ends_at: datetime


def _svc(
    db: Session = Depends(get_db), ctx: TenantContext = Depends(get_tenant_context)
) -> ApprovalService:
    return ApprovalService(db, ctx)


def _audit_svc(
    db: Session = Depends(get_db), ctx: TenantContext = Depends(get_tenant_context)
) -> AuditService:
    return AuditService(db, ctx)


@router.get("/approvals")
def list_approvals(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = None,
    biz_type: str | None = None,
    park_id: int | None = Query(default=None, gt=0),
    priority: str | None = None,
    mine: bool = False,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    svc: ApprovalService = Depends(_svc),
) -> dict:
    return ok(
        svc.list_approvals(
            page=page,
            page_size=page_size,
            status=status,
            biz_type=biz_type,
            park_id=park_id,
            priority=priority,
            mine=mine,
            created_from=created_from,
            created_to=created_to,
        )
    )


@router.post("/approvals")
def create_approval(body: ApprovalCreate, svc: ApprovalService = Depends(_svc)) -> dict:
    return ok(svc.create(body.model_dump()), message="created")


@router.get("/approvals/{approval_id}")
def approval_detail(approval_id: int, svc: ApprovalService = Depends(_svc)) -> dict:
    return ok(svc.get_approval(approval_id))


@router.post("/approvals/{approval_id}/approve")
def approve(
    approval_id: int,
    body: ApprovalCommand | None = None,
    svc: ApprovalService = Depends(_svc),
) -> dict:
    return ok(
        svc.decide(approval_id, approve=True, remark=body.remark if body else None),
        message="approved",
    )


@router.post("/approvals/{approval_id}/reject")
def reject(
    approval_id: int,
    body: ApprovalCommand | None = None,
    svc: ApprovalService = Depends(_svc),
) -> dict:
    return ok(
        svc.decide(approval_id, approve=False, remark=body.remark if body else None),
        message="rejected",
    )


@router.post("/approvals/{approval_id}/withdraw")
def withdraw(
    approval_id: int,
    body: ApprovalCommand | None = None,
    svc: ApprovalService = Depends(_svc),
) -> dict:
    command = body or ApprovalCommand()
    return ok(
        svc.withdraw(
            approval_id,
            remark=command.remark,
            expected_version=command.expected_version,
            idempotency_key=command.idempotency_key,
        ),
        message="withdrawn",
    )


@router.post("/approvals/{approval_id}/resubmit")
def resubmit(
    approval_id: int,
    body: ApprovalResubmit,
    svc: ApprovalService = Depends(_svc),
) -> dict:
    return ok(svc.resubmit(approval_id, **body.model_dump()), message="resubmitted")


@router.get("/approvals/{approval_id}/history")
def approval_history(approval_id: int, svc: ApprovalService = Depends(_svc)) -> dict:
    return ok(svc.history(approval_id))


@router.get("/approval-definitions")
def list_definitions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    biz_type: str | None = None,
    svc: ApprovalService = Depends(_svc),
) -> dict:
    return ok(
        svc.list_definitions(
            status=status,
            biz_type=biz_type,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/approval-definitions")
def create_definition(
    body: ApprovalDefinitionCreate,
    svc: ApprovalService = Depends(_svc),
) -> dict:
    return ok(svc.create_definition(body.model_dump()), message="created")


@router.get("/approval-definitions/{definition_id}")
def definition_detail(definition_id: int, svc: ApprovalService = Depends(_svc)) -> dict:
    return ok(svc.get_definition(definition_id))


@router.patch("/approval-definitions/{definition_id}")
def update_definition(
    definition_id: int,
    body: ApprovalDefinitionUpdate,
    svc: ApprovalService = Depends(_svc),
) -> dict:
    return ok(svc.update_definition(definition_id, body.model_dump(exclude_unset=True)))


@router.post("/approval-definitions/{definition_id}/draft")
def create_draft(
    definition_id: int,
    body: VersionCommand,
    svc: ApprovalService = Depends(_svc),
) -> dict:
    return ok(
        svc.create_draft(
            definition_id,
            expected_lock_version=body.expected_lock_version,
        ),
        message="draft_ready",
    )


@router.post("/approval-definitions/{definition_id}/publish")
def publish_definition(
    definition_id: int,
    body: PublishCommand,
    svc: ApprovalService = Depends(_svc),
) -> dict:
    return ok(
        svc.publish_definition(
            definition_id,
            version_id=body.version_id,
            expected_lock_version=body.expected_lock_version,
        ),
        message="published",
    )


@router.post("/approval-definitions/{definition_id}/retire")
def retire_definition(
    definition_id: int,
    body: VersionCommand,
    svc: ApprovalService = Depends(_svc),
) -> dict:
    return ok(
        svc.retire_definition(
            definition_id,
            expected_lock_version=body.expected_lock_version,
        ),
        message="retired",
    )


@router.get("/approval-tasks")
def list_tasks(
    processed: bool = False,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: ApprovalService = Depends(_svc),
) -> dict:
    return ok(
        svc.list_tasks(
            processed=processed,
            status=status,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/approval-tasks/{task_id}/decide")
def decide_task(
    task_id: int,
    body: ApprovalTaskDecision,
    svc: ApprovalService = Depends(_svc),
) -> dict:
    return ok(svc.decide_task(task_id, **body.model_dump()), message="decided")


@router.post("/approval-tasks/sweep-overdue")
def sweep_overdue(
    limit: int = Query(200, ge=1, le=500),
    svc: ApprovalService = Depends(_svc),
) -> dict:
    return ok(svc.sweep_overdue(limit=limit), message="swept")


@router.get("/approval-delegations")
def list_delegations(svc: ApprovalService = Depends(_svc)) -> dict:
    return ok(svc.list_delegations())


@router.post("/approval-delegations")
def create_delegation(
    body: DelegationCreate,
    svc: ApprovalService = Depends(_svc),
) -> dict:
    return ok(svc.create_delegation(body.model_dump()), message="created")


@router.post("/approval-delegations/{delegation_id}/revoke")
def revoke_delegation(delegation_id: int, svc: ApprovalService = Depends(_svc)) -> dict:
    return ok(svc.revoke_delegation(delegation_id), message="revoked")


def _audit_filters(
    *,
    user_id: int | None,
    action: str | None,
    resource_type: str | None,
    resource_id: str | None,
    park_id: int | None,
    request_id: str | None,
    integrity_state: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "park_id": park_id,
        "request_id": request_id,
        "integrity_state": integrity_state,
        "created_from": created_from,
        "created_to": created_to,
    }


@router.get("/audit-logs")
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    user_id: int | None = Query(default=None, gt=0),
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    park_id: int | None = Query(default=None, gt=0),
    request_id: str | None = None,
    integrity_state: Literal["VERIFIED", "FAILED", "LEGACY_UNVERIFIED"] | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    svc: AuditService = Depends(_audit_svc),
) -> dict:
    filters = _audit_filters(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        park_id=park_id,
        request_id=request_id,
        integrity_state=integrity_state,
        created_from=created_from,
        created_to=created_to,
    )
    return ok(svc.search(filters=filters, page=page, page_size=page_size))


@router.get("/audit-logs/verify")
def verify_audit_chain(svc: AuditService = Depends(_audit_svc)) -> dict:
    return ok(svc.verify())


@router.get("/audit-logs/export", response_class=Response)
def export_audit_logs(
    limit: int = Query(2000, ge=1, le=2000),
    user_id: int | None = Query(default=None, gt=0),
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    park_id: int | None = Query(default=None, gt=0),
    request_id: str | None = None,
    integrity_state: Literal["VERIFIED", "FAILED", "LEGACY_UNVERIFIED"] | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    svc: AuditService = Depends(_audit_svc),
) -> Response:
    filters = _audit_filters(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        park_id=park_id,
        request_id=request_id,
        integrity_state=integrity_state,
        created_from=created_from,
        created_to=created_to,
    )
    content = svc.export_csv(filters=filters, limit=limit)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit-logs.csv"'},
    )


@router.get("/audit-logs/{audit_id}")
def audit_log_detail(audit_id: int, svc: AuditService = Depends(_audit_svc)) -> dict:
    return ok(svc.get(audit_id))

"""Tenant-service and work-order REST endpoints."""

# FastAPI's declarative dependency defaults intentionally call Depends at import time.
# ruff: noqa: B008

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.facility_ops.application.work_order_service import WorkOrderService
from app.modules.facility_ops.interface.schemas import (
    AcceptanceDecision,
    AssignmentRuleCreate,
    AssignmentRuleRetire,
    CancelRequest,
    CompletionSubmit,
    CostCreate,
    CostReverse,
    DispatchRequest,
    ExpectedVersion,
    QuoteCreate,
    QuoteDecision,
    RatingCreate,
    SlaSweepRequest,
    TenantServicePrincipalGrant,
    TenantServiceRequestCreate,
    WorkOrderCreate,
)
from app.shared.deps import get_tenant_context, require_permissions
from app.shared.response import ok
from app.shared.tenant_context import TenantContext

router = APIRouter(tags=["TenantService"])
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=128),
]


def _svc(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> WorkOrderService:
    return WorkOrderService(db, ctx)


# Static staff administration paths must precede the integer work-order path.
@router.get(
    "/work-order-assignment-rules",
    dependencies=[Depends(require_permissions("work_order:dispatch"))],
)
def list_assignment_rules(svc: WorkOrderService = Depends(_svc)) -> dict:
    return ok(svc.list_rules())


@router.post(
    "/work-order-assignment-rules",
    dependencies=[Depends(require_permissions("work_order:dispatch_rule_manage"))],
)
def create_assignment_rule(
    body: AssignmentRuleCreate,
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    return ok(svc.create_rule(body.model_dump()), message="created")


@router.post(
    "/work-order-assignment-rules/{rule_id}/publish",
    dependencies=[Depends(require_permissions("work_order:dispatch_rule_manage"))],
)
def publish_assignment_rule(rule_id: int, svc: WorkOrderService = Depends(_svc)) -> dict:
    return ok(svc.publish_rule(rule_id), message="published")


@router.post(
    "/work-order-assignment-rules/{rule_id}/retire",
    dependencies=[Depends(require_permissions("work_order:dispatch_rule_manage"))],
)
def retire_assignment_rule(
    rule_id: int,
    body: AssignmentRuleRetire,
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    return ok(svc.retire_rule(rule_id, reason=body.reason), message="retired")


@router.post(
    "/work-orders/sla/sweep",
    dependencies=[Depends(require_permissions("work_order:sla_sweep"))],
)
def sweep_work_order_sla(
    body: SlaSweepRequest,
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    as_of: datetime | None = body.as_of
    return ok(svc.sweep_sla(as_of=as_of), message="swept")


@router.get(
    "/work-orders",
    dependencies=[Depends(require_permissions("work_order:read"))],
)
def list_work_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = None,
    park_id: int | None = None,
    party_id: int | None = None,
    category: str | None = None,
    assignee_user_id: int | None = None,
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    return ok(
        svc.list_orders(
            page=page,
            page_size=page_size,
            status=status,
            park_id=park_id,
            party_id=party_id,
            category=category,
            assignee_user_id=assignee_user_id,
        )
    )


@router.post(
    "/work-orders",
    dependencies=[Depends(require_permissions("work_order:intake"))],
)
def create_work_order(
    body: WorkOrderCreate,
    idempotency_key: IdempotencyKey,
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    return ok(
        svc.create_order(body.model_dump(), idempotency_key=idempotency_key),
        message="created",
    )


@router.get(
    "/work-orders/{work_order_id}",
    dependencies=[Depends(require_permissions("work_order:read"))],
)
def get_work_order(work_order_id: int, svc: WorkOrderService = Depends(_svc)) -> dict:
    return ok(svc.get_order(work_order_id))


@router.post(
    "/work-orders/{work_order_id}/dispatch",
    dependencies=[Depends(require_permissions("work_order:dispatch"))],
)
def dispatch_work_order(
    work_order_id: int,
    body: DispatchRequest,
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    return ok(svc.dispatch(work_order_id, body.model_dump()), message="dispatched")


@router.post(
    "/work-orders/{work_order_id}/start",
    dependencies=[Depends(require_permissions("work_order:execute"))],
)
def start_work_order(
    work_order_id: int,
    body: ExpectedVersion,
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    return ok(
        svc.start_order(work_order_id, expected_version=body.expected_version),
        message="started",
    )


@router.post(
    "/work-orders/{work_order_id}/quotes",
    dependencies=[Depends(require_permissions("work_order:quote"))],
)
def create_work_order_quote(
    work_order_id: int,
    body: QuoteCreate,
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    return ok(svc.create_quote(work_order_id, body.model_dump()), message="created")


@router.post(
    "/work-orders/{work_order_id}/quotes/{quote_id}/submit",
    dependencies=[Depends(require_permissions("work_order:quote"))],
)
def submit_work_order_quote(
    work_order_id: int,
    quote_id: int,
    body: ExpectedVersion,
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    return ok(
        svc.submit_quote(
            work_order_id,
            quote_id,
            expected_version=body.expected_version,
        ),
        message="submitted",
    )


@router.post(
    "/work-orders/{work_order_id}/cost-entries",
    dependencies=[Depends(require_permissions("work_order:execute"))],
)
def create_work_order_cost(
    work_order_id: int,
    body: CostCreate,
    idempotency_key: IdempotencyKey,
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    return ok(
        svc.add_cost(
            work_order_id,
            body.model_dump(),
            idempotency_key=idempotency_key,
        ),
        message="created",
    )


@router.post(
    "/work-orders/{work_order_id}/cost-entries/{cost_id}/reverse",
    dependencies=[Depends(require_permissions("work_order:execute"))],
)
def reverse_work_order_cost(
    work_order_id: int,
    cost_id: int,
    body: CostReverse,
    idempotency_key: IdempotencyKey,
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    return ok(
        svc.reverse_cost(
            work_order_id,
            cost_id,
            body.model_dump(),
            idempotency_key=idempotency_key,
        ),
        message="reversed",
    )


@router.post(
    "/work-orders/{work_order_id}/complete",
    dependencies=[Depends(require_permissions("work_order:execute"))],
)
def complete_work_order(
    work_order_id: int,
    body: CompletionSubmit,
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    return ok(svc.submit_completion(work_order_id, body.model_dump()), message="submitted")


@router.post(
    "/work-orders/{work_order_id}/cancel",
    dependencies=[Depends(require_permissions("work_order:write"))],
)
def cancel_work_order(
    work_order_id: int,
    body: CancelRequest,
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    return ok(
        svc.cancel_order(
            work_order_id,
            expected_version=body.expected_version,
            reason=body.reason,
        ),
        message="cancelled",
    )


@router.get(
    "/tenant-service/principals",
    dependencies=[Depends(require_permissions("tenant_service:principal_manage"))],
)
def list_tenant_service_principals(svc: WorkOrderService = Depends(_svc)) -> dict:
    return ok(svc.list_principals())


@router.post(
    "/tenant-service/principals",
    dependencies=[Depends(require_permissions("tenant_service:principal_manage"))],
)
def grant_tenant_service_principal(
    body: TenantServicePrincipalGrant,
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    return ok(svc.grant_principal(body.model_dump()), message="granted")


@router.post(
    "/tenant-service/principals/{principal_id}/disable",
    dependencies=[Depends(require_permissions("tenant_service:principal_manage"))],
)
def disable_tenant_service_principal(
    principal_id: int,
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    return ok(svc.disable_principal(principal_id), message="disabled")


@router.get(
    "/tenant-service/requests",
    dependencies=[Depends(require_permissions("tenant_service:read_own"))],
)
def list_tenant_service_requests(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    return ok(svc.list_tenant_orders(page=page, page_size=page_size))


@router.post(
    "/tenant-service/requests",
    dependencies=[Depends(require_permissions("tenant_service:request"))],
)
def create_tenant_service_request(
    body: TenantServiceRequestCreate,
    idempotency_key: IdempotencyKey,
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    return ok(
        svc.create_tenant_order(body.model_dump(), idempotency_key=idempotency_key),
        message="created",
    )


@router.get(
    "/tenant-service/requests/{work_order_id}",
    dependencies=[Depends(require_permissions("tenant_service:read_own"))],
)
def get_tenant_service_request(
    work_order_id: int,
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    return ok(svc.get_tenant_order(work_order_id))


@router.post(
    "/tenant-service/requests/{work_order_id}/quotes/{quote_id}/decision",
    dependencies=[Depends(require_permissions("tenant_service:quote_decide"))],
)
def decide_tenant_service_quote(
    work_order_id: int,
    quote_id: int,
    body: QuoteDecision,
    idempotency_key: IdempotencyKey,
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    return ok(
        svc.decide_quote(
            work_order_id,
            quote_id,
            body.model_dump(),
            idempotency_key=idempotency_key,
        ),
        message="decided",
    )


@router.post(
    "/tenant-service/requests/{work_order_id}/acceptance",
    dependencies=[Depends(require_permissions("tenant_service:accept"))],
)
def decide_tenant_service_acceptance(
    work_order_id: int,
    body: AcceptanceDecision,
    idempotency_key: IdempotencyKey,
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    return ok(
        svc.decide_acceptance(
            work_order_id,
            body.model_dump(),
            idempotency_key=idempotency_key,
        ),
        message="decided",
    )


@router.post(
    "/tenant-service/requests/{work_order_id}/rating",
    dependencies=[Depends(require_permissions("tenant_service:rate"))],
)
def rate_tenant_service_request(
    work_order_id: int,
    body: RatingCreate,
    idempotency_key: IdempotencyKey,
    svc: WorkOrderService = Depends(_svc),
) -> dict:
    return ok(
        svc.rate_order(
            work_order_id,
            body.model_dump(),
            idempotency_key=idempotency_key,
        ),
        message="rated",
    )

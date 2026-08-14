"""功能说明：WorkItem REST 路由。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.session import get_db
from app.modules.workbench.application.automation_service import WorkbenchAutomationService
from app.modules.workbench.application.summary_service import WorkbenchSummaryService
from app.modules.workbench.application.work_item_service import WorkItemService
from app.modules.workbench.interface.schemas import (
    BusinessEventEmit,
    LayoutSave,
    NotificationBulkRead,
    ReplayRequest,
    RoleLayoutSave,
    RuleCreate,
    RuleDraftUpdate,
    ScheduleCreate,
    ScheduleRunRequest,
    ScheduleUpdate,
    WorkbenchVersionCommand,
    WorkItemCreate,
    WorkItemReassign,
    WorkItemTransition,
)
from app.shared.deps import get_tenant_context, require_permissions
from app.shared.response import ok
from app.shared.tenant_context import TenantContext

router = APIRouter(tags=["WorkItems"])


def _svc(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> WorkItemService:
    return WorkItemService(db, ctx)


def _summary_svc(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> WorkbenchSummaryService:
    return WorkbenchSummaryService(db, ctx)


def _automation_svc(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> WorkbenchAutomationService:
    return WorkbenchAutomationService(db, ctx)


@router.get(
    "/workbench/summary",
    dependencies=[Depends(require_permissions("work_item:read"))],
)
def workbench_summary(
    park_id: Optional[int] = None,
    expiring_within_days: int = Query(90, ge=1, le=365),
    todo_limit: int = Query(10, ge=1, le=50),
    svc: WorkbenchSummaryService = Depends(_summary_svc),
) -> dict:
    """功能说明：运营工作台聚合指标与最近待办。"""

    return ok(
        svc.summary(
            park_id=park_id,
            expiring_within_days=expiring_within_days,
            todo_limit=todo_limit,
        )
    )


@router.post("/workbench/jobs/sync-lease-todos")
def sync_lease_todos(
    within_days: int = Query(90, ge=1, le=365),
    svc: WorkbenchSummaryService = Depends(_summary_svc),
) -> dict:
    """功能说明：扫描即将到期合同并幂等补齐待办。"""

    return ok(svc.sync_lease_expiring_todos(within_days=within_days), message="synced")


@router.get("/work-items", dependencies=[Depends(require_permissions("work_item:read"))])
def list_work_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
    park_id: Optional[int] = None,
    assignee_user_id: Optional[int] = None,
    item_type: Optional[str] = None,
    mine: bool = Query(False, description="仅当前用户指派"),
    svc: WorkItemService = Depends(_svc),
) -> dict:
    """功能说明：GET /work-items 分页列表。"""

    return ok(
        svc.list_work_items(
            page=page,
            page_size=page_size,
            status=status,
            park_id=park_id,
            assignee_user_id=assignee_user_id,
            item_type=item_type,
            mine=mine,
        )
    )


@router.post("/work-items")
def create_work_item(
    body: WorkItemCreate,
    svc: WorkItemService = Depends(_svc),
) -> dict:
    """功能说明：POST /work-items 人工创建待办。"""

    return ok(svc.create_work_item(body.model_dump()), message="created")


@router.get(
    "/work-items/{work_item_id}",
    dependencies=[Depends(require_permissions("work_item:read"))],
)
def get_work_item(work_item_id: int, svc: WorkItemService = Depends(_svc)) -> dict:
    """功能说明：GET 待办详情。"""

    return ok(svc.get_work_item(work_item_id))


@router.post("/work-items/{work_item_id}/complete")
def complete_work_item(
    work_item_id: int, body: WorkItemTransition, svc: WorkItemService = Depends(_svc)
) -> dict:
    """功能说明：完成待办。"""

    return ok(svc.complete_work_item(work_item_id, **body.model_dump()), message="completed")


@router.post("/work-items/{work_item_id}/cancel")
def cancel_work_item(
    work_item_id: int, body: WorkItemTransition, svc: WorkItemService = Depends(_svc)
) -> dict:
    """功能说明：取消待办。"""

    return ok(svc.cancel_work_item(work_item_id, **body.model_dump()), message="cancelled")


@router.post("/work-items/{work_item_id}/reopen")
def reopen_work_item(
    work_item_id: int, body: WorkItemTransition, svc: WorkItemService = Depends(_svc)
) -> dict:
    """功能说明：重新打开待办。"""

    return ok(svc.reopen_work_item(work_item_id, **body.model_dump()), message="reopened")


@router.post("/work-items/{work_item_id}/reassign")
def reassign_work_item(
    work_item_id: int, body: WorkItemReassign, svc: WorkItemService = Depends(_svc)
) -> dict:
    return ok(svc.reassign_work_item(work_item_id, **body.model_dump()), message="reassigned")


@router.post("/business-events")
def emit_business_event(
    body: BusinessEventEmit, svc: WorkbenchAutomationService = Depends(_automation_svc)
) -> dict:
    return ok(svc.emit_event(**body.model_dump()), message="accepted")


@router.get("/business-events")
def list_business_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    event_type: Optional[str] = None,
    park_id: Optional[int] = None,
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    return ok(
        svc.list_events(
            page=page,
            page_size=page_size,
            event_type=event_type,
            park_id=park_id,
        )
    )


@router.post("/business-events/dispatch")
def dispatch_business_events(
    limit: int = Query(100, ge=1, le=500),
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    return ok(svc.dispatch(limit=limit), message="dispatched")


@router.post("/event-consumers/{consumer_id}/replay")
def replay_event_consumer(
    consumer_id: int,
    body: ReplayRequest,
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    return ok(svc.replay_consumer(consumer_id, reason=body.reason), message="replay queued")


@router.get("/automation-rules")
def list_automation_rules(svc: WorkbenchAutomationService = Depends(_automation_svc)) -> dict:
    return ok(svc.list_rules())


@router.post("/automation-rules")
def create_automation_rule(
    body: RuleCreate, svc: WorkbenchAutomationService = Depends(_automation_svc)
) -> dict:
    return ok(svc.create_rule(body.model_dump()), message="created")


@router.put("/automation-rules/{rule_id}/draft")
def update_automation_rule_draft(
    rule_id: int,
    body: RuleDraftUpdate,
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    return ok(
        svc.update_rule_draft(rule_id, body.model_dump(exclude_unset=True)), message="updated"
    )


@router.post("/automation-rules/{rule_id}/publish")
def publish_automation_rule(
    rule_id: int,
    body: WorkbenchVersionCommand,
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    return ok(svc.publish_rule(rule_id, expected_version=body.expected_version), message="published")


@router.post("/automation-rules/{rule_id}/draft")
def create_automation_rule_draft(
    rule_id: int,
    body: WorkbenchVersionCommand,
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    return ok(
        svc.create_rule_draft(rule_id, expected_version=body.expected_version), message="draft created"
    )


@router.post("/automation-rules/{rule_id}/retire")
def retire_automation_rule(
    rule_id: int,
    body: WorkbenchVersionCommand,
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    return ok(svc.retire_rule(rule_id, expected_version=body.expected_version), message="retired")


@router.get("/automation-executions")
def list_automation_executions(
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    return ok(svc.list_executions())


@router.get("/notifications")
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    return ok(svc.list_notifications(page=page, page_size=page_size, status=status))


@router.post("/notifications/bulk-read")
def bulk_read_notifications(
    body: NotificationBulkRead,
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    return ok(svc.bulk_read(body.ids), message="read")


@router.post("/notifications/{notification_id}/read")
def read_notification(
    notification_id: int,
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    return ok(svc.mark_notification(notification_id), message="read")


@router.post("/notifications/{notification_id}/archive")
def archive_notification(
    notification_id: int,
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    return ok(svc.mark_notification(notification_id, archive=True), message="archived")


@router.get("/scheduler/definitions")
def list_scheduler_definitions(
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    return ok(svc.list_schedules())


@router.post("/scheduler/definitions")
def create_scheduler_definition(
    body: ScheduleCreate, svc: WorkbenchAutomationService = Depends(_automation_svc)
) -> dict:
    return ok(svc.create_schedule(body.model_dump()), message="created")


@router.put("/scheduler/definitions/{schedule_id}")
def update_scheduler_definition(
    schedule_id: int,
    body: ScheduleUpdate,
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    return ok(
        svc.update_schedule(schedule_id, body.model_dump(exclude_unset=True)), message="updated"
    )


@router.post("/scheduler/definitions/{schedule_id}/run")
def run_scheduler_definition(
    schedule_id: int,
    body: ScheduleRunRequest,
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    return ok(
        svc.run_schedule(schedule_id, idempotency_key=body.idempotency_key), message="finished"
    )


@router.post("/scheduler/poll")
def poll_scheduler(
    limit: int = Query(20, ge=1, le=100),
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    return ok(svc.poll_schedules(limit=limit), message="polled")


@router.post("/scheduler/recover")
def recover_scheduler(
    limit: int = Query(100, ge=1, le=200),
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    return ok(svc.recover_stale_runs(limit=limit), message="recovered")


@router.get("/scheduler/runs")
def list_scheduler_runs(
    schedule_id: Optional[int] = None,
    limit: int = Query(100, ge=1, le=500),
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    return ok(svc.list_runs(schedule_id=schedule_id, limit=limit))


@router.get("/workbench/layout")
def effective_workbench_layout(
    park_id: Optional[int] = None,
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    return ok(svc.effective_layout(park_id=park_id))


@router.put("/workbench/layout")
def save_workbench_layout(
    body: LayoutSave, svc: WorkbenchAutomationService = Depends(_automation_svc)
) -> dict:
    return ok(svc.save_user_layout(body.model_dump()), message="saved")


@router.delete("/workbench/layout")
def reset_workbench_layout(svc: WorkbenchAutomationService = Depends(_automation_svc)) -> dict:
    return ok(svc.reset_user_layout(), message="reset")


@router.get("/workbench/layout/roles")
def list_role_workbench_layouts(
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    return ok(svc.list_role_layouts())


@router.get("/workbench/layout/roles/{role_id}")
def get_role_workbench_layout(
    role_id: int,
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    return ok(svc.get_role_layout(role_id))


@router.put("/workbench/layout/roles/{role_id}")
def save_role_workbench_layout(
    role_id: int,
    body: RoleLayoutSave,
    svc: WorkbenchAutomationService = Depends(_automation_svc),
) -> dict:
    payload = body.model_dump()
    if int(payload["role_id"]) != int(role_id):
        raise AppError("路径角色与请求角色不一致", code="PARAMETER_POLLUTION", status_code=400)
    return ok(svc.save_role_layout(payload), message="saved")

"""功能说明：WorkItem REST 路由。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.workbench.application.work_item_service import WorkItemService
from app.modules.workbench.interface.schemas import WorkItemCreate
from app.shared.deps import get_tenant_context, require_permissions
from app.shared.response import ok
from app.shared.tenant_context import TenantContext

router = APIRouter(tags=["WorkItems"])


def _svc(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> WorkItemService:
    return WorkItemService(db, ctx)


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
def complete_work_item(work_item_id: int, svc: WorkItemService = Depends(_svc)) -> dict:
    """功能说明：完成待办。"""

    return ok(svc.complete_work_item(work_item_id), message="completed")


@router.post("/work-items/{work_item_id}/cancel")
def cancel_work_item(work_item_id: int, svc: WorkItemService = Depends(_svc)) -> dict:
    """功能说明：取消待办。"""

    return ok(svc.cancel_work_item(work_item_id), message="cancelled")


@router.post("/work-items/{work_item_id}/reopen")
def reopen_work_item(work_item_id: int, svc: WorkItemService = Depends(_svc)) -> dict:
    """功能说明：重新打开待办。"""

    return ok(svc.reopen_work_item(work_item_id), message="reopened")

"""功能说明：运维工单应用服务。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.business_logging import log_business_success
from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.modules.facility_ops.infrastructure.work_order_repository import WorkOrderRepository
from app.modules.park_property.infrastructure.park_repository import ParkRepository
from app.modules.workbench.application.work_item_service import WorkItemService
from app.shared.tenant_context import TenantContext

logger = logging.getLogger(__name__)

VALID_PRIORITY = frozenset({"LOW", "MEDIUM", "HIGH", "URGENT"})
WO_ITEM_TYPE = "WORK_ORDER_FOLLOW"


class WorkOrderService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.orders = WorkOrderRepository(session, ctx)
        self.parks = ParkRepository(session, ctx)
        self.work_items = WorkItemService(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def _require(self, work_order_id: int, *, for_update: bool = False):
        m = self.orders.get_by_id(work_order_id, for_update=for_update)
        if m is None:
            raise AppError("工单不存在", code="WORK_ORDER_NOT_FOUND", status_code=404)
        return m

    def _assert_park(self, park_id: int) -> int:
        pid = int(park_id)
        if not self.parks.exists_in_tenant(pid):
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        if not self.ctx.allows_park(pid):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        return pid

    def _to_dict(self, m) -> dict[str, Any]:
        return {
            "id": m.id,
            "tenant_id": m.tenant_id,
            "park_id": m.park_id,
            "title": m.title,
            "description": m.description,
            "category": m.category,
            "priority": m.priority,
            "status": m.status,
            "reporter_user_id": m.reporter_user_id,
            "assignee_user_id": m.assignee_user_id,
            "unit_id": m.unit_id,
            "due_at": m.due_at.isoformat() if m.due_at else None,
            "completed_at": m.completed_at.isoformat() if m.completed_at else None,
            "source_type": m.source_type,
            "source_id": m.source_id,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }

    def list_orders(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
    ) -> dict[str, Any]:
        if not self.ctx.has_permission("work_order:read"):
            raise AppError("无工单查看权限", code="PERMISSION_DENIED", status_code=403)
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        if park_id is not None:
            self._assert_park(int(park_id))
        items = self.orders.list(
            offset=(page - 1) * page_size, limit=page_size, status=status, park_id=park_id
        )
        total = self.orders.count(status=status, park_id=park_id)
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [self._to_dict(i) for i in items],
        }

    def get_order(self, work_order_id: int) -> dict[str, Any]:
        if not self.ctx.has_permission("work_order:read"):
            raise AppError("无工单查看权限", code="PERMISSION_DENIED", status_code=403)
        return self._to_dict(self._require(work_order_id))

    def create_order(self, data: dict[str, Any]) -> dict[str, Any]:
        if not self.ctx.has_permission("work_order:write"):
            raise AppError("无工单维护权限", code="PERMISSION_DENIED", status_code=403)
        park_id = self._assert_park(int(data["park_id"]))
        title = str(data.get("title") or "").strip()
        if not title:
            raise AppError("title 必填", code="VALIDATION_ERROR", status_code=400)
        priority = str(data.get("priority") or "MEDIUM").upper()
        if priority not in VALID_PRIORITY:
            raise AppError("priority 无效", code="VALIDATION_ERROR", status_code=400)
        due_raw = data.get("due_at")
        due_at = None
        if due_raw:
            due_at = (
                due_raw
                if isinstance(due_raw, datetime)
                else datetime.fromisoformat(str(due_raw).replace("Z", ""))
            )
        model = self.orders.create(
            park_id=park_id,
            title=title,
            description=data.get("description"),
            category=str(data.get("category") or "GENERAL"),
            priority=priority,
            reporter_user_id=self.ctx.user_id or None,
            assignee_user_id=int(data["assignee_user_id"])
            if data.get("assignee_user_id") is not None
            else None,
            unit_id=int(data["unit_id"]) if data.get("unit_id") is not None else None,
            due_at=due_at,
        )
        self.work_items.ensure_from_source(
            source_type="WORK_ORDER",
            source_id=str(model.id),
            item_type=WO_ITEM_TYPE,
            title=f"处理工单 {title[:80]}",
            park_id=park_id,
            priority=priority if priority in {"LOW", "MEDIUM", "HIGH", "URGENT"} else "MEDIUM",
            assignee_user_id=model.assignee_user_id,
            due_at=due_at.isoformat() if due_at else None,
            commit=False,
        )
        self.audit.record(
            action="create",
            resource_type="WORK_ORDER",
            resource_id=model.id,
            park_id=park_id,
            detail={"title": title[:80]},
        )
        self.session.commit()
        log_business_success(
            logger,
            "工单创建成功",
            ctx=self.ctx,
            module="facility_ops",
            action="create_work_order",
            resource_id=model.id,
            park_id=park_id,
        )
        return self._to_dict(model)

    def start_order(self, work_order_id: int) -> dict[str, Any]:
        if not self.ctx.has_permission("work_order:write"):
            raise AppError("无工单维护权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(work_order_id, for_update=True)
        if model.status not in {"OPEN", "IN_PROGRESS"}:
            raise AppError("状态不可开始", code="WORK_ORDER_STATUS_INVALID", status_code=400)
        model.status = "IN_PROGRESS"
        self.orders.save(model)
        self.session.commit()
        return self._to_dict(model)

    def complete_order(self, work_order_id: int) -> dict[str, Any]:
        if not self.ctx.has_permission("work_order:write"):
            raise AppError("无工单维护权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(work_order_id, for_update=True)
        if model.status == "DONE":
            return self._to_dict(model)
        if model.status == "CANCELLED":
            raise AppError("已取消工单不可完成", code="WORK_ORDER_STATUS_INVALID", status_code=400)
        model.status = "DONE"
        model.completed_at = utc_now()
        self.orders.save(model)
        self.work_items.complete_by_source(
            source_type="WORK_ORDER",
            source_id=str(work_order_id),
            item_type=WO_ITEM_TYPE,
            commit=False,
        )
        self.audit.record(
            action="complete",
            resource_type="WORK_ORDER",
            resource_id=model.id,
            park_id=model.park_id,
            detail={},
        )
        self.session.commit()
        return self._to_dict(model)

    def cancel_order(self, work_order_id: int) -> dict[str, Any]:
        if not self.ctx.has_permission("work_order:write"):
            raise AppError("无工单维护权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(work_order_id, for_update=True)
        if model.status == "DONE":
            raise AppError("已完成工单不可取消", code="WORK_ORDER_STATUS_INVALID", status_code=400)
        model.status = "CANCELLED"
        self.orders.save(model)
        self.work_items.cancel_by_source(
            source_type="WORK_ORDER",
            source_id=str(work_order_id),
            item_type=WO_ITEM_TYPE,
            commit=False,
        )
        self.session.commit()
        return self._to_dict(model)

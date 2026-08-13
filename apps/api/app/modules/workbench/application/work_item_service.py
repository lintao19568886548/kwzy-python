"""功能说明：工作台待办/工作项应用服务。"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.business_logging import log_business_success
from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.modules.park_property.infrastructure.park_repository import ParkRepository
from app.modules.workbench.infrastructure.work_item_repository import WorkItemRepository
from app.shared.tenant_context import TenantContext

logger = logging.getLogger(__name__)

VALID_STATUSES = frozenset({"OPEN", "DONE", "CANCELLED"})
VALID_PRIORITIES = frozenset({"LOW", "MEDIUM", "HIGH", "URGENT"})
DEFAULT_ITEM_TYPE = "MANUAL"


class WorkItemService:
    """功能说明：编排待办创建、列表、完成与来源幂等 upsert。"""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.items = WorkItemRepository(session, ctx)
        self.parks = ParkRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def _require(self, work_item_id: int, *, for_update: bool = False):
        model = self.items.get_by_id(work_item_id, for_update=for_update)
        if model is None:
            raise AppError("待办不存在", code="WORK_ITEM_NOT_FOUND", status_code=404)
        return model

    def _parse_dt(self, value: Any) -> Optional[datetime]:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", ""))
        raise AppError("due_at 无效", code="VALIDATION_ERROR", status_code=422)

    def _normalize_priority(self, raw: Any) -> str:
        priority = str(raw or "MEDIUM").upper().strip()
        if priority not in VALID_PRIORITIES:
            raise AppError(
                f"priority 无效，允许: {', '.join(sorted(VALID_PRIORITIES))}",
                code="VALIDATION_ERROR",
                status_code=400,
            )
        return priority

    def _assert_park_access(self, park_id: Optional[int]) -> Optional[int]:
        if park_id is None:
            return None
        pid = int(park_id)
        if not self.parks.exists_in_tenant(pid):
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        if not self.ctx.allows_park(pid):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        return pid

    def _to_dict(self, model) -> dict[str, Any]:
        return {
            "id": model.id,
            "tenant_id": model.tenant_id,
            "park_id": model.park_id,
            "item_type": model.item_type,
            "title": model.title,
            "description": model.description,
            "status": model.status,
            "priority": model.priority,
            "assignee_user_id": model.assignee_user_id,
            "due_at": model.due_at.isoformat() if model.due_at else None,
            "source_type": model.source_type,
            "source_id": model.source_id,
            "completed_at": model.completed_at.isoformat() if model.completed_at else None,
            "completed_by": model.completed_by,
            "sort_order": model.sort_order,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        }

    def list_work_items(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        assignee_user_id: Optional[int] = None,
        item_type: Optional[str] = None,
        mine: bool = False,
    ) -> dict[str, Any]:
        if not self.ctx.has_permission("work_item:read"):
            raise AppError("无待办查看权限", code="PERMISSION_DENIED", status_code=403)
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        if status and status not in VALID_STATUSES:
            raise AppError("status 无效", code="VALIDATION_ERROR", status_code=400)
        if park_id is not None:
            self._assert_park_access(int(park_id))
        items = self.items.list(
            offset=(page - 1) * page_size,
            limit=page_size,
            status=status,
            park_id=park_id,
            assignee_user_id=assignee_user_id,
            item_type=item_type,
            mine=mine,
        )
        total = self.items.count(
            status=status,
            park_id=park_id,
            assignee_user_id=assignee_user_id,
            item_type=item_type,
            mine=mine,
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [self._to_dict(i) for i in items],
        }

    def get_work_item(self, work_item_id: int) -> dict[str, Any]:
        if not self.ctx.has_permission("work_item:read"):
            raise AppError("无待办查看权限", code="PERMISSION_DENIED", status_code=403)
        return self._to_dict(self._require(work_item_id))

    def create_work_item(self, data: dict[str, Any]) -> dict[str, Any]:
        """功能说明：人工创建待办（source=MANUAL，source_id 唯一）。"""

        if not self.ctx.has_permission("work_item:write"):
            raise AppError("无待办维护权限", code="PERMISSION_DENIED", status_code=403)

        title = str(data.get("title") or "").strip()
        if not title:
            raise AppError("title 必填", code="VALIDATION_ERROR", status_code=400)
        if len(title) > 255:
            raise AppError("title 过长", code="VALIDATION_ERROR", status_code=400)

        park_id = data.get("park_id")
        park_id = self._assert_park_access(int(park_id) if park_id is not None else None)

        item_type = str(data.get("item_type") or DEFAULT_ITEM_TYPE).strip() or DEFAULT_ITEM_TYPE
        if len(item_type) > 64:
            raise AppError("item_type 过长", code="VALIDATION_ERROR", status_code=400)

        priority = self._normalize_priority(data.get("priority"))
        due_at = self._parse_dt(data.get("due_at"))
        description = data.get("description")
        if description is not None:
            description = str(description)
        assignee = data.get("assignee_user_id")
        assignee_user_id = int(assignee) if assignee is not None else None
        sort_order = int(data.get("sort_order") or 0)

        # 人工待办：唯一 source 防撞 uk_work_item_source
        source_type = "MANUAL"
        source_id = f"m-{uuid.uuid4().hex[:16]}"

        try:
            model = self.items.create(
                park_id=park_id,
                item_type=item_type,
                title=title,
                description=description,
                status="OPEN",
                priority=priority,
                assignee_user_id=assignee_user_id,
                due_at=due_at,
                source_type=source_type,
                source_id=source_id,
                sort_order=sort_order,
            )
            self.audit.record(
                action="create",
                resource_type="WORK_ITEM",
                resource_id=model.id,
                park_id=park_id,
                detail={"item_type": item_type, "title": title[:80]},
            )
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(
                "待办来源冲突",
                code="WORK_ITEM_SOURCE_CONFLICT",
                status_code=409,
            ) from exc

        log_business_success(
            logger,
            "待办创建成功",
            ctx=self.ctx,
            module="workbench",
            action="create_work_item",
            resource_id=model.id,
            park_id=park_id,
        )
        return self._to_dict(model)

    def complete_work_item(self, work_item_id: int) -> dict[str, Any]:
        if not self.ctx.has_permission("work_item:write"):
            raise AppError("无待办维护权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(work_item_id, for_update=True)
        if model.status == "DONE":
            return self._to_dict(model)
        if model.status == "CANCELLED":
            raise AppError("已取消待办不可完成", code="WORK_ITEM_STATUS_INVALID", status_code=400)
        model.status = "DONE"
        model.completed_at = utc_now()
        model.completed_by = self.ctx.user_id or None
        self.items.save(model)
        self.audit.record(
            action="complete",
            resource_type="WORK_ITEM",
            resource_id=model.id,
            park_id=model.park_id,
            detail={},
        )
        self.session.commit()
        log_business_success(
            logger,
            "待办完成",
            ctx=self.ctx,
            module="workbench",
            action="complete_work_item",
            resource_id=model.id,
            park_id=model.park_id,
        )
        return self._to_dict(model)

    def cancel_work_item(self, work_item_id: int) -> dict[str, Any]:
        if not self.ctx.has_permission("work_item:write"):
            raise AppError("无待办维护权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(work_item_id, for_update=True)
        if model.status == "CANCELLED":
            return self._to_dict(model)
        if model.status == "DONE":
            raise AppError("已完成待办不可取消", code="WORK_ITEM_STATUS_INVALID", status_code=400)
        model.status = "CANCELLED"
        self.items.save(model)
        self.audit.record(
            action="cancel",
            resource_type="WORK_ITEM",
            resource_id=model.id,
            park_id=model.park_id,
            detail={},
        )
        self.session.commit()
        return self._to_dict(model)

    def reopen_work_item(self, work_item_id: int) -> dict[str, Any]:
        if not self.ctx.has_permission("work_item:write"):
            raise AppError("无待办维护权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(work_item_id, for_update=True)
        if model.status == "OPEN":
            return self._to_dict(model)
        model.status = "OPEN"
        model.completed_at = None
        model.completed_by = None
        self.items.save(model)
        self.audit.record(
            action="reopen",
            resource_type="WORK_ITEM",
            resource_id=model.id,
            park_id=model.park_id,
            detail={},
        )
        self.session.commit()
        return self._to_dict(model)

    def ensure_from_source(
        self,
        *,
        source_type: str,
        source_id: str,
        item_type: str,
        title: str,
        description: Optional[str] = None,
        park_id: Optional[int] = None,
        priority: str = "MEDIUM",
        assignee_user_id: Optional[int] = None,
        due_at: Any = None,
    ) -> dict[str, Any]:
        """功能说明：按业务来源幂等打开/复开待办（供账单/合同等域事件调用）。

        不单独校验 work_item:write——调用方须已在自身用例中完成鉴权；
        仍强制 tenant 与 park 存在性。
        """

        source_type = str(source_type or "").strip()
        source_id = str(source_id or "").strip()
        item_type = str(item_type or "").strip()
        if not source_type or not source_id or not item_type:
            raise AppError(
                "source_type/source_id/item_type 必填",
                code="VALIDATION_ERROR",
                status_code=400,
            )
        title = str(title or "").strip()
        if not title:
            raise AppError("title 必填", code="VALIDATION_ERROR", status_code=400)
        park_id = self._assert_park_access(int(park_id) if park_id is not None else None)
        priority = self._normalize_priority(priority)
        due = self._parse_dt(due_at)

        existing = self.items.get_by_source(
            source_type=source_type,
            source_id=source_id,
            item_type=item_type,
            for_update=True,
        )
        if existing is not None:
            # 若已完成/取消则重新打开；刷新展示字段
            existing.title = title
            existing.description = description
            existing.priority = priority
            if park_id is not None:
                existing.park_id = park_id
            if assignee_user_id is not None:
                existing.assignee_user_id = assignee_user_id
            if due is not None:
                existing.due_at = due
            if existing.status != "OPEN":
                existing.status = "OPEN"
                existing.completed_at = None
                existing.completed_by = None
            self.items.save(existing)
            self.session.commit()
            return self._to_dict(existing)

        try:
            model = self.items.create(
                park_id=park_id,
                item_type=item_type,
                title=title,
                description=description,
                status="OPEN",
                priority=priority,
                assignee_user_id=assignee_user_id,
                due_at=due,
                source_type=source_type,
                source_id=source_id,
            )
            self.audit.record(
                action="ensure",
                resource_type="WORK_ITEM",
                resource_id=model.id,
                park_id=park_id,
                detail={
                    "source_type": source_type,
                    "source_id": source_id,
                    "item_type": item_type,
                },
            )
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            # 并发插入：再读一次
            existing = self.items.get_by_source(
                source_type=source_type,
                source_id=source_id,
                item_type=item_type,
            )
            if existing is None:
                raise AppError(
                    "待办来源冲突",
                    code="WORK_ITEM_SOURCE_CONFLICT",
                    status_code=409,
                )
            return self._to_dict(existing)
        return self._to_dict(model)

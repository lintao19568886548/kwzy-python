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
from app.modules.workbench.domain.registry import is_safe_deep_link
from app.modules.workbench.infrastructure.automation_repository import AutomationRepository
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
        self.automation = AutomationRepository(session, ctx)
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
            "deep_link": model.deep_link,
            "escalation_level": model.escalation_level,
            "reassigned_from_user_id": model.reassigned_from_user_id,
            "last_event_id": model.last_event_id,
            "source_owned": model.source_owned,
            "lock_version": model.lock_version,
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
        total, items = self.items.list_with_total(
            offset=(page - 1) * page_size,
            limit=page_size,
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
        deep_link = str(data.get("deep_link") or "").strip() or None
        if not is_safe_deep_link(deep_link):
            raise AppError("deep_link 无效", code="VALIDATION_ERROR", status_code=400)

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
                deep_link=deep_link,
                source_owned=False,
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

    def _assert_manual_transition(
        self,
        model,
        *,
        expected_version: Optional[int],
        override_reason: Optional[str],
    ) -> None:
        if expected_version is None:
            raise AppError("expected_version 必填", code="VALIDATION_ERROR", status_code=400)
        if int(model.lock_version) != int(expected_version):
            raise AppError(
                "待办已被其他操作更新",
                code="WORK_ITEM_VERSION_CONFLICT",
                status_code=409,
                data={"current_version": int(model.lock_version)},
            )
        if model.source_owned:
            if not self.ctx.has_permission("work_item:override_source"):
                raise AppError(
                    "来源待办必须由业务来源关闭",
                    code="WORK_ITEM_SOURCE_OWNED",
                    status_code=409,
                )
            reason = str(override_reason or "").strip()
            if len(reason) < 5:
                raise AppError(
                    "覆盖来源待办必须填写至少 5 个字符的原因",
                    code="OVERRIDE_REASON_REQUIRED",
                    status_code=400,
                )

    def complete_work_item(
        self,
        work_item_id: int,
        *,
        expected_version: Optional[int] = None,
        override_reason: Optional[str] = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        if not self.ctx.has_permission("work_item:write"):
            raise AppError("无待办维护权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(work_item_id, for_update=True)
        self._assert_manual_transition(
            model, expected_version=expected_version, override_reason=override_reason
        )
        if model.status == "DONE":
            return self._to_dict(model)
        if model.status == "CANCELLED":
            raise AppError("已取消待办不可完成", code="WORK_ITEM_STATUS_INVALID", status_code=400)
        model.status = "DONE"
        model.completed_at = utc_now()
        model.completed_by = self.ctx.user_id or None
        model.lock_version = int(model.lock_version) + 1
        self.items.save(model)
        self.audit.record(
            action="complete",
            resource_type="WORK_ITEM",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"override_reason": override_reason if model.source_owned else None},
        )
        if commit:
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

    def cancel_work_item(
        self,
        work_item_id: int,
        *,
        expected_version: Optional[int] = None,
        override_reason: Optional[str] = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        if not self.ctx.has_permission("work_item:write"):
            raise AppError("无待办维护权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(work_item_id, for_update=True)
        self._assert_manual_transition(
            model, expected_version=expected_version, override_reason=override_reason
        )
        if model.status == "CANCELLED":
            return self._to_dict(model)
        if model.status == "DONE":
            raise AppError("已完成待办不可取消", code="WORK_ITEM_STATUS_INVALID", status_code=400)
        model.status = "CANCELLED"
        model.lock_version = int(model.lock_version) + 1
        self.items.save(model)
        self.audit.record(
            action="cancel",
            resource_type="WORK_ITEM",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"override_reason": override_reason if model.source_owned else None},
        )
        if commit:
            self.session.commit()
        return self._to_dict(model)

    def reopen_work_item(
        self,
        work_item_id: int,
        *,
        expected_version: Optional[int] = None,
        override_reason: Optional[str] = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        if not self.ctx.has_permission("work_item:write"):
            raise AppError("无待办维护权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(work_item_id, for_update=True)
        self._assert_manual_transition(
            model, expected_version=expected_version, override_reason=override_reason
        )
        if model.status == "OPEN":
            return self._to_dict(model)
        model.status = "OPEN"
        model.completed_at = None
        model.completed_by = None
        model.lock_version = int(model.lock_version) + 1
        self.items.save(model)
        self.audit.record(
            action="reopen",
            resource_type="WORK_ITEM",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"override_reason": override_reason if model.source_owned else None},
        )
        if commit:
            self.session.commit()
        return self._to_dict(model)

    def reassign_work_item(
        self,
        work_item_id: int,
        *,
        expected_version: int,
        assignee_user_id: int,
        reason: str,
    ) -> dict[str, Any]:
        if not self.ctx.has_permission("work_item:reassign"):
            raise AppError("无待办改派权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(work_item_id, for_update=True)
        if model.status != "OPEN":
            raise AppError("仅开放待办可改派", code="WORK_ITEM_STATUS_INVALID", status_code=409)
        if int(model.lock_version) != int(expected_version):
            raise AppError(
                "待办已被其他操作更新",
                code="WORK_ITEM_VERSION_CONFLICT",
                status_code=409,
                data={"current_version": int(model.lock_version)},
            )
        if not self.automation.user_exists(int(assignee_user_id)):
            raise AppError("改派用户不存在", code="ASSIGNEE_NOT_FOUND", status_code=400)
        old_assignee = model.assignee_user_id
        if old_assignee == int(assignee_user_id):
            return self._to_dict(model)
        model.reassigned_from_user_id = old_assignee
        model.assignee_user_id = int(assignee_user_id)
        model.lock_version = int(model.lock_version) + 1
        self.items.save(model)
        self.audit.record(
            action="reassign",
            resource_type="WORK_ITEM",
            resource_id=model.id,
            park_id=model.park_id,
            detail={
                "from_user_id": old_assignee,
                "to_user_id": int(assignee_user_id),
                "reason": str(reason)[:200],
            },
        )
        self.session.commit()
        return self._to_dict(model)

    def escalate_by_source(
        self,
        *,
        source_type: str,
        source_id: str,
        item_type: str,
        event_id: int,
        assignee_user_id: Optional[int] = None,
        commit: bool = True,
    ) -> Optional[dict[str, Any]]:
        existing = self.items.get_by_source(
            source_type=source_type,
            source_id=source_id,
            item_type=item_type,
            for_update=True,
        )
        if existing is None or existing.status != "OPEN":
            return None
        if existing.last_event_id == int(event_id):
            return self._to_dict(existing)
        if assignee_user_id is not None and existing.assignee_user_id != int(assignee_user_id):
            existing.reassigned_from_user_id = existing.assignee_user_id
            existing.assignee_user_id = int(assignee_user_id)
        existing.escalation_level = int(existing.escalation_level) + 1
        existing.priority = "URGENT"
        existing.last_event_id = int(event_id)
        existing.lock_version = int(existing.lock_version) + 1
        self.items.save(existing)
        self.audit.record(
            action="escalate",
            resource_type="WORK_ITEM",
            resource_id=existing.id,
            park_id=existing.park_id,
            detail={"event_id": int(event_id), "level": int(existing.escalation_level)},
        )
        if commit:
            self.session.commit()
        return self._to_dict(existing)

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
        deep_link: Optional[str] = None,
        last_event_id: Optional[int] = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        """功能说明：按业务来源幂等打开/复开待办（供账单/合同等域事件调用）。

        不单独校验 work_item:write——调用方须已在自身用例中完成鉴权；
        仍强制 tenant 与 park 存在性。
        commit=False 时仅 flush，由调用方统一提交（同事务挂接）。
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
        if not is_safe_deep_link(deep_link):
            raise AppError("deep_link 无效", code="VALIDATION_ERROR", status_code=400)

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
            if deep_link is not None:
                existing.deep_link = deep_link
            if last_event_id is not None and existing.last_event_id != int(last_event_id):
                existing.last_event_id = int(last_event_id)
            if existing.status != "OPEN":
                existing.status = "OPEN"
                existing.completed_at = None
                existing.completed_by = None
            existing.source_owned = True
            existing.lock_version = int(existing.lock_version) + 1
            self.items.save(existing)
            if commit:
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
                deep_link=deep_link,
                source_owned=True,
                last_event_id=last_event_id,
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
            if commit:
                self.session.commit()
        except IntegrityError:
            if commit:
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

    def complete_by_source(
        self,
        *,
        source_type: str,
        source_id: str,
        item_type: str,
        commit: bool = True,
    ) -> Optional[dict[str, Any]]:
        """按来源完成待办；不存在则静默跳过。"""

        existing = self.items.get_by_source(
            source_type=source_type,
            source_id=source_id,
            item_type=item_type,
            for_update=True,
        )
        if existing is None:
            return None
        if existing.status == "DONE":
            return self._to_dict(existing)
        if existing.status == "CANCELLED":
            return self._to_dict(existing)
        existing.status = "DONE"
        existing.completed_at = utc_now()
        existing.completed_by = self.ctx.user_id or None
        existing.lock_version = int(existing.lock_version) + 1
        self.items.save(existing)
        self.audit.record(
            action="complete",
            resource_type="WORK_ITEM",
            resource_id=existing.id,
            park_id=existing.park_id,
            detail={"via": "source"},
        )
        if commit:
            self.session.commit()
        return self._to_dict(existing)

    def cancel_by_source(
        self,
        *,
        source_type: str,
        source_id: str,
        item_type: str,
        commit: bool = True,
    ) -> Optional[dict[str, Any]]:
        """按来源取消待办；不存在或已终态则静默跳过。"""

        existing = self.items.get_by_source(
            source_type=source_type,
            source_id=source_id,
            item_type=item_type,
            for_update=True,
        )
        if existing is None:
            return None
        if existing.status in {"CANCELLED", "DONE"}:
            return self._to_dict(existing)
        existing.status = "CANCELLED"
        existing.lock_version = int(existing.lock_version) + 1
        self.items.save(existing)
        self.audit.record(
            action="cancel",
            resource_type="WORK_ITEM",
            resource_id=existing.id,
            park_id=existing.park_id,
            detail={"via": "source"},
        )
        if commit:
            self.session.commit()
        return self._to_dict(existing)

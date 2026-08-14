"""功能说明：招商线索应用服务（创建/跟进/输单/转化）。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.business_logging import log_business_success
from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.modules.investment.domain.entities import (
    LeadActivityEntity,
    LeadAssignmentEventEntity,
    LeadMergeLinkEntity,
    LeadUnitLockEntity,
)
from app.modules.investment.domain.rules import (
    CONVERTIBLE,
    OPEN_STATUSES,
    assert_activity_type,
    assert_status_transition,
    mask_phone,
    normalize_intent_level,
    normalize_name_key,
    normalize_phone,
    normalize_phone_key,
    normalize_status,
)
from app.modules.investment.application.assignment_service import AssignmentRuleService
from app.modules.investment.application.intent_service import IntentService
from app.modules.investment.infrastructure.crm_repository import (
    LeadActivityRepository,
    LeadAssigneeRepository,
    LeadAssignmentRepository,
    LeadMergeRepository,
    LeadUnitLockRepository,
)
from app.modules.investment.infrastructure.lead_repository import LeadRepository
from app.modules.investment.infrastructure.mappers import (
    LeadActivityMapper,
    LeadAssignmentEventMapper,
    LeadMergeLinkMapper,
    LeadUnitLockMapper,
)
from app.modules.lease.application.lease_service import LeaseService
from app.modules.park_property.infrastructure.park_repository import ParkRepository
from app.modules.park_property.infrastructure.unit_repository import UnitRepository
from app.modules.party.application.party_service import PartyService
from app.modules.workbench.application.automation_service import WorkbenchAutomationService
from app.modules.workbench.application.work_item_service import WorkItemService
from app.shared.tenant_context import TenantContext

logger = logging.getLogger(__name__)

LEAD_FOLLOW_ITEM_TYPE = "LEAD_FOLLOW"


class LeadService:
    """功能说明：编排线索生命周期；转化时创建主体与可选合同草稿。"""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.leads = LeadRepository(session, ctx)
        self.assignees = LeadAssigneeRepository(session, ctx)
        self.activities = LeadActivityRepository(session, ctx)
        self.assignments = LeadAssignmentRepository(session, ctx)
        self.merges = LeadMergeRepository(session, ctx)
        self.unit_locks = LeadUnitLockRepository(session, ctx)
        self.units = UnitRepository(session, ctx)
        self.parks = ParkRepository(session, ctx)
        self.parties = PartyService(session, ctx)
        self.leases = LeaseService(session, ctx)
        self.work_items = WorkItemService(session, ctx)
        self.events = WorkbenchAutomationService(session, ctx)
        self.audit = AuditRecorder(session, ctx)
        self.assignment_rules = AssignmentRuleService(session, ctx)
        self.intents = IntentService(session, ctx)

    def _require(self, lead_id: int, *, for_update: bool = False, manage: bool = False):
        m = self.leads.get_by_id(lead_id, for_update=for_update, manage=manage)
        if m is None:
            raise AppError("线索不存在", code="LEAD_NOT_FOUND", status_code=404)
        return m

    def _assert_park(self, park_id: int) -> int:
        pid = int(park_id)
        if not self.parks.exists_in_tenant(pid):
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        if not self.ctx.allows_park(pid):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        return pid

    def _is_manager(self) -> bool:
        return self.ctx.has_permission("lead:manage")

    def _assert_can_write(self, model) -> None:
        if self._is_manager():
            return
        if not self.ctx.has_permission("lead:write") or int(model.owner_user_id or 0) != int(self.ctx.user_id or 0):
            raise AppError("无线索维护权限", code="PERMISSION_DENIED", status_code=403)

    def _assert_expected_version(self, model, expected_version: Any) -> None:
        if expected_version is None:
            raise AppError("expected_version 必填", code="EXPECTED_VERSION_REQUIRED", status_code=400)
        if int(expected_version) != int(model.lock_version):
            raise AppError("线索版本冲突", code="LEAD_VERSION_CONFLICT", status_code=409)

    @staticmethod
    def _parse_datetime(value: Any, field: str) -> Optional[datetime]:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise AppError(f"{field} 无效", code="VALIDATION_ERROR", status_code=400) from exc
        else:
            raise AppError(f"{field} 无效", code="VALIDATION_ERROR", status_code=400)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    def _assert_owner(self, owner_user_id: int) -> int:
        owner_id = self.assignees.active_id(owner_user_id)
        if owner_id is None:
            raise AppError("负责人不存在或不可用", code="LEAD_OWNER_INVALID", status_code=400)
        return owner_id

    def _add_assignment_event(
        self,
        model,
        *,
        event_type: str,
        from_owner: Optional[int],
        to_owner: Optional[int],
        reason: Optional[str] = None,
    ) -> None:
        self.assignments.add(
            LeadAssignmentEventMapper.new_model(
                LeadAssignmentEventEntity(
                    tenant_id=self.ctx.tenant_id,
                    park_id=int(model.park_id),
                    lead_id=int(model.id),
                    event_type=event_type,
                    from_owner_user_id=from_owner,
                    to_owner_user_id=to_owner,
                    reason=(reason or "").strip() or None,
                    actor_user_id=self.ctx.user_id or None,
                    occurred_at=utc_now(),
                )
            )
        )

    def _add_activity(
        self,
        model,
        *,
        activity_type: str,
        content: Optional[str] = None,
        next_follow_up_at: Optional[datetime] = None,
        stage_from: Optional[str] = None,
        stage_to: Optional[str] = None,
        attributes: Optional[dict[str, Any]] = None,
    ) -> None:
        self.activities.add(
            LeadActivityMapper.new_model(
                LeadActivityEntity(
                    tenant_id=self.ctx.tenant_id,
                    park_id=int(model.park_id),
                    lead_id=int(model.id),
                    actor_user_id=self.ctx.user_id or None,
                    activity_type=activity_type,
                    content=(content or "").strip() or None,
                    occurred_at=utc_now(),
                    next_follow_up_at=next_follow_up_at,
                    stage_from=stage_from,
                    stage_to=stage_to,
                    attributes_json=attributes or {},
                )
            )
        )

    def _to_dict(self, model) -> dict[str, Any]:
        public_summary = (
            model.pool_status == "PUBLIC"
            and int(model.owner_user_id or 0) != int(self.ctx.user_id or 0)
            and not self._is_manager()
        )
        return {
            "id": model.id,
            "tenant_id": model.tenant_id,
            "park_id": model.park_id,
            "name": model.name,
            "contact_phone": mask_phone(model.contact_phone) if public_summary else model.contact_phone,
            "contact_name": None if public_summary else model.contact_name,
            "agent_name": model.agent_name,
            "intent_level": model.intent_level,
            "intent_area": str(model.intent_area) if model.intent_area is not None else None,
            "desired_usage": model.desired_usage,
            "budget_unit_price": str(model.budget_unit_price) if model.budget_unit_price is not None else None,
            "status": model.status,
            "source_type": model.source_type,
            "source_ref": model.source_ref,
            "pool_status": model.pool_status,
            "remark": model.remark,
            "owner_user_id": model.owner_user_id,
            "party_id": model.party_id,
            "lease_id": model.lease_id,
            "converted_at": model.converted_at.isoformat() if model.converted_at else None,
            "lost_reason": model.lost_reason,
            "merged_into_lead_id": model.merged_into_lead_id,
            "assigned_at": model.assigned_at.isoformat() if model.assigned_at else None,
            "first_contact_at": model.first_contact_at.isoformat() if model.first_contact_at else None,
            "last_activity_at": model.last_activity_at.isoformat() if model.last_activity_at else None,
            "next_follow_up_at": model.next_follow_up_at.isoformat() if model.next_follow_up_at else None,
            "recycle_due_at": model.recycle_due_at.isoformat() if model.recycle_due_at else None,
            "overdue": bool(model.next_follow_up_at and model.next_follow_up_at < utc_now() and model.status in OPEN_STATUSES),
            "lock_version": model.lock_version,
            "public_summary": public_summary,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        }

    def _open_follow_todo(self, model) -> None:
        due = model.next_follow_up_at or (utc_now() + timedelta(days=3))
        self.work_items.ensure_from_source(
            source_type="LEAD",
            source_id=str(model.id),
            item_type=LEAD_FOLLOW_ITEM_TYPE,
            title=f"跟进线索 {model.name}",
            description=f"phone={model.contact_phone}",
            park_id=int(model.park_id),
            priority="MEDIUM",
            assignee_user_id=model.owner_user_id,
            due_at=due.isoformat(),
            commit=False,
        )

    def _close_follow_todo(self, lead_id: int, *, done: bool) -> None:
        if done:
            self.work_items.complete_by_source(
                source_type="LEAD",
                source_id=str(lead_id),
                item_type=LEAD_FOLLOW_ITEM_TYPE,
                commit=False,
            )
        else:
            self.work_items.cancel_by_source(
                source_type="LEAD",
                source_id=str(lead_id),
                item_type=LEAD_FOLLOW_ITEM_TYPE,
                commit=False,
            )

    def list_leads(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        keyword: Optional[str] = None,
        owner_user_id: Optional[int] = None,
        pool_status: Optional[str] = None,
        source_type: Optional[str] = None,
        created_from: Any = None,
        created_to: Any = None,
    ) -> dict[str, Any]:
        if not self.ctx.has_permission("lead:read"):
            raise AppError("无线索查看权限", code="PERMISSION_DENIED", status_code=403)
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        if park_id is not None:
            self._assert_park(int(park_id))
        normalized_status = normalize_status(status) if status else None
        start = self._parse_datetime(created_from, "created_from")
        end = self._parse_datetime(created_to, "created_to")
        if start is not None and end is not None and start >= end:
            raise AppError("created_from 必须早于 created_to", code="VALIDATION_ERROR", status_code=400)
        items = self.leads.list(
            offset=(page - 1) * page_size,
            limit=page_size,
            status=normalized_status,
            park_id=park_id,
            keyword=keyword,
            owner_user_id=owner_user_id,
            pool_status=pool_status,
            source_type=source_type,
            created_from=start,
            created_to=end,
        )
        total = self.leads.count(
            status=normalized_status,
            park_id=park_id,
            keyword=keyword,
            owner_user_id=owner_user_id,
            pool_status=pool_status,
            source_type=source_type,
            created_from=start,
            created_to=end,
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [self._to_dict(x) for x in items],
        }

    def get_lead(self, lead_id: int) -> dict[str, Any]:
        if not self.ctx.has_permission("lead:read"):
            raise AppError("无线索查看权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(lead_id)
        return {
            **self._to_dict(model),
            "activities": [self._activity_dict(row) for row in self.activities.list_for_lead(lead_id)],
            "assignment_events": [
                self._assignment_dict(row) for row in self.assignments.list_for_lead(lead_id)
            ],
            "merged_sources": [row.source_lead_id for row in self.merges.list_for_target(lead_id)],
            "unit_locks": [self._lock_dict(row) for row in self.unit_locks.list_for_lead(lead_id)],
        }

    def list_assignees(self) -> list[dict[str, Any]]:
        if not self._is_manager():
            raise AppError("无线索分配权限", code="PERMISSION_DENIED", status_code=403)
        return self.assignees.list_active()

    @staticmethod
    def _activity_dict(row) -> dict[str, Any]:
        return {
            "id": row.id,
            "activity_type": row.activity_type,
            "content": row.content,
            "actor_user_id": row.actor_user_id,
            "occurred_at": row.occurred_at.isoformat(),
            "next_follow_up_at": row.next_follow_up_at.isoformat() if row.next_follow_up_at else None,
            "stage_from": row.stage_from,
            "stage_to": row.stage_to,
            "attributes": row.attributes_json or {},
        }

    @staticmethod
    def _assignment_dict(row) -> dict[str, Any]:
        return {
            "id": row.id,
            "event_type": row.event_type,
            "from_owner_user_id": row.from_owner_user_id,
            "to_owner_user_id": row.to_owner_user_id,
            "reason": row.reason,
            "actor_user_id": row.actor_user_id,
            "occurred_at": row.occurred_at.isoformat(),
            "rule_version_id": row.rule_version_id,
            "trigger": row.trigger,
            "decision": row.decision_json or {},
        }

    @staticmethod
    def _lock_dict(row) -> dict[str, Any]:
        return {
            "id": row.id,
            "lead_id": row.lead_id,
            "unit_id": row.unit_id,
            "lease_id": row.lease_id,
            "intent_application_id": row.intent_application_id,
            "intent_version_id": row.intent_version_id,
            "status": row.status,
            "expires_at": row.expires_at.isoformat(),
            "released_at": row.released_at.isoformat() if row.released_at else None,
            "consumed_at": row.consumed_at.isoformat() if row.consumed_at else None,
            "lock_version": row.lock_version,
        }

    def create_lead(self, data: dict[str, Any]) -> dict[str, Any]:
        if not self.ctx.has_permission("lead:write"):
            raise AppError("无线索维护权限", code="PERMISSION_DENIED", status_code=403)
        park_id = self._assert_park(int(data["park_id"]))
        name = str(data.get("name") or "").strip()
        if not name:
            raise AppError("name 必填", code="VALIDATION_ERROR", status_code=400)
        try:
            phone = normalize_phone(str(data.get("contact_phone") or ""))
            normalized_phone = normalize_phone_key(phone)
            intent = normalize_intent_level(data.get("intent_level"))
        except ValueError as exc:
            raise AppError(str(exc), code="VALIDATION_ERROR", status_code=400) from exc
        area = data.get("intent_area")
        intent_area = Decimal(str(area)) if area is not None and area != "" else None
        if intent_area is not None and intent_area < 0:
            raise AppError("intent_area 不得为负", code="VALIDATION_ERROR", status_code=400)

        budget_raw = data.get("budget_unit_price")
        budget = Decimal(str(budget_raw)) if budget_raw not in (None, "") else None
        if budget is not None and budget < 0:
            raise AppError("budget_unit_price 不得为负", code="VALIDATION_ERROR", status_code=400)

        normalized_name = normalize_name_key(name)
        source_type = str(data.get("source_type") or "MANUAL").strip().upper()
        source_ref = (str(data["source_ref"]).strip() if data.get("source_ref") else None)
        duplicates = self.leads.duplicate_candidates(
            normalized_name=normalized_name,
            normalized_phone=normalized_phone,
            source_type=source_type,
            source_ref=source_ref,
        )
        override_reason = (str(data.get("duplicate_override_reason") or "").strip() or None)
        if duplicates and not override_reason:
            raise AppError(
                "发现可能重复的线索",
                code="LEAD_DUPLICATE",
                status_code=409,
                data={
                    "candidates": [
                        self._duplicate_summary(
                            row,
                            normalized_name=normalized_name,
                            normalized_phone=normalized_phone,
                            source_type=source_type,
                            source_ref=source_ref,
                        )
                        for row in duplicates
                    ]
                },
            )

        requested_pool = str(data.get("pool_status") or "PRIVATE").strip().upper()
        if requested_pool not in {"PRIVATE", "PUBLIC"}:
            raise AppError("pool_status 无效", code="VALIDATION_ERROR", status_code=400)
        owner = data.get("owner_user_id")
        if requested_pool == "PUBLIC":
            owner_user_id = None
        elif owner is None:
            owner_user_id = int(self.ctx.user_id or 0) or None
        else:
            owner_user_id = self._assert_owner(int(owner))
            if owner_user_id != int(self.ctx.user_id or 0) and not self._is_manager():
                raise AppError("无分配负责人权限", code="PERMISSION_DENIED", status_code=403)
        if requested_pool == "PRIVATE" and owner_user_id is None:
            raise AppError("私有线索必须有负责人", code="LEAD_OWNER_INVALID", status_code=400)

        now = utc_now()
        next_follow = self._parse_datetime(data.get("next_follow_up_at"), "next_follow_up_at")
        if owner_user_id and next_follow is None:
            next_follow = now + timedelta(days=3)

        try:
            model = self.leads.create(
                park_id=park_id,
                name=name,
                contact_phone=phone,
                contact_name=(str(data["contact_name"]).strip() if data.get("contact_name") else None),
                agent_name=(str(data["agent_name"]).strip() if data.get("agent_name") else None),
                intent_level=intent,
                intent_area=intent_area,
                desired_usage=(str(data["desired_usage"]).strip().upper() if data.get("desired_usage") else None),
                budget_unit_price=budget,
                status="NEW",
                normalized_name=normalized_name,
                normalized_phone=normalized_phone,
                source_type=source_type,
                source_ref=source_ref,
                duplicate_override_reason=override_reason,
                pool_status=requested_pool,
                remark=data.get("remark"),
                owner_user_id=owner_user_id,
                assigned_at=now if owner_user_id else None,
                next_follow_up_at=next_follow,
                recycle_due_at=(now + timedelta(days=7)) if owner_user_id else None,
            )
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError("来源线索已存在", code="LEAD_SOURCE_DUPLICATE", status_code=409) from exc
        assignment_result = None
        should_auto_assign = bool(data.get("auto_assign", True)) and data.get("owner_user_id") is None
        if should_auto_assign:
            trigger = "CHANNEL_INTAKE" if source_type.startswith("CHANNEL:") else "MANUAL_CREATE"
            assignment_result = self.assignment_rules.execute_for_lead(model, trigger=trigger)
        if assignment_result is None:
            self._add_assignment_event(
                model,
                event_type="ASSIGN" if owner_user_id else "PUBLIC_CREATE",
                from_owner=None,
                to_owner=owner_user_id,
                reason="create",
            )
            if owner_user_id:
                self._open_follow_todo(model)
        owner_user_id = model.owner_user_id
        next_follow = model.next_follow_up_at
        self.events.emit_event(
            event_type="LEAD_CREATED",
            source_type="LEAD",
            source_id=str(model.id),
            idempotency_key=f"lead-created:{model.id}",
            park_id=park_id,
            payload={
                "title": f"新招商线索 {name[:80]}",
                "description": "招商线索待跟进",
                "priority": "MEDIUM",
                "assignee_user_id": owner_user_id,
                "due_at": next_follow.isoformat() if next_follow else None,
                "deep_link": "/leads",
                "park_id": park_id,
            },
            commit=False,
            enforce_permission=False,
        )
        self.audit.record(
            action="create",
            resource_type="LEAD",
            resource_id=model.id,
            park_id=park_id,
            detail={"name": name[:80], "source_type": source_type, "override": bool(override_reason)},
        )
        self.session.commit()
        log_business_success(
            logger,
            "线索创建成功",
            ctx=self.ctx,
            module="investment",
            action="create_lead",
            resource_id=model.id,
            park_id=park_id,
        )
        return self._to_dict(model)

    def _duplicate_summary(
        self,
        model,
        *,
        normalized_name: Optional[str] = None,
        normalized_phone: Optional[str] = None,
        source_type: Optional[str] = None,
        source_ref: Optional[str] = None,
    ) -> dict[str, Any]:
        full = self._is_manager() or int(model.owner_user_id or 0) == int(self.ctx.user_id or 0)
        reasons = []
        if normalized_phone and model.normalized_phone == normalized_phone:
            reasons.append("PHONE")
        if normalized_name and model.normalized_name == normalized_name:
            reasons.append("NAME")
        if (
            source_type
            and source_ref
            and model.source_type == source_type
            and model.source_ref == source_ref
        ):
            reasons.append("SOURCE_REF")
        return {
            "id": model.id,
            "park_id": model.park_id,
            "name": model.name,
            "contact_phone": model.contact_phone if full else mask_phone(model.contact_phone),
            "status": model.status,
            "pool_status": model.pool_status,
            "owner_user_id": model.owner_user_id if full else None,
            "reasons": reasons,
        }

    def update_lead(self, lead_id: int, data: dict[str, Any]) -> dict[str, Any]:
        model = self._require(lead_id, for_update=True)
        self._assert_can_write(model)
        self._assert_expected_version(model, data.pop("expected_version", None))
        if model.status in {"WON", "LOST", "CANCELLED", "MERGED"}:
            raise AppError("终态线索不可修改", code="LEAD_STATUS_INVALID", status_code=400)

        previous_status = model.status

        if "name" in data and data["name"] is not None:
            name = str(data["name"]).strip()
            if not name:
                raise AppError("name 不能为空", code="VALIDATION_ERROR", status_code=400)
            model.name = name
            model.normalized_name = normalize_name_key(name)
        if "contact_phone" in data and data["contact_phone"] is not None:
            try:
                model.contact_phone = normalize_phone(str(data["contact_phone"]))
                model.normalized_phone = normalize_phone_key(model.contact_phone)
            except ValueError as exc:
                raise AppError(str(exc), code="VALIDATION_ERROR", status_code=400) from exc
        if "contact_name" in data:
            model.contact_name = (
                str(data["contact_name"]).strip() if data["contact_name"] else None
            )
        if "agent_name" in data:
            model.agent_name = str(data["agent_name"]).strip() if data["agent_name"] else None
        if "intent_level" in data:
            try:
                model.intent_level = normalize_intent_level(data.get("intent_level"))
            except ValueError as exc:
                raise AppError(str(exc), code="VALIDATION_ERROR", status_code=400) from exc
        if "intent_area" in data:
            raw = data.get("intent_area")
            model.intent_area = Decimal(str(raw)) if raw not in (None, "") else None
            if model.intent_area is not None and model.intent_area < 0:
                raise AppError("intent_area 不得为负", code="VALIDATION_ERROR", status_code=400)
        if "desired_usage" in data:
            model.desired_usage = str(data["desired_usage"]).strip().upper() if data["desired_usage"] else None
        if "budget_unit_price" in data:
            raw_budget = data.get("budget_unit_price")
            model.budget_unit_price = Decimal(str(raw_budget)) if raw_budget not in (None, "") else None
            if model.budget_unit_price is not None and model.budget_unit_price < 0:
                raise AppError("budget_unit_price 不得为负", code="VALIDATION_ERROR", status_code=400)
        if "remark" in data:
            model.remark = data.get("remark")
        if "status" in data and data["status"]:
            reason = str(data.get("stage_reason") or "").strip()
            try:
                target = normalize_status(str(data["status"]))
                if target in {"WON", "LOST", "MERGED"}:
                    raise AppError(
                        "该终态须使用专用命令",
                        code="LEAD_STATUS_COMMAND_REQUIRED",
                        status_code=400,
                    )
                open_order = ["NEW", "CONTACTING", "VISITING", "QUOTING", "NEGOTIATING"]
                regression = (
                    model.status in open_order
                    and target in open_order
                    and open_order.index(target) < open_order.index(model.status)
                )
                if regression and (not self._is_manager() or not reason):
                    raise AppError(
                        "阶段回退仅允许管理员并须填写原因",
                        code="LEAD_STAGE_OVERRIDE_REQUIRED",
                        status_code=400,
                    )
                if target == "CANCELLED" and not reason:
                    raise AppError("取消原因必填", code="VALIDATION_ERROR", status_code=400)
                model.status = assert_status_transition(
                    model.status,
                    target,
                    allow_regression=regression,
                )
            except ValueError as exc:
                raise AppError(str(exc), code="LEAD_STATUS_INVALID", status_code=400) from exc

        if model.status in OPEN_STATUSES:
            self._open_follow_todo(model)

        if model.status != previous_status:
            self._add_activity(
                model,
                activity_type="SYSTEM",
                content=(str(data.get("stage_reason") or "").strip() or "stage update"),
                stage_from=previous_status,
                stage_to=model.status,
            )
            if model.status == "CANCELLED":
                self._close_follow_todo(lead_id, done=False)

        model.lock_version += 1

        self.leads.save(model)
        self.audit.record(
            action="update",
            resource_type="LEAD",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"fields": sorted(data.keys()), "version": model.lock_version},
        )
        self.session.commit()
        return self._to_dict(model)

    def mark_lost(
        self,
        lead_id: int,
        *,
        reason: Optional[str] = None,
        expected_version: Optional[int] = None,
    ) -> dict[str, Any]:
        model = self._require(lead_id, for_update=True)
        self._assert_can_write(model)
        self._assert_expected_version(model, expected_version)
        normalized_reason = (reason or "").strip()
        if not normalized_reason:
            raise AppError("输单原因必填", code="VALIDATION_ERROR", status_code=400)
        previous_status = model.status
        try:
            model.status = assert_status_transition(model.status, "LOST")
        except ValueError as exc:
            raise AppError(str(exc), code="LEAD_STATUS_INVALID", status_code=400) from exc
        model.lost_reason = normalized_reason
        model.lock_version += 1
        self.leads.save(model)
        self._add_activity(
            model,
            activity_type="SYSTEM",
            content=normalized_reason,
            stage_from=previous_status,
            stage_to="LOST",
        )
        self._close_follow_todo(lead_id, done=False)
        self.audit.record(
            action="lose",
            resource_type="LEAD",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"reason": (model.lost_reason or "")[:80]},
        )
        self.session.commit()
        return self._to_dict(model)

    def duplicate_candidates(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        if not self.ctx.has_permission("lead:read"):
            raise AppError("无线索查看权限", code="PERMISSION_DENIED", status_code=403)
        self._assert_park(int(data["park_id"]))
        name = str(data.get("name") or "").strip()
        phone = normalize_phone(str(data.get("contact_phone") or ""))
        normalized_name = normalize_name_key(name)
        normalized_phone = normalize_phone_key(phone)
        source_type = str(data.get("source_type") or "MANUAL").strip().upper()
        source_ref = str(data["source_ref"]).strip() if data.get("source_ref") else None
        rows = self.leads.duplicate_candidates(
            normalized_name=normalized_name,
            normalized_phone=normalized_phone,
            source_type=source_type,
            source_ref=source_ref,
        )
        return [
            self._duplicate_summary(
                row,
                normalized_name=normalized_name,
                normalized_phone=normalized_phone,
                source_type=source_type,
                source_ref=source_ref,
            )
            for row in rows
        ]

    def add_activity(self, lead_id: int, data: dict[str, Any]) -> dict[str, Any]:
        model = self._require(lead_id, for_update=True)
        self._assert_can_write(model)
        self._assert_expected_version(model, data.get("expected_version"))
        if model.status not in OPEN_STATUSES:
            raise AppError("终态线索不可新增跟进", code="LEAD_STATUS_INVALID", status_code=400)
        try:
            activity_type = assert_activity_type(str(data.get("activity_type") or "NOTE"))
        except ValueError as exc:
            raise AppError(str(exc), code="VALIDATION_ERROR", status_code=400) from exc
        content = str(data.get("content") or "").strip()
        if not content:
            raise AppError("跟进内容必填", code="VALIDATION_ERROR", status_code=400)
        next_follow = self._parse_datetime(data.get("next_follow_up_at"), "next_follow_up_at")
        if next_follow is None:
            next_follow = model.next_follow_up_at or (utc_now() + timedelta(days=3))
        previous_status = model.status
        target = previous_status
        if data.get("stage_to"):
            try:
                target = assert_status_transition(previous_status, str(data["stage_to"]))
            except ValueError as exc:
                raise AppError(str(exc), code="LEAD_STAGE_INVALID", status_code=400) from exc
        now = utc_now()
        if model.first_contact_at is None:
            model.first_contact_at = now
        model.last_activity_at = now
        model.next_follow_up_at = next_follow
        model.status = target
        model.recycle_due_at = now + timedelta(days=7)
        model.lock_version += 1
        self._add_activity(
            model,
            activity_type=activity_type,
            content=content,
            next_follow_up_at=next_follow,
            stage_from=previous_status,
            stage_to=target if target != previous_status else None,
            attributes=data.get("attributes"),
        )
        self.leads.save(model)
        if model.status in OPEN_STATUSES:
            self._open_follow_todo(model)
        self.audit.record(
            action="activity",
            resource_type="LEAD",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"type": activity_type, "stage": model.status},
        )
        self.session.commit()
        return self.get_lead(lead_id)

    def reopen_lead(
        self,
        lead_id: int,
        *,
        expected_version: int,
        reason: str,
        target_status: str = "CONTACTING",
    ) -> dict[str, Any]:
        if not self._is_manager():
            raise AppError("无线索重开权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(lead_id, for_update=True, manage=True)
        self._assert_expected_version(model, expected_version)
        if model.status != "LOST":
            raise AppError("仅输单线索可重开", code="LEAD_STATUS_INVALID", status_code=400)
        normalized_reason = str(reason or "").strip()
        if not normalized_reason:
            raise AppError("重开原因必填", code="VALIDATION_ERROR", status_code=400)
        target = normalize_status(target_status)
        if target not in OPEN_STATUSES:
            raise AppError("重开目标须为开放阶段", code="LEAD_STAGE_INVALID", status_code=400)
        previous = model.status
        model.status = target
        model.lost_reason = None
        model.next_follow_up_at = utc_now() + timedelta(days=3)
        model.recycle_due_at = utc_now() + timedelta(days=7)
        model.lock_version += 1
        self.leads.save(model)
        self._add_activity(
            model,
            activity_type="SYSTEM",
            content=normalized_reason,
            stage_from=previous,
            stage_to=target,
        )
        self._open_follow_todo(model)
        self.audit.record(
            action="reopen",
            resource_type="LEAD",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"target": target, "reason": normalized_reason[:80]},
        )
        self.session.commit()
        return self._to_dict(model)

    def assign_lead(
        self,
        lead_id: int,
        *,
        owner_user_id: int,
        expected_version: int,
        reason: Optional[str] = None,
    ) -> dict[str, Any]:
        if not self._is_manager():
            raise AppError("无线索分配权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(lead_id, for_update=True, manage=True)
        self._assert_expected_version(model, expected_version)
        if model.status not in OPEN_STATUSES:
            raise AppError("终态线索不可分配", code="LEAD_STATUS_INVALID", status_code=400)
        owner = self._assert_owner(owner_user_id)
        previous = model.owner_user_id
        model.owner_user_id = owner
        model.pool_status = "PRIVATE"
        model.assigned_at = utc_now()
        model.recycle_due_at = utc_now() + timedelta(days=7)
        model.lock_version += 1
        self._add_assignment_event(
            model,
            event_type="ASSIGN" if previous is None else "REASSIGN",
            from_owner=previous,
            to_owner=owner,
            reason=reason,
        )
        self.leads.save(model)
        self._open_follow_todo(model)
        self.audit.record(
            action="assign",
            resource_type="LEAD",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"from": previous, "to": owner},
        )
        self.session.commit()
        return self._to_dict(model)

    def claim_lead(self, lead_id: int, *, expected_version: int) -> dict[str, Any]:
        if not self.ctx.has_permission("lead:claim"):
            raise AppError("无线索领取权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(lead_id, for_update=True, manage=True)
        if model.pool_status != "PUBLIC" or model.owner_user_id is not None:
            raise AppError("线索已被领取", code="LEAD_ALREADY_CLAIMED", status_code=409)
        self._assert_expected_version(model, expected_version)
        owner = self._assert_owner(int(self.ctx.user_id or 0))
        model.owner_user_id = owner
        model.pool_status = "PRIVATE"
        model.assigned_at = utc_now()
        model.recycle_due_at = utc_now() + timedelta(days=7)
        model.lock_version += 1
        self._add_assignment_event(
            model,
            event_type="CLAIM",
            from_owner=None,
            to_owner=owner,
            reason="public pool claim",
        )
        self.leads.save(model)
        self._open_follow_todo(model)
        self.audit.record(
            action="claim",
            resource_type="LEAD",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"to": owner},
        )
        self.session.commit()
        return self._to_dict(model)

    def release_lead(
        self,
        lead_id: int,
        *,
        expected_version: int,
        reason: Optional[str] = None,
        event_type: str = "RELEASE",
    ) -> dict[str, Any]:
        if not self._is_manager():
            raise AppError("无线索释放权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(lead_id, for_update=True, manage=True)
        self._assert_expected_version(model, expected_version)
        if model.status not in OPEN_STATUSES:
            raise AppError("终态线索不可释放", code="LEAD_STATUS_INVALID", status_code=400)
        previous = model.owner_user_id
        if previous is None and model.pool_status == "PUBLIC":
            return self._to_dict(model)
        model.owner_user_id = None
        model.pool_status = "PUBLIC"
        model.assigned_at = None
        model.recycle_due_at = None
        model.lock_version += 1
        self._add_assignment_event(
            model,
            event_type=event_type,
            from_owner=previous,
            to_owner=None,
            reason=reason,
        )
        self.leads.save(model)
        self._close_follow_todo(lead_id, done=False)
        self.audit.record(
            action=event_type.lower(),
            resource_type="LEAD",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"from": previous},
        )
        self.session.commit()
        return self._to_dict(model)

    def recycle_lead(self, lead_id: int, *, expected_version: int) -> dict[str, Any]:
        if not self._is_manager():
            raise AppError("无线索回收权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(lead_id, for_update=True, manage=True)
        if model.pool_status == "PUBLIC":
            return self._to_dict(model)
        self._assert_expected_version(model, expected_version)
        if model.recycle_due_at is None or model.recycle_due_at > utc_now():
            raise AppError("线索尚未到回收时间", code="LEAD_RECYCLE_NOT_DUE", status_code=409)
        assignment = self.assignment_rules.execute_for_lead(model, trigger="RECYCLE")
        if assignment is not None:
            self.leads.save(model)
            self.session.commit()
            return self._to_dict(model)
        return self.release_lead(
            lead_id,
            expected_version=expected_version,
            reason="recycle due",
            event_type="RECYCLE",
        )

    def merge_leads(
        self,
        source_id: int,
        *,
        target_id: int,
        source_version: int,
        target_version: int,
        reason: str,
    ) -> dict[str, Any]:
        if not self._is_manager():
            raise AppError("无线索合并权限", code="PERMISSION_DENIED", status_code=403)
        if source_id == target_id:
            raise AppError("不可合并同一线索", code="VALIDATION_ERROR", status_code=400)
        rows = self.leads.get_pair_for_update(source_id, target_id)
        if len(rows) != 2:
            raise AppError("线索不存在", code="LEAD_NOT_FOUND", status_code=404)
        by_id = {int(row.id): row for row in rows}
        source = by_id[source_id]
        target = by_id[target_id]
        self._assert_expected_version(source, source_version)
        self._assert_expected_version(target, target_version)
        if int(source.park_id) != int(target.park_id):
            raise AppError("仅可合并同园区线索", code="LEAD_MERGE_SCOPE_INVALID", status_code=400)
        if source.status not in OPEN_STATUSES or target.status not in OPEN_STATUSES:
            raise AppError("已转化或终态线索不可合并", code="LEAD_MERGE_STATUS_INVALID", status_code=400)
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise AppError("合并原因必填", code="VALIDATION_ERROR", status_code=400)
        source.status = "MERGED"
        source.merged_into_lead_id = target.id
        source.lock_version += 1
        target.lock_version += 1
        self.leads.save(source)
        self.leads.save(target)
        self.merges.add(
            LeadMergeLinkMapper.new_model(
                LeadMergeLinkEntity(
                    tenant_id=self.ctx.tenant_id,
                    park_id=int(source.park_id),
                    source_lead_id=int(source.id),
                    target_lead_id=int(target.id),
                    actor_user_id=self.ctx.user_id,
                    reason=normalized_reason,
                    merged_at=utc_now(),
                )
            )
        )
        self._close_follow_todo(source_id, done=False)
        self.audit.record(
            action="merge",
            resource_type="LEAD",
            resource_id=source.id,
            park_id=source.park_id,
            detail={"target_id": target.id},
        )
        self.session.commit()
        return {"source": self._to_dict(source), "target": self.get_lead(target_id)}

    def _assert_can_lock(self, model) -> None:
        if not self.ctx.has_permission("lead:lock"):
            raise AppError("无房源锁定权限", code="PERMISSION_DENIED", status_code=403)
        self._assert_can_write(model)
        if model.status not in OPEN_STATUSES:
            raise AppError("仅开放线索可匹配和锁定房源", code="LEAD_STATUS_INVALID", status_code=400)

    def _expire_lock(self, lock, *, now: datetime, unit=None) -> bool:
        if unit is None:
            unit = self.units.get_current_for_update(int(lock.unit_id))
        current = self.unit_locks.get_by_id(int(lock.id), for_update=True)
        if current is None or current.status != "ACTIVE" or current.expires_at > now:
            return False
        current.status = "EXPIRED"
        current.released_at = now
        current.lock_version += 1
        self.session.add(current)
        if (
            unit is not None
            and unit.status == "RESERVED"
            and Decimal(str(unit.used_area or 0)) == 0
            and self.leases.units_lines.sum_active_occupied_for_unit(int(unit.id)) == 0
        ):
            unit.status = "VACANT"
            unit.lock_version += 1
            self.session.add(unit)
        return True

    def sweep_expired_unit_locks(self, *, park_id: Optional[int] = None) -> dict[str, Any]:
        if not self.ctx.has_permission("lead:lock"):
            raise AppError("无房源锁定权限", code="PERMISSION_DENIED", status_code=403)
        if park_id is not None:
            self._assert_park(int(park_id))
        now = utc_now()
        candidates = list(self.unit_locks.expired_active(now, park_id=park_id))
        expired_count = sum(1 for lock in candidates if self._expire_lock(lock, now=now))
        if expired_count:
            self.audit.record(
                action="expire",
                resource_type="LEAD_UNIT_LOCK",
                resource_id=0,
                park_id=park_id,
                detail={"count": expired_count},
            )
        if candidates:
            self.session.commit()
        return {"expired_count": expired_count, "as_of": now.isoformat()}

    def match_units(self, lead_id: int, *, limit: int = 50) -> dict[str, Any]:
        model = self._require(lead_id)
        self._assert_can_lock(model)
        self.sweep_expired_unit_locks(park_id=int(model.park_id))
        units = self.units.all_current_filtered(park_id=int(model.park_id), status="VACANT")
        desired_area = Decimal(str(model.intent_area)) if model.intent_area is not None else None
        budget = (
            Decimal(str(model.budget_unit_price))
            if model.budget_unit_price is not None
            else None
        )
        desired_usage = str(model.desired_usage or "").upper() or None
        matches: list[dict[str, Any]] = []
        for unit in units:
            if self.unit_locks.active_for_unit(int(unit.id)) is not None:
                continue
            unit_area = Decimal(str(unit.rentable_area or 0))
            unit_price = Decimal(str(unit.base_rent_price or 0))
            if desired_area is None:
                area_score = 0
                area_reason = "线索未填写意向面积"
                area_delta = Decimal("0")
            else:
                area_delta = abs(unit_area - desired_area)
                denominator = max(desired_area, Decimal("1"))
                area_score = max(0, 50 - int(min(area_delta / denominator, Decimal("1")) * 50))
                area_reason = f"可租面积 {unit_area}，与意向面积相差 {area_delta}"
            if desired_usage is None:
                usage_score = 0
                usage_reason = "线索未填写意向用途"
            elif str(unit.usage_type).upper() == desired_usage:
                usage_score = 25
                usage_reason = f"用途匹配 {desired_usage}"
            else:
                usage_score = 0
                usage_reason = f"用途 {unit.usage_type} 与意向 {desired_usage} 不同"
            if budget is None:
                price_score = 0
                price_reason = "线索未填写预算单价"
            elif unit_price <= budget:
                price_score = 25
                price_reason = f"基础租金 {unit_price} 不高于预算 {budget}"
            else:
                price_score = 0
                price_reason = f"基础租金 {unit_price} 高于预算 {budget}"
            matches.append(
                {
                    "unit_id": int(unit.id),
                    "park_id": int(unit.park_id),
                    "building_id": int(unit.building_id),
                    "code": unit.code,
                    "name": unit.name,
                    "usage_type": unit.usage_type,
                    "rentable_area": str(unit.rentable_area),
                    "base_rent_price": str(unit.base_rent_price),
                    "status": unit.status,
                    "score": area_score + usage_score + price_score,
                    "score_breakdown": {
                        "area": {"score": area_score, "max": 50, "reason": area_reason},
                        "usage": {"score": usage_score, "max": 25, "reason": usage_reason},
                        "price": {"score": price_score, "max": 25, "reason": price_reason},
                    },
                    "_area_delta": area_delta,
                }
            )
        matches.sort(
            key=lambda row: (
                -int(row["score"]),
                Decimal(str(row["_area_delta"])),
                int(row["unit_id"]),
            )
        )
        selected = matches[: min(max(int(limit), 1), 200)]
        for row in selected:
            row.pop("_area_delta", None)
        return {"lead_id": int(model.id), "total": len(matches), "items": selected}

    def acquire_unit_lock(
        self,
        lead_id: int,
        *,
        unit_id: int,
        expected_version: int,
        intent_id: int,
        duration_hours: int = 48,
    ) -> dict[str, Any]:
        model = self._require(lead_id, for_update=True)
        self._assert_can_lock(model)
        self._assert_expected_version(model, expected_version)
        hours = int(duration_hours)
        if hours < 1 or hours > 168:
            raise AppError("duration_hours 必须在 1 到 168 之间", code="VALIDATION_ERROR", status_code=400)
        unit = self.units.get_current_for_update(int(unit_id))
        if unit is None:
            raise AppError("单元不存在", code="UNIT_NOT_FOUND", status_code=404)
        if int(unit.park_id) != int(model.park_id):
            raise AppError("单元不属于线索园区", code="UNIT_PARK_MISMATCH", status_code=400)
        intent, intent_version = self.intents.assert_approved_for_unit(
            intent_id=int(intent_id), lead_id=int(model.id), unit_id=int(unit.id)
        )
        now = utc_now()
        active = self.unit_locks.active_for_unit(int(unit.id), for_update=True)
        if active is not None and active.expires_at <= now:
            self._expire_lock(active, now=now, unit=unit)
            self.session.flush()
            active = None
        if active is not None:
            if int(active.lead_id) == int(model.id):
                if (
                    int(active.intent_application_id or 0) != int(intent.id)
                    or int(active.intent_version_id or 0) != int(intent_version.id)
                ):
                    raise AppError(
                        "现有锁与批准意向不一致",
                        code="UNIT_LOCK_INTENT_MISMATCH",
                        status_code=409,
                    )
                result = self._lock_dict(active)
                self.session.commit()
                return result
            raise AppError("单元已被其他线索锁定", code="UNIT_ALREADY_LOCKED", status_code=409)
        if unit.status != "VACANT" or Decimal(str(unit.used_area or 0)) > 0:
            raise AppError("单元当前不可锁定", code="UNIT_NOT_AVAILABLE", status_code=409)
        lock = LeadUnitLockMapper.new_model(
            LeadUnitLockEntity(
                tenant_id=self.ctx.tenant_id,
                park_id=int(model.park_id),
                lead_id=int(model.id),
                unit_id=int(unit.id),
                expires_at=now + timedelta(hours=hours),
                created_by=self.ctx.user_id,
                intent_application_id=int(intent.id),
                intent_version_id=int(intent_version.id),
            )
        )
        try:
            self.unit_locks.add(lock)
            unit.status = "RESERVED"
            unit.lock_version += 1
            self.session.add(unit)
            model.lock_version += 1
            self.leads.save(model)
            self.audit.record(
                action="acquire",
                resource_type="LEAD_UNIT_LOCK",
                resource_id=lock.id,
                park_id=model.park_id,
                detail={
                    "lead_id": model.id,
                    "unit_id": unit.id,
                    "hours": hours,
                    "intent_application_id": int(intent.id),
                    "intent_version_id": int(intent_version.id),
                },
            )
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError("单元已被其他线索锁定", code="UNIT_ALREADY_LOCKED", status_code=409) from exc
        return {**self._lock_dict(lock), "lead_lock_version": model.lock_version}

    def release_unit_lock(
        self,
        lead_id: int,
        lock_id: int,
        *,
        expected_version: int,
    ) -> dict[str, Any]:
        model = self._require(lead_id, for_update=True)
        self._assert_can_lock(model)
        lock = self.unit_locks.get_by_id(lock_id)
        if lock is None or int(lock.lead_id) != int(model.id):
            raise AppError("房源锁不存在", code="UNIT_LOCK_NOT_FOUND", status_code=404)
        unit = self.units.get_current_for_update(int(lock.unit_id))
        lock = self.unit_locks.get_by_id(lock_id, for_update=True)
        if lock is None or int(lock.lead_id) != int(model.id):
            raise AppError("房源锁不存在", code="UNIT_LOCK_NOT_FOUND", status_code=404)
        if int(lock.lock_version) != int(expected_version):
            raise AppError("房源锁版本冲突", code="UNIT_LOCK_VERSION_CONFLICT", status_code=409)
        if lock.status != "ACTIVE":
            result = self._lock_dict(lock)
            self.session.commit()
            return result
        now = utc_now()
        lock.status = "EXPIRED" if lock.expires_at <= now else "RELEASED"
        lock.released_at = now
        lock.lock_version += 1
        if (
            unit is not None
            and unit.status == "RESERVED"
            and Decimal(str(unit.used_area or 0)) == 0
            and self.leases.units_lines.sum_active_occupied_for_unit(int(unit.id)) == 0
        ):
            unit.status = "VACANT"
            unit.lock_version += 1
            self.session.add(unit)
        self.session.add(lock)
        self.audit.record(
            action="release",
            resource_type="LEAD_UNIT_LOCK",
            resource_id=lock.id,
            park_id=lock.park_id,
            detail={"lead_id": model.id, "unit_id": lock.unit_id, "status": lock.status},
        )
        self.session.commit()
        return self._lock_dict(lock)

    def renew_unit_lock(
        self,
        lead_id: int,
        lock_id: int,
        *,
        expected_version: int,
        intent_id: int,
        duration_hours: int = 48,
    ) -> dict[str, Any]:
        model = self._require(lead_id, for_update=True)
        self._assert_can_lock(model)
        lock = self.unit_locks.get_by_id(lock_id)
        if lock is None or int(lock.lead_id) != int(model.id):
            raise AppError("房源锁不存在", code="UNIT_LOCK_NOT_FOUND", status_code=404)
        intent, intent_version = self.intents.assert_approved_for_unit(
            intent_id=int(intent_id), lead_id=int(model.id), unit_id=int(lock.unit_id)
        )
        if (
            int(lock.intent_application_id or 0) != int(intent.id)
            or int(lock.intent_version_id or 0) != int(intent_version.id)
        ):
            raise AppError(
                "房源锁与当前批准意向不一致",
                code="UNIT_LOCK_INTENT_MISMATCH",
                status_code=409,
            )
        unit = self.units.get_current_for_update(int(lock.unit_id))
        lock = self.unit_locks.get_by_id(lock_id, for_update=True)
        if lock is None or int(lock.lead_id) != int(model.id):
            raise AppError("房源锁不存在", code="UNIT_LOCK_NOT_FOUND", status_code=404)
        if int(lock.lock_version) != int(expected_version):
            raise AppError("房源锁版本冲突", code="UNIT_LOCK_VERSION_CONFLICT", status_code=409)
        hours = int(duration_hours)
        if hours < 1 or hours > 168:
            raise AppError("duration_hours 必须在 1 到 168 之间", code="VALIDATION_ERROR", status_code=400)
        now = utc_now()
        if lock.status != "ACTIVE" or lock.expires_at <= now:
            if lock.status == "ACTIVE":
                self._expire_lock(lock, now=now, unit=unit)
                self.session.commit()
            raise AppError("房源锁已失效", code="UNIT_LOCK_EXPIRED", status_code=409)
        lock.expires_at = now + timedelta(hours=hours)
        lock.lock_version += 1
        self.session.add(lock)
        self.audit.record(
            action="renew",
            resource_type="LEAD_UNIT_LOCK",
            resource_id=lock.id,
            park_id=lock.park_id,
            detail={"lead_id": model.id, "unit_id": lock.unit_id, "hours": hours},
        )
        self.session.commit()
        return self._lock_dict(lock)

    def _crm_filters(
        self,
        *,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        keyword: Optional[str] = None,
        owner_user_id: Optional[int] = None,
        pool_status: Optional[str] = None,
        source_type: Optional[str] = None,
        created_from: Any = None,
        created_to: Any = None,
    ) -> dict[str, Any]:
        if park_id is not None:
            self._assert_park(int(park_id))
        start = self._parse_datetime(created_from, "created_from")
        end = self._parse_datetime(created_to, "created_to")
        if start is not None and end is not None and start >= end:
            raise AppError("created_from 必须早于 created_to", code="VALIDATION_ERROR", status_code=400)
        return {
            "status": normalize_status(status) if status else None,
            "park_id": park_id,
            "keyword": keyword,
            "owner_user_id": owner_user_id,
            "pool_status": pool_status,
            "source_type": source_type,
            "created_from": start,
            "created_to": end,
        }

    def crm_summary(self, **raw_filters: Any) -> dict[str, Any]:
        if not self.ctx.has_permission("lead:read"):
            raise AppError("无线索查看权限", code="PERMISSION_DENIED", status_code=403)
        filters = self._crm_filters(**raw_filters)
        rows = list(self.leads.all_filtered(**filters))
        ordered_stages = [
            "NEW", "CONTACTING", "VISITING", "QUOTING", "NEGOTIATING",
            "WON", "LOST", "CANCELLED",
        ]
        stage_counts = {stage: 0 for stage in ordered_stages}
        source_counts: dict[str, int] = {}
        owner_counts: dict[Optional[int], int] = {}
        first_follow_seconds: list[float] = []
        now = utc_now()
        for row in rows:
            if row.status in stage_counts:
                stage_counts[row.status] += 1
            source = str(row.source_type or "UNKNOWN")
            source_counts[source] = source_counts.get(source, 0) + 1
            owner = int(row.owner_user_id) if row.owner_user_id is not None else None
            owner_counts[owner] = owner_counts.get(owner, 0) + 1
            if row.first_contact_at is not None and row.created_at is not None:
                first_follow_seconds.append(max(0.0, (row.first_contact_at - row.created_at).total_seconds()))
        total = len(rows)
        won = stage_counts["WON"]
        return {
            "as_of_utc": now.isoformat(),
            "counts": {
                "total": total,
                "new": stage_counts["NEW"],
                "open": sum(stage_counts[stage] for stage in OPEN_STATUSES),
                "won": won,
                "lost": stage_counts["LOST"],
                "public": sum(1 for row in rows if row.pool_status == "PUBLIC"),
                "overdue": sum(
                    1
                    for row in rows
                    if row.status in OPEN_STATUSES
                    and row.next_follow_up_at is not None
                    and row.next_follow_up_at < now
                ),
            },
            "stage_counts": stage_counts,
            "conversion_rate": round(won / total, 6) if total else 0.0,
            "average_first_follow_seconds": (
                round(sum(first_follow_seconds) / len(first_follow_seconds), 3)
                if first_follow_seconds
                else None
            ),
            "source_breakdown": [
                {"source_type": key, "count": source_counts[key]}
                for key in sorted(source_counts)
            ],
            "owner_breakdown": [
                {"owner_user_id": key, "count": owner_counts[key]}
                for key in sorted(owner_counts, key=lambda value: (-1 if value is None else value))
            ],
        }

    def crm_board(self, **raw_filters: Any) -> dict[str, Any]:
        if not self.ctx.has_permission("lead:read"):
            raise AppError("无线索查看权限", code="PERMISSION_DENIED", status_code=403)
        filters = self._crm_filters(**raw_filters)
        rows = list(self.leads.all_filtered(**filters))
        stages = ["NEW", "CONTACTING", "VISITING", "QUOTING", "NEGOTIATING", "WON", "LOST", "CANCELLED"]
        return {
            "total": len(rows),
            "columns": [
                {
                    "status": stage,
                    "count": sum(1 for row in rows if row.status == stage),
                    "items": [self._to_dict(row) for row in rows if row.status == stage],
                }
                for stage in stages
            ],
        }

    def convert_lead(self, lead_id: int, data: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """功能说明：线索转主体，可选创建合同草稿（不自动激活）。"""

        if not self.ctx.has_permission("lead:convert"):
            raise AppError("无线索转化权限", code="PERMISSION_DENIED", status_code=403)
        if not self.ctx.has_permission("party:write"):
            raise AppError("转化需主体写权限", code="PERMISSION_DENIED", status_code=403)

        data = data or {}
        model = self._require(lead_id, for_update=True)
        self._assert_can_write(model)
        if model.status == "WON" and model.party_id is not None:
            expected = data.get("expected_version")
            if expected is None:
                raise AppError("expected_version 必填", code="EXPECTED_VERSION_REQUIRED", status_code=400)
            if int(expected) not in {int(model.lock_version), int(model.lock_version) - 1}:
                raise AppError("线索版本冲突", code="LEAD_VERSION_CONFLICT", status_code=409)
            requested_unit_ids = {int(uid) for uid in (data.get("unit_ids") or [])}
            wants_lease = bool(
                requested_unit_ids or data.get("start_date") or data.get("end_date")
            )
            if wants_lease != (model.lease_id is not None):
                raise AppError("线索已按不同参数转化", code="LEAD_ALREADY_CONVERTED", status_code=409)
            existing_lease = (
                self.leases.get_contract(int(model.lease_id))
                if model.lease_id is not None
                else None
            )
            if existing_lease is not None:
                existing_unit_ids = {
                    int(row["unit_id"]) for row in existing_lease.get("units", [])
                }
                if existing_unit_ids != requested_unit_ids:
                    raise AppError(
                        "线索已按不同房源转化",
                        code="LEAD_ALREADY_CONVERTED",
                        status_code=409,
                    )
                for field in ("start_date", "end_date"):
                    if data.get(field) and str(existing_lease.get(field)) != str(data[field]):
                        raise AppError(
                            "线索已按不同租期转化",
                            code="LEAD_ALREADY_CONVERTED",
                            status_code=409,
                        )
            result = {
                "lead": self._to_dict(model),
                "party": self.parties.get_party(int(model.party_id)),
                "lease": existing_lease,
            }
            self.session.commit()
            return result
        self._assert_expected_version(model, data.get("expected_version"))
        if model.status not in CONVERTIBLE:
            raise AppError("仅跟进中线索可转化", code="LEAD_STATUS_INVALID", status_code=400)

        self._assert_park(int(model.park_id))

        lease_dict: Optional[dict[str, Any]] = None
        unit_ids = data.get("unit_ids") or []
        start_raw = data.get("start_date")
        end_raw = data.get("end_date")

        if unit_ids or start_raw or end_raw:
            if not self.ctx.has_permission("lease:write"):
                raise AppError("转化建合同需租赁写权限", code="PERMISSION_DENIED", status_code=403)
            if not start_raw or not end_raw:
                raise AppError(
                    "创建合同草稿须同时提供 start_date 与 end_date",
                    code="VALIDATION_ERROR",
                    status_code=400,
                )
        try:
            party = self.parties.create_party(
                {
                    "name": model.name,
                    "party_type": str(data.get("party_type") or "ORGANIZATION"),
                    "contact_name": model.contact_name or model.name,
                    "contact_phone": model.contact_phone,
                    "remark": f"from_lead:{model.id}",
                    "initial_park_relation": {
                        "park_id": int(model.park_id),
                        "role_code": "LESSEE",
                    },
                },
                commit=False,
            )
            model.party_id = int(party["id"])
            if data.get("_test_fail_after_party"):
                raise RuntimeError("injected conversion failure")

            if unit_ids or start_raw or end_raw:
                requested_unit_ids = {int(uid) for uid in unit_ids}
                units = [
                    {
                        "unit_id": int(uid),
                        "occupied_area": str(data.get("occupied_area") or "0"),
                        "unit_rent_price": str(data.get("unit_rent_price") or "0"),
                    }
                    for uid in unit_ids
                ]
                for uid in unit_ids:
                    unit = self.units.get_current_for_update(int(uid))
                    if unit is None:
                        raise AppError("单元不存在", code="UNIT_NOT_FOUND", status_code=404)
                    if int(unit.park_id) != int(model.park_id):
                        raise AppError("单元不属于线索园区", code="UNIT_PARK_MISMATCH", status_code=400)
                    active_lock = self.unit_locks.active_for_unit(int(uid), for_update=True)
                    if active_lock is not None and active_lock.expires_at <= utc_now():
                        self._expire_lock(active_lock, now=utc_now(), unit=unit)
                        active_lock = None
                    if active_lock is None or int(active_lock.lead_id) != int(model.id):
                        raise AppError(
                            "线索转化只能使用自身有效房源锁",
                            code="LEAD_UNIT_LOCK_REQUIRED",
                            status_code=409,
                        )
                    if not active_lock.intent_application_id:
                        raise AppError(
                            "房源锁缺少批准意向",
                            code="INTENT_LOCK_GATE_DENIED",
                            status_code=409,
                        )
                    self.intents.assert_approved_for_unit(
                        intent_id=int(active_lock.intent_application_id),
                        lead_id=int(model.id),
                        unit_id=int(uid),
                    )
                lease_dict = self.leases.create_contract(
                    {
                        "park_id": int(model.park_id),
                        "party_id": int(party["id"]),
                        "start_date": start_raw,
                        "end_date": end_raw,
                        "deposit_amount": data.get("deposit_amount") or "0",
                        "units": units,
                        "remark": f"from_lead:{model.id}",
                    },
                    commit=False,
                )
                model.lease_id = int(lease_dict["id"])
                for lock in self.unit_locks.active_for_lead(lead_id):
                    if int(lock.unit_id) in requested_unit_ids:
                        lock.lease_id = int(lease_dict["id"])
                        self.session.add(lock)
                if data.get("_test_fail_after_lease"):
                    raise RuntimeError("injected conversion failure after lease")

            previous_status = model.status
            model.status = "WON"
            model.converted_at = utc_now()
            model.lock_version += 1
            self.leads.save(model)
            self._add_activity(
                model,
                activity_type="SYSTEM",
                content="lead converted",
                stage_from=previous_status,
                stage_to="WON",
                attributes={"party_id": model.party_id, "lease_id": model.lease_id},
            )
            self._close_follow_todo(lead_id, done=True)
            self.events.emit_event(
                event_type="LEAD_CONVERTED",
                source_type="LEAD",
                source_id=str(model.id),
                idempotency_key=f"lead-converted:{model.id}",
                park_id=int(model.park_id),
                payload={
                    "title": f"线索已转化 {model.name[:80]}",
                    "description": "线索已形成客户主体",
                    "deep_link": "/leads",
                    "park_id": int(model.park_id),
                },
                commit=False,
                enforce_permission=False,
            )
            self.audit.record(
                action="convert",
                resource_type="LEAD",
                resource_id=model.id,
                park_id=model.park_id,
                detail={
                    "party_id": model.party_id,
                    "lease_id": model.lease_id,
                },
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

        log_business_success(
            logger,
            "线索转化成功",
            ctx=self.ctx,
            module="investment",
            action="convert_lead",
            resource_id=model.id,
            park_id=model.park_id,
        )
        return {
            "lead": self._to_dict(model),
            "party": party,
            "lease": lease_dict,
        }

"""First-class, tenant-safe lead viewing orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.modules.investment.domain.entities import LeadActivityEntity, ViewingWindow
from app.modules.investment.domain.rules import assert_viewing_transition, validate_viewing_window
from app.modules.investment.infrastructure.completion_repository import ViewingRepository
from app.modules.investment.infrastructure.crm_repository import LeadActivityRepository
from app.modules.investment.infrastructure.lead_repository import LeadRepository
from app.modules.investment.infrastructure.mappers import LeadActivityMapper
from app.modules.park_property.infrastructure.unit_repository import UnitRepository
from app.modules.workbench.application.work_item_service import WorkItemService
from app.shared.tenant_context import TenantContext


class ViewingService:
    """Schedule and complete viewings without treating free-text activities as master data."""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.viewings = ViewingRepository(session, ctx)
        self.leads = LeadRepository(session, ctx)
        self.units = UnitRepository(session, ctx)
        self.activities = LeadActivityRepository(session, ctx)
        self.work_items = WorkItemService(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def _require_permission(self, permission: str) -> None:
        if not self.ctx.has_permission(permission):
            raise AppError("无带看管理权限", code="PERMISSION_DENIED", status_code=403)

    @staticmethod
    def _parse_datetime(value: Any, field: str) -> datetime:
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

    def _lead(self, lead_id: int, *, for_update: bool = False):
        row = self.leads.get_by_id(lead_id, for_update=for_update)
        if row is None:
            raise AppError("线索不存在", code="LEAD_NOT_FOUND", status_code=404)
        return row

    def _assert_write(self, lead) -> None:
        self._require_permission("lead.viewing.write")
        if self.ctx.has_permission("lead:manage"):
            return
        if int(lead.owner_user_id or 0) != int(self.ctx.user_id or 0):
            raise AppError("只能维护本人负责的带看", code="PERMISSION_DENIED", status_code=403)

    def _validated_units(self, *, park_id: int, unit_ids: tuple[int, ...]):
        rows = self.units.get_currents_for_update(list(unit_ids))
        if len(rows) != len(unit_ids):
            raise AppError("带看单元不存在或已失效", code="VIEWING_UNIT_INVALID", status_code=409)
        by_id = {int(row.id): row for row in rows}
        if any(int(row.park_id) != int(park_id) for row in rows):
            raise AppError("带看单元与线索园区不一致", code="VIEWING_UNIT_PARK_INVALID", status_code=409)
        return [by_id[unit_id] for unit_id in unit_ids]

    def _to_dict(self, row) -> dict[str, Any]:
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "lead_id": int(row.lead_id),
            "owner_user_id": int(row.owner_user_id),
            "status": row.status,
            "starts_at": row.starts_at.isoformat(),
            "ends_at": row.ends_at.isoformat(),
            "visitor_name": row.visitor_name,
            "visitor_count": int(row.visitor_count),
            "notes": row.notes,
            "outcome": row.outcome,
            "next_follow_up_at": row.next_follow_up_at.isoformat() if row.next_follow_up_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "cancelled_at": row.cancelled_at.isoformat() if row.cancelled_at else None,
            "cancellation_reason": row.cancellation_reason,
            "lock_version": int(row.lock_version),
            "units": [
                {
                    "unit_id": int(item.unit_id),
                    "unit_version": int(item.unit_version),
                }
                for item in self.viewings.units(int(row.id))
            ],
        }

    def list_for_lead(self, lead_id: int) -> list[dict[str, Any]]:
        self._require_permission("lead.viewing.read")
        self._lead(lead_id)
        return [self._to_dict(row) for row in self.viewings.list_for_lead(lead_id)]

    def get(self, viewing_id: int) -> dict[str, Any]:
        self._require_permission("lead.viewing.read")
        row = self.viewings.get(viewing_id)
        if row is None:
            raise AppError("带看不存在", code="VIEWING_NOT_FOUND", status_code=404)
        self._lead(int(row.lead_id))
        return self._to_dict(row)

    def create(self, lead_id: int, data: dict[str, Any]) -> dict[str, Any]:
        lead = self._lead(lead_id, for_update=True)
        self._assert_write(lead)
        owner_user_id = int(data.get("owner_user_id") or lead.owner_user_id or 0)
        if owner_user_id <= 0 or self.viewings.lock_owner(owner_user_id) is None:
            raise AppError("带看负责人不存在或不可用", code="VIEWING_OWNER_INVALID", status_code=400)
        starts_at = self._parse_datetime(data.get("starts_at"), "starts_at")
        ends_at = self._parse_datetime(data.get("ends_at"), "ends_at")
        unit_ids = tuple(int(value) for value in (data.get("unit_ids") or []))
        try:
            window = validate_viewing_window(
                ViewingWindow(starts_at=starts_at, ends_at=ends_at, unit_ids=unit_ids)
            )
        except ValueError as exc:
            raise AppError(str(exc), code="VALIDATION_ERROR", status_code=400) from exc
        unit_rows = self._validated_units(park_id=int(lead.park_id), unit_ids=window.unit_ids)
        if self.viewings.overlapping(
            owner_user_id=owner_user_id,
            starts_at=window.starts_at,
            ends_at=window.ends_at,
        ) is not None:
            raise AppError("负责人该时段已有带看", code="VIEWING_TIME_CONFLICT", status_code=409)
        visitor_count = int(data.get("visitor_count", 1))
        if visitor_count < 1 or visitor_count > 100:
            raise AppError("visitor_count 无效", code="VALIDATION_ERROR", status_code=400)
        row = self.viewings.create(
            park_id=int(lead.park_id),
            lead_id=int(lead.id),
            owner_user_id=owner_user_id,
            status="SCHEDULED",
            starts_at=window.starts_at,
            ends_at=window.ends_at,
            visitor_name=(str(data.get("visitor_name") or "").strip()[:64] or None),
            visitor_count=visitor_count,
            notes=(str(data.get("notes") or "").strip()[:2000] or None),
            lock_version=1,
            created_by=self.ctx.user_id or None,
            updated_by=self.ctx.user_id or None,
        )
        for unit in unit_rows:
            self.viewings.add_unit(
                viewing_id=int(row.id),
                unit_id=int(unit.id),
                unit_version=int(unit.version_no),
            )
        self.work_items.ensure_from_source(
            source_type="LEAD_VIEWING",
            source_id=str(row.id),
            item_type="LEAD_VIEWING",
            title=f"执行带看：{str(lead.name)[:80]}",
            park_id=int(lead.park_id),
            priority="MEDIUM",
            assignee_user_id=owner_user_id,
            due_at=window.starts_at,
            deep_link="/leads",
            commit=False,
        )
        self.audit.record(
            action="schedule",
            resource_type="LEAD_VIEWING",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"lead_id": int(lead.id), "unit_ids": list(window.unit_ids)},
        )
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError("带看创建并发冲突", code="VIEWING_CONFLICT", status_code=409) from exc
        return self._to_dict(row)

    def reschedule(self, viewing_id: int, data: dict[str, Any]) -> dict[str, Any]:
        row = self.viewings.get(viewing_id, for_update=True)
        if row is None:
            raise AppError("带看不存在", code="VIEWING_NOT_FOUND", status_code=404)
        lead = self._lead(int(row.lead_id), for_update=True)
        self._assert_write(lead)
        if row.status not in {"SCHEDULED", "CONFIRMED"}:
            raise AppError("当前带看不可改期", code="VIEWING_STATUS_INVALID", status_code=409)
        if int(row.lock_version) != int(data.get("expected_version") or 0):
            raise AppError("带看版本冲突", code="VERSION_CONFLICT", status_code=409)
        owner_user_id = int(data.get("owner_user_id") or row.owner_user_id)
        if self.viewings.lock_owner(owner_user_id) is None:
            raise AppError("带看负责人不存在或不可用", code="VIEWING_OWNER_INVALID", status_code=400)
        starts_at = self._parse_datetime(data.get("starts_at", row.starts_at), "starts_at")
        ends_at = self._parse_datetime(data.get("ends_at", row.ends_at), "ends_at")
        old_units = tuple(int(item.unit_id) for item in self.viewings.units(int(row.id)))
        unit_ids = tuple(int(value) for value in data.get("unit_ids", old_units))
        try:
            window = validate_viewing_window(
                ViewingWindow(starts_at=starts_at, ends_at=ends_at, unit_ids=unit_ids)
            )
        except ValueError as exc:
            raise AppError(str(exc), code="VALIDATION_ERROR", status_code=400) from exc
        unit_rows = self._validated_units(park_id=int(row.park_id), unit_ids=window.unit_ids)
        if self.viewings.overlapping(
            owner_user_id=owner_user_id,
            starts_at=starts_at,
            ends_at=ends_at,
            exclude_id=int(row.id),
        ) is not None:
            raise AppError("负责人该时段已有带看", code="VIEWING_TIME_CONFLICT", status_code=409)
        row.owner_user_id = owner_user_id
        row.starts_at = starts_at
        row.ends_at = ends_at
        if "visitor_name" in data:
            row.visitor_name = str(data.get("visitor_name") or "").strip()[:64] or None
        if "visitor_count" in data:
            count = int(data["visitor_count"])
            if count < 1 or count > 100:
                raise AppError("visitor_count 无效", code="VALIDATION_ERROR", status_code=400)
            row.visitor_count = count
        if "notes" in data:
            row.notes = str(data.get("notes") or "").strip()[:2000] or None
        row.lock_version += 1
        row.updated_by = self.ctx.user_id or None
        self.viewings.save(row)
        self.viewings.delete_units(int(row.id))
        for unit in unit_rows:
            self.viewings.add_unit(
                viewing_id=int(row.id), unit_id=int(unit.id), unit_version=int(unit.version_no)
            )
        self.work_items.ensure_from_source(
            source_type="LEAD_VIEWING",
            source_id=str(row.id),
            item_type="LEAD_VIEWING",
            title=f"执行带看：{str(lead.name)[:80]}",
            park_id=int(row.park_id),
            priority="MEDIUM",
            assignee_user_id=owner_user_id,
            due_at=starts_at,
            deep_link="/leads",
            commit=False,
        )
        self.audit.record(
            action="reschedule",
            resource_type="LEAD_VIEWING",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"unit_ids": list(window.unit_ids)},
        )
        self.session.commit()
        return self._to_dict(row)

    def transition(self, viewing_id: int, data: dict[str, Any]) -> dict[str, Any]:
        idempotency_key = str(data.get("idempotency_key") or "").strip()
        target = str(data.get("status") or "").strip().upper()
        if target == "COMPLETED" and not idempotency_key:
            raise AppError("完成带看必须提供幂等键", code="IDEMPOTENCY_KEY_REQUIRED", status_code=400)
        if idempotency_key:
            prior = self.viewings.completion_by_key(idempotency_key)
            if prior is not None:
                if int(prior.id) != int(viewing_id) or target != "COMPLETED":
                    raise AppError("幂等键已用于其他命令", code="IDEMPOTENCY_CONFLICT", status_code=409)
                self._require_permission("lead.viewing.write")
                return self._to_dict(prior)
        row = self.viewings.get(viewing_id, for_update=True)
        if row is None:
            raise AppError("带看不存在", code="VIEWING_NOT_FOUND", status_code=404)
        lead = self._lead(int(row.lead_id), for_update=True)
        self._assert_write(lead)
        if int(row.lock_version) != int(data.get("expected_version") or 0):
            raise AppError("带看版本冲突", code="VERSION_CONFLICT", status_code=409)
        try:
            assert_viewing_transition(row.status, target)
        except ValueError as exc:
            raise AppError(str(exc), code="VIEWING_STATUS_INVALID", status_code=409) from exc
        now = utc_now()
        row.status = target
        row.lock_version += 1
        row.updated_by = self.ctx.user_id or None
        if target == "COMPLETED":
            outcome = str(data.get("outcome") or "").strip()
            if not outcome:
                raise AppError("outcome 必填", code="VALIDATION_ERROR", status_code=400)
            next_follow = data.get("next_follow_up_at")
            parsed_follow = (
                self._parse_datetime(next_follow, "next_follow_up_at") if next_follow else None
            )
            row.outcome = outcome[:1000]
            row.next_follow_up_at = parsed_follow
            row.completed_at = now
            row.completion_idempotency_key = idempotency_key
            previous_stage = lead.status
            if lead.status == "CONTACTING":
                lead.status = "VISITING"
            lead.last_activity_at = now
            lead.next_follow_up_at = parsed_follow
            lead.lock_version += 1
            self.leads.save(lead)
            self.activities.add(
                LeadActivityMapper.new_model(
                    LeadActivityEntity(
                        tenant_id=self.ctx.tenant_id,
                        park_id=int(row.park_id),
                        lead_id=int(row.lead_id),
                        actor_user_id=self.ctx.user_id or None,
                        activity_type="VISIT",
                        content=outcome[:1000],
                        occurred_at=now,
                        next_follow_up_at=parsed_follow,
                        stage_from=previous_stage,
                        stage_to=lead.status,
                        attributes_json={
                            "viewing_id": int(row.id),
                            "unit_ids": [int(item.unit_id) for item in self.viewings.units(int(row.id))],
                        },
                    )
                )
            )
            self.work_items.complete_by_source(
                source_type="LEAD_VIEWING",
                source_id=str(row.id),
                item_type="LEAD_VIEWING",
                commit=False,
            )
            if parsed_follow is not None:
                self.work_items.ensure_from_source(
                    source_type="LEAD",
                    source_id=str(lead.id),
                    item_type="LEAD_FOLLOW",
                    title=f"跟进招商线索 {str(lead.name)[:80]}",
                    park_id=int(lead.park_id),
                    priority="MEDIUM",
                    assignee_user_id=lead.owner_user_id,
                    due_at=parsed_follow,
                    deep_link="/leads",
                    commit=False,
                )
        elif target in {"CANCELLED", "NO_SHOW"}:
            reason = str(data.get("reason") or "").strip()
            if not reason:
                raise AppError("reason 必填", code="VALIDATION_ERROR", status_code=400)
            row.cancelled_at = now
            row.cancellation_reason = reason[:255]
            self.work_items.cancel_by_source(
                source_type="LEAD_VIEWING",
                source_id=str(row.id),
                item_type="LEAD_VIEWING",
                commit=False,
            )
        self.viewings.save(row)
        self.audit.record(
            action=target.lower(),
            resource_type="LEAD_VIEWING",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"lead_id": int(row.lead_id)},
        )
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            prior = self.viewings.completion_by_key(idempotency_key) if idempotency_key else None
            if prior is not None and int(prior.id) == int(viewing_id):
                return self._to_dict(prior)
            raise AppError("带看命令并发冲突", code="VIEWING_CONFLICT", status_code=409) from exc
        return self._to_dict(row)

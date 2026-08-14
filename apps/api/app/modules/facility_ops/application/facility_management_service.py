"""Facility device, weekly inspection and IoT alarm application service."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.modules.facility_ops.application.work_order_service import WorkOrderService
from app.modules.facility_ops.domain.facility_management import (
    ALARM_STATUSES,
    DEVICE_STATUSES,
    TASK_STATUSES,
    criticality,
    device_type,
    normalize_severity,
    severity_rank,
    transition_alarm,
    transition_device,
    transition_task,
    validate_device_properties,
    validate_result,
    validate_template_items,
    weekly_window,
)
from app.modules.facility_ops.domain.work_order import bounded_text
from app.modules.facility_ops.infrastructure.facility_management_repository import (
    FacilityManagementRepository,
)
from app.modules.workbench.application.work_item_service import WorkItemService
from app.shared.tenant_context import TenantContext

INSPECTION_ITEM_TYPE = "INSPECTION_TASK"
ALARM_ITEM_TYPE = "IOT_ALARM"


def _naive_utc(value: Any, *, field: str) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AppError(f"{field} 无效", code="VALIDATION_ERROR", status_code=400) from exc
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise AppError(f"{field} 无效", code="VALIDATION_ERROR", status_code=400)
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _expected(model, value: Any) -> None:  # type: ignore[no-untyped-def]
    if int(value) != int(model.lock_version):
        raise AppError("数据已被其他操作更新", code="VERSION_CONFLICT", status_code=409)


class FacilityManagementService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.repo = FacilityManagementRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)
        self.work_items = WorkItemService(session, ctx)
        self.work_orders = WorkOrderService(session, ctx)

    def _permission(self, *codes: str) -> None:
        if any(self.ctx.has_permission(code) for code in codes):
            return
        raise AppError("无操作权限", code="PERMISSION_DENIED", status_code=403)

    def _assert_park(self, park_id: Any) -> int:
        value = int(park_id)
        if not self.repo.park_exists(value):
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        if not self.ctx.allows_park(value):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        return value

    def _commit(self, *, code: str, message: str) -> None:
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(message, code=code, status_code=409) from exc

    @staticmethod
    def _device_snapshot(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "unit_id": int(row.unit_id) if row.unit_id is not None else None,
            "device_code": row.device_code,
            "name": row.name,
            "device_type": row.device_type,
            "location": row.location,
            "criticality": row.criticality,
            "status": row.status,
            "manufacturer": row.manufacturer,
            "model_no": row.model_no,
            "serial_no": row.serial_no,
            "commissioned_on": row.commissioned_on.isoformat() if row.commissioned_on else None,
            "warranty_expires_on": (
                row.warranty_expires_on.isoformat() if row.warranty_expires_on else None
            ),
            "properties": dict(row.properties_json or {}),
            "lock_version": int(row.lock_version),
        }

    def _device_dict(self, row, *, detail: bool = False) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        result = self._device_snapshot(row)
        result.update(
            {
                "retired_at": row.retired_at.isoformat() if row.retired_at else None,
                "retirement_reason": row.retirement_reason,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
        )
        if detail:
            result["history"] = [
                {
                    "version_no": int(item.version_no),
                    "action": item.action,
                    "reason": item.reason,
                    "changed_at": item.changed_at.isoformat(),
                    "before": item.before_json,
                    "after": item.after_json,
                }
                for item in self.repo.device_history(int(row.id))
            ]
        return result

    def _require_device(self, device_id: int, *, for_update: bool = False):
        row = self.repo.get_device(device_id, for_update=for_update)
        if row is None:
            raise AppError("设备不存在", code="FACILITY_DEVICE_NOT_FOUND", status_code=404)
        return row

    def list_devices(
        self,
        *,
        page: int,
        page_size: int,
        park_id: int | None = None,
        status: str | None = None,
        kind: str | None = None,
    ) -> dict[str, Any]:
        self._permission("facility_device:read")
        if park_id is not None:
            self._assert_park(park_id)
        normalized_status = str(status).upper() if status else None
        if normalized_status and normalized_status not in DEVICE_STATUSES:
            raise AppError("status 无效", code="VALIDATION_ERROR", status_code=400)
        normalized_type = device_type(kind) if kind else None
        offset = (page - 1) * page_size
        rows = self.repo.list_devices(
            offset=offset,
            limit=page_size,
            park_id=park_id,
            status=normalized_status,
            device_type=normalized_type,
        )
        return {
            "items": [self._device_dict(row) for row in rows],
            "total": self.repo.count_devices(
                park_id=park_id, status=normalized_status, device_type=normalized_type
            ),
            "page": page,
            "page_size": page_size,
        }

    def get_device(self, device_id: int) -> dict[str, Any]:
        self._permission("facility_device:read")
        return self._device_dict(self._require_device(device_id), detail=True)

    def create_device(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("facility_device:write")
        park_id = self._assert_park(data["park_id"])
        unit_id = int(data["unit_id"]) if data.get("unit_id") is not None else None
        if unit_id is not None and self.repo.unit_in_park(unit_id, park_id) is None:
            raise AppError("出租单元不存在", code="UNIT_NOT_FOUND", status_code=404)
        now = utc_now()
        row = self.repo.create_device(
            park_id=park_id,
            unit_id=unit_id,
            device_code=bounded_text(
                data.get("device_code"), field="device_code", maximum=64, required=True
            ).upper(),
            name=bounded_text(data.get("name"), field="name", maximum=128, required=True),
            device_type=device_type(data.get("device_type")),
            location=bounded_text(
                data.get("location"), field="location", maximum=255, required=True
            ),
            criticality=criticality(data.get("criticality") or "MEDIUM"),
            status="ACTIVE",
            manufacturer=bounded_text(
                data.get("manufacturer"), field="manufacturer", maximum=128
            )
            or None,
            model_no=bounded_text(data.get("model_no"), field="model_no", maximum=128)
            or None,
            serial_no=bounded_text(data.get("serial_no"), field="serial_no", maximum=128)
            or None,
            commissioned_on=(
                _naive_utc(data["commissioned_on"], field="commissioned_on")
                if data.get("commissioned_on")
                else None
            ),
            warranty_expires_on=(
                _naive_utc(data["warranty_expires_on"], field="warranty_expires_on")
                if data.get("warranty_expires_on")
                else None
            ),
            properties_json=validate_device_properties(data.get("properties")),
            lock_version=1,
        )
        snapshot = self._device_snapshot(row)
        self.repo.create_device_history(
            park_id=park_id,
            device_id=int(row.id),
            version_no=1,
            action="CREATED",
            before_json=None,
            after_json=snapshot,
            reason="创建设备",
            changed_by=self.ctx.user_id or None,
            changed_at=now,
        )
        self.audit.record(
            action="create",
            resource_type="FACILITY_DEVICE",
            resource_id=int(row.id),
            park_id=park_id,
            detail={"device_code": row.device_code, "device_type": row.device_type},
        )
        self._commit(code="FACILITY_DEVICE_CONFLICT", message="设备编码或关联关系冲突")
        return self._device_dict(row, detail=True)

    def update_device(self, device_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("facility_device:write")
        row = self._require_device(device_id, for_update=True)
        _expected(row, data["expected_version"])
        if row.status == "RETIRED":
            raise AppError("退役设备不可修改", code="DEVICE_STATE_INVALID", status_code=409)
        before = self._device_snapshot(row)
        if data.get("unit_id") is not None:
            unit_id = int(data["unit_id"])
            if self.repo.unit_in_park(unit_id, int(row.park_id)) is None:
                raise AppError("出租单元不存在", code="UNIT_NOT_FOUND", status_code=404)
            row.unit_id = unit_id
        if "unit_id" in data and data.get("unit_id") is None:
            row.unit_id = None
        for field, maximum in (
            ("name", 128),
            ("location", 255),
            ("manufacturer", 128),
            ("model_no", 128),
            ("serial_no", 128),
        ):
            if field in data:
                value = bounded_text(
                    data.get(field),
                    field=field,
                    maximum=maximum,
                    required=field in {"name", "location"},
                )
                setattr(row, field, value or None)
        if data.get("criticality") is not None:
            row.criticality = criticality(data["criticality"])
        if data.get("status") is not None and str(data["status"]).upper() != row.status:
            row.status = transition_device(row.status, str(data["status"]).upper())
        if "properties" in data:
            row.properties_json = validate_device_properties(data.get("properties"))
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        after = self._device_snapshot(row)
        reason = bounded_text(data.get("reason"), field="reason", maximum=1000, required=True)
        self.repo.create_device_history(
            park_id=int(row.park_id),
            device_id=int(row.id),
            version_no=int(row.lock_version),
            action="UPDATED",
            before_json=before,
            after_json=after,
            reason=reason,
            changed_by=self.ctx.user_id or None,
            changed_at=utc_now(),
        )
        self.audit.record(
            action="update",
            resource_type="FACILITY_DEVICE",
            resource_id=int(row.id),
            park_id=int(row.park_id),
            detail={"reason": reason, "version": int(row.lock_version)},
        )
        self._commit(code="FACILITY_DEVICE_CONFLICT", message="设备更新冲突")
        return self._device_dict(row, detail=True)

    def retire_device(self, device_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("facility_device:retire")
        row = self._require_device(device_id, for_update=True)
        _expected(row, data["expected_version"])
        blockers = self.repo.device_retirement_blockers(device_id)
        if any(blockers.values()):
            raise AppError(
                "设备仍有关联的生效巡检、任务、告警或 IoT 绑定",
                code="FACILITY_DEVICE_RETIREMENT_BLOCKED",
                status_code=409,
                data=blockers,
            )
        before = self._device_snapshot(row)
        row.status = transition_device(row.status, "RETIRED")
        row.retired_at = utc_now()
        row.retired_by = self.ctx.user_id or None
        row.retirement_reason = bounded_text(
            data.get("reason"), field="reason", maximum=1000, required=True
        )
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        self.repo.create_device_history(
            park_id=int(row.park_id),
            device_id=int(row.id),
            version_no=int(row.lock_version),
            action="RETIRED",
            before_json=before,
            after_json=self._device_snapshot(row),
            reason=row.retirement_reason,
            changed_by=self.ctx.user_id or None,
            changed_at=row.retired_at,
        )
        self.audit.record(
            action="retire",
            resource_type="FACILITY_DEVICE",
            resource_id=int(row.id),
            park_id=int(row.park_id),
            detail={"reason": row.retirement_reason},
        )
        self._commit(code="FACILITY_DEVICE_CONFLICT", message="设备退役冲突")
        return self._device_dict(row, detail=True)

    @staticmethod
    def _template_item_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "item_code": row.item_code,
            "label": row.label,
            "position": int(row.position),
            "result_type": row.result_type,
            "required": bool(row.required),
            "critical": bool(row.critical),
            "minimum": str(row.minimum) if row.minimum is not None else None,
            "maximum": str(row.maximum) if row.maximum is not None else None,
            "options": list(row.options_json or []),
        }

    def _version_dict(self, row, *, include_items: bool = True) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        result = {
            "id": int(row.id),
            "template_id": int(row.template_id),
            "version_no": int(row.version_no),
            "status": row.status,
            "description": row.description,
            "lock_version": int(row.lock_version),
            "published_at": row.published_at.isoformat() if row.published_at else None,
        }
        if include_items:
            result["items"] = [
                self._template_item_dict(item)
                for item in self.repo.template_items(int(row.id))
            ]
        return result

    def _template_dict(self, row, *, detail: bool = False) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        result = {
            "id": int(row.id),
            "code": row.code,
            "name": row.name,
            "device_type": row.device_type,
            "status": row.status,
            "current_version": int(row.current_version),
        }
        if detail:
            result["versions"] = [
                self._version_dict(version)
                for version in self.repo.versions_for_template(int(row.id))
            ]
        return result

    def list_templates(self) -> list[dict[str, Any]]:
        self._permission("inspection:read")
        return [self._template_dict(row, detail=True) for row in self.repo.list_templates()]

    def create_template(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("inspection:template_manage")
        items = validate_template_items(data.get("items") or [])
        template = self.repo.create_template(
            code=bounded_text(data.get("code"), field="code", maximum=64, required=True).upper(),
            name=bounded_text(data.get("name"), field="name", maximum=128, required=True),
            device_type=device_type(data["device_type"]) if data.get("device_type") else None,
            status="ACTIVE",
            current_version=0,
            created_by=self.ctx.user_id or None,
        )
        version = self.repo.create_template_version(
            template_id=int(template.id),
            version_no=1,
            status="DRAFT",
            description=bounded_text(
                data.get("description"), field="description", maximum=1000
            )
            or None,
            lock_version=1,
            created_by=self.ctx.user_id or None,
        )
        for item in items:
            self.repo.create_template_item(
                template_version_id=int(version.id),
                item_code=item["item_code"],
                label=item["label"],
                position=item["position"],
                result_type=item["result_type"],
                required=item["required"],
                critical=item["critical"],
                minimum=item["minimum"],
                maximum=item["maximum"],
                options_json=item["options"],
            )
        self.audit.record(
            action="create",
            resource_type="INSPECTION_TEMPLATE",
            resource_id=int(template.id),
            detail={"code": template.code, "version": 1},
        )
        self._commit(code="INSPECTION_TEMPLATE_CONFLICT", message="巡检模板编码冲突")
        return self._template_dict(template, detail=True)

    def add_template_version(self, template_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("inspection:template_manage")
        template = self.repo.get_template(template_id, for_update=True)
        if template is None:
            raise AppError("巡检模板不存在", code="INSPECTION_TEMPLATE_NOT_FOUND", status_code=404)
        if template.status != "ACTIVE":
            raise AppError("已退役模板不可新增版本", code="INSPECTION_TEMPLATE_RETIRED", status_code=409)
        items = validate_template_items(data.get("items") or [])
        versions = self.repo.versions_for_template(template_id)
        version_no = max((int(row.version_no) for row in versions), default=0) + 1
        version = self.repo.create_template_version(
            template_id=int(template.id),
            version_no=version_no,
            status="DRAFT",
            description=bounded_text(
                data.get("description"), field="description", maximum=1000
            )
            or None,
            lock_version=1,
            created_by=self.ctx.user_id or None,
        )
        for item in items:
            self.repo.create_template_item(
                template_version_id=int(version.id),
                item_code=item["item_code"],
                label=item["label"],
                position=item["position"],
                result_type=item["result_type"],
                required=item["required"],
                critical=item["critical"],
                minimum=item["minimum"],
                maximum=item["maximum"],
                options_json=item["options"],
            )
        self.audit.record(
            action="create_version",
            resource_type="INSPECTION_TEMPLATE",
            resource_id=int(template.id),
            detail={"version": version_no},
        )
        self._commit(code="INSPECTION_TEMPLATE_CONFLICT", message="巡检模板版本冲突")
        return self._version_dict(version)

    def publish_template_version(
        self, version_id: int, *, expected_version: int
    ) -> dict[str, Any]:
        self._permission("inspection:template_manage")
        version = self.repo.get_template_version(version_id, for_update=True)
        if version is None:
            raise AppError("巡检模板版本不存在", code="INSPECTION_VERSION_NOT_FOUND", status_code=404)
        _expected(version, expected_version)
        if version.status != "DRAFT":
            raise AppError("仅草稿版本可发布", code="INSPECTION_VERSION_STATE_INVALID", status_code=409)
        template = self.repo.get_template(int(version.template_id), for_update=True)
        if template is None or template.status != "ACTIVE":
            raise AppError("巡检模板不可发布", code="INSPECTION_TEMPLATE_RETIRED", status_code=409)
        for current in self.repo.versions_for_template(int(template.id)):
            if current.status == "PUBLISHED":
                current.status = "RETIRED"
                current.retired_by = self.ctx.user_id or None
                current.retired_at = utc_now()
                current.lock_version = int(current.lock_version) + 1
                self.repo.save(current)
        version.status = "PUBLISHED"
        version.published_by = self.ctx.user_id or None
        version.published_at = utc_now()
        version.lock_version = int(version.lock_version) + 1
        template.current_version = int(version.version_no)
        self.repo.save(version)
        self.repo.save(template)
        self.audit.record(
            action="publish",
            resource_type="INSPECTION_TEMPLATE_VERSION",
            resource_id=int(version.id),
            detail={"template_id": int(template.id), "version": int(version.version_no)},
        )
        self._commit(code="INSPECTION_TEMPLATE_CONFLICT", message="巡检模板发布冲突")
        return self._version_dict(version)

    @staticmethod
    def _schedule_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "code": row.code,
            "name": row.name,
            "device_id": int(row.device_id),
            "template_version_id": int(row.template_version_id),
            "assignee_user_id": int(row.assignee_user_id),
            "timezone": row.timezone,
            "weekday": int(row.weekday),
            "local_due_time": row.local_due_time,
            "completion_window_minutes": int(row.completion_window_minutes),
            "missed_work_order": bool(row.missed_work_order),
            "status": row.status,
            "lock_version": int(row.lock_version),
        }

    def list_schedules(self, *, park_id: int | None = None) -> list[dict[str, Any]]:
        self._permission("inspection:read")
        if park_id is not None:
            self._assert_park(park_id)
        return [self._schedule_dict(row) for row in self.repo.list_schedules(park_id=park_id)]

    def create_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("inspection:schedule_manage")
        park_id = self._assert_park(data["park_id"])
        device = self._require_device(int(data["device_id"]))
        if int(device.park_id) != park_id or device.status == "RETIRED":
            raise AppError("设备不属于该园区或已退役", code="FACILITY_DEVICE_INVALID", status_code=409)
        version = self.repo.get_template_version(int(data["template_version_id"]))
        if version is None or version.status != "PUBLISHED":
            raise AppError("须使用已发布巡检模板版本", code="INSPECTION_VERSION_INVALID", status_code=409)
        template = self.repo.get_template(int(version.template_id))
        if template is None or (
            template.device_type is not None and template.device_type != device.device_type
        ):
            raise AppError("巡检模板与设备类型不匹配", code="INSPECTION_TEMPLATE_MISMATCH", status_code=409)
        assignee = int(data["assignee_user_id"])
        if not self.repo.active_user_allows_park(assignee, park_id):
            raise AppError("巡检执行人无该园区权限", code="ASSIGNEE_SCOPE_DENIED", status_code=409)
        weekday = int(data["weekday"])
        window_minutes = int(data.get("completion_window_minutes") or 1440)
        weekly_window(
            reference=utc_now(),
            weekday=weekday,
            local_due_time=str(data["local_due_time"]),
            timezone_name=str(data.get("timezone") or "Asia/Shanghai"),
            completion_window_minutes=window_minutes,
        )
        row = self.repo.create_schedule(
            park_id=park_id,
            code=bounded_text(data.get("code"), field="code", maximum=64, required=True).upper(),
            name=bounded_text(data.get("name"), field="name", maximum=128, required=True),
            device_id=int(device.id),
            template_version_id=int(version.id),
            assignee_user_id=assignee,
            timezone=str(data.get("timezone") or "Asia/Shanghai"),
            weekday=weekday,
            local_due_time=str(data["local_due_time"]),
            completion_window_minutes=window_minutes,
            missed_work_order=bool(data.get("missed_work_order", False)),
            status="ACTIVE",
            lock_version=1,
            created_by=self.ctx.user_id or None,
        )
        self.audit.record(
            action="create",
            resource_type="INSPECTION_SCHEDULE",
            resource_id=int(row.id),
            park_id=park_id,
            detail={"code": row.code, "device_id": int(device.id)},
        )
        self._commit(code="INSPECTION_SCHEDULE_CONFLICT", message="巡检计划编码冲突")
        return self._schedule_dict(row)

    def retire_schedule(self, schedule_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("inspection:schedule_manage")
        row = self.repo.get_schedule(schedule_id, for_update=True)
        if row is None:
            raise AppError("巡检计划不存在", code="INSPECTION_SCHEDULE_NOT_FOUND", status_code=404)
        _expected(row, data["expected_version"])
        if row.status == "RETIRED":
            return self._schedule_dict(row)
        row.status = "RETIRED"
        row.retired_at = utc_now()
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        self.audit.record(
            action="retire",
            resource_type="INSPECTION_SCHEDULE",
            resource_id=int(row.id),
            park_id=int(row.park_id),
            detail={"reason": bounded_text(data.get("reason"), field="reason", maximum=1000)},
        )
        self.session.commit()
        return self._schedule_dict(row)

    def transition_schedule(
        self, schedule_id: int, target: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        self._permission("inspection:schedule_manage")
        row = self.repo.get_schedule(schedule_id, for_update=True)
        if row is None:
            raise AppError("巡检计划不存在", code="INSPECTION_SCHEDULE_NOT_FOUND", status_code=404)
        _expected(row, data["expected_version"])
        normalized_target = str(target).upper()
        allowed = {"ACTIVE": {"PAUSED"}, "PAUSED": {"ACTIVE"}, "RETIRED": set()}
        if normalized_target not in allowed.get(row.status, set()):
            raise AppError("巡检计划状态转换无效", code="INSPECTION_SCHEDULE_STATE_INVALID", status_code=409)
        before = row.status
        reason = bounded_text(data.get("reason"), field="reason", maximum=1000, required=True)
        row.status = normalized_target
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        self.audit.record(
            action=normalized_target.lower(),
            resource_type="INSPECTION_SCHEDULE",
            resource_id=int(row.id),
            park_id=int(row.park_id),
            detail={"from": before, "to": normalized_target, "reason": reason},
        )
        self._commit(code="INSPECTION_SCHEDULE_CONFLICT", message="巡检计划状态冲突")
        return self._schedule_dict(row)

    def _task_snapshot(self, version_id: int) -> dict[str, Any]:
        version = self.repo.get_template_version(version_id)
        if version is None:
            raise AppError("巡检模板版本不存在", code="INSPECTION_VERSION_NOT_FOUND", status_code=404)
        return {
            "version_id": int(version.id),
            "template_id": int(version.template_id),
            "version_no": int(version.version_no),
            "items": [
                self._template_item_dict(item) for item in self.repo.template_items(int(version.id))
            ],
        }

    def _task_event(
        self,
        row,
        *,
        event_type: str,
        from_status: str | None,
        to_status: str | None,
        key: str,
        reason: str | None = None,
        detail: dict[str, Any] | None = None,
        at: datetime | None = None,
    ):  # type: ignore[no-untyped-def]
        return self.repo.create_task_event(
            park_id=int(row.park_id),
            task_id=int(row.id),
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            actor_user_id=self.ctx.user_id or None,
            reason=reason,
            detail_json=detail or {},
            idempotency_key=key,
            occurred_at=at or utc_now(),
        )

    def generate_tasks(self, *, as_of: datetime | None = None) -> dict[str, Any]:
        self._permission("inspection:sweep")
        reference = _naive_utc(as_of, field="as_of") if as_of else utc_now()
        created: list[int] = []
        existing: list[int] = []
        for schedule in self.repo.active_schedules():
            start, due = weekly_window(
                reference=reference,
                weekday=int(schedule.weekday),
                local_due_time=schedule.local_due_time,
                timezone_name=schedule.timezone,
                completion_window_minutes=int(schedule.completion_window_minutes),
            )
            current = self.repo.task_for_window(int(schedule.id), start)
            if current is not None:
                existing.append(int(current.id))
                continue
            try:
                with self.session.begin_nested():
                    task = self.repo.create_task(
                        park_id=int(schedule.park_id),
                        schedule_id=int(schedule.id),
                        device_id=int(schedule.device_id),
                        template_version_id=int(schedule.template_version_id),
                        template_snapshot_json=self._task_snapshot(
                            int(schedule.template_version_id)
                        ),
                        assignee_user_id=int(schedule.assignee_user_id),
                        window_start=start,
                        window_due_at=due,
                        status="PENDING",
                        lock_version=1,
                    )
                    self._task_event(
                        task,
                        event_type="GENERATED",
                        from_status=None,
                        to_status="PENDING",
                        key=f"inspection-generated:{schedule.id}:{start.isoformat()}",
                        at=reference,
                    )
                    self.work_items.ensure_from_source(
                        source_type="INSPECTION_TASK",
                        source_id=str(task.id),
                        item_type=INSPECTION_ITEM_TYPE,
                        title=f"执行周巡检 {schedule.name}",
                        description=f"设备 {schedule.device_id} 的巡检任务",
                        park_id=int(schedule.park_id),
                        priority="HIGH",
                        assignee_user_id=int(schedule.assignee_user_id),
                        due_at=due.isoformat(),
                        deep_link="/facility-operations",
                        commit=False,
                    )
                    created.append(int(task.id))
            except IntegrityError:
                current = self.repo.task_for_window(int(schedule.id), start)
                if current is not None:
                    existing.append(int(current.id))
        self.audit.record(
            action="generate",
            resource_type="INSPECTION_TASK",
            resource_id=None,
            detail={"as_of": reference.isoformat(), "created": len(created)},
        )
        self.session.commit()
        return {"created_ids": created, "existing_ids": existing, "as_of": reference.isoformat()}

    def _task_dict(self, row, *, detail: bool = False) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        result = {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "schedule_id": int(row.schedule_id),
            "device_id": int(row.device_id),
            "template_version_id": int(row.template_version_id),
            "assignee_user_id": int(row.assignee_user_id),
            "window_start": row.window_start.isoformat(),
            "window_due_at": row.window_due_at.isoformat(),
            "status": row.status,
            "lock_version": int(row.lock_version),
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        }
        if detail:
            result["template_snapshot"] = row.template_snapshot_json
            result["results"] = [
                {
                    "item_code": item.item_code,
                    "label": item.label,
                    "position": int(item.position),
                    "result_type": item.result_type,
                    "text_value": item.text_value,
                    "number_value": str(item.number_value)
                    if item.number_value is not None
                    else None,
                    "passed": bool(item.passed),
                    "critical": bool(item.critical),
                    "evidence_refs": list(item.evidence_refs_json or []),
                    "remark": item.remark,
                }
                for item in self.repo.task_results(int(row.id))
            ]
            result["exceptions"] = [
                {
                    "id": int(item.id),
                    "item_code": item.item_code,
                    "severity": item.severity,
                    "summary": item.summary,
                    "status": item.status,
                    "work_order_id": item.work_order_id,
                }
                for item in self.repo.task_exceptions(int(row.id))
            ]
            result["events"] = [
                {
                    "id": int(item.id),
                    "event_type": item.event_type,
                    "from_status": item.from_status,
                    "to_status": item.to_status,
                    "reason": item.reason,
                    "detail": item.detail_json or {},
                    "occurred_at": item.occurred_at.isoformat(),
                }
                for item in self.repo.task_events(int(row.id))
            ]
        return result

    def _require_task(self, task_id: int, *, for_update: bool = False):
        row = self.repo.get_task(task_id, for_update=for_update)
        if row is None:
            raise AppError("巡检任务不存在", code="INSPECTION_TASK_NOT_FOUND", status_code=404)
        return row

    def list_tasks(
        self,
        *,
        page: int,
        page_size: int,
        park_id: int | None = None,
        status: str | None = None,
        assignee_user_id: int | None = None,
    ) -> dict[str, Any]:
        self._permission("inspection:read", "inspection:execute")
        if park_id is not None:
            self._assert_park(park_id)
        normalized = str(status).upper() if status else None
        if normalized and normalized not in TASK_STATUSES:
            raise AppError("status 无效", code="VALIDATION_ERROR", status_code=400)
        if self.ctx.has_permission("inspection:execute") and not self.ctx.has_permission(
            "inspection:read"
        ):
            assignee_user_id = int(self.ctx.user_id)
        rows = self.repo.list_tasks(
            offset=(page - 1) * page_size,
            limit=page_size,
            park_id=park_id,
            status=normalized,
            assignee_user_id=assignee_user_id,
        )
        return {
            "items": [self._task_dict(row) for row in rows],
            "total": self.repo.count_tasks(
                park_id=park_id, status=normalized, assignee_user_id=assignee_user_id
            ),
            "page": page,
            "page_size": page_size,
        }

    def get_task(self, task_id: int) -> dict[str, Any]:
        self._permission("inspection:read", "inspection:execute")
        row = self._require_task(task_id)
        if not self.ctx.has_permission("inspection:read") and int(row.assignee_user_id) != int(
            self.ctx.user_id
        ):
            raise AppError("巡检任务不存在", code="INSPECTION_TASK_NOT_FOUND", status_code=404)
        return self._task_dict(row, detail=True)

    def start_task(self, task_id: int, *, expected_version: int, key: str) -> dict[str, Any]:
        self._permission("inspection:execute")
        existing = self.repo.task_event_by_key(key)
        if existing is not None:
            if int(existing.task_id) != int(task_id) or existing.event_type != "STARTED":
                raise AppError("Idempotency-Key 已用于不同请求", code="IDEMPOTENCY_KEY_REUSED", status_code=409)
            return self._task_dict(self._require_task(task_id), detail=True)
        row = self._require_task(task_id, for_update=True)
        if int(row.assignee_user_id) != int(self.ctx.user_id) and not self.ctx.has_permission(
            "inspection:dispatch"
        ):
            raise AppError("仅执行人可开始巡检", code="ASSIGNEE_REQUIRED", status_code=403)
        _expected(row, expected_version)
        before = row.status
        row.status = transition_task(row.status, "IN_PROGRESS")
        row.started_at = utc_now()
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        event = self._task_event(
            row,
            event_type="STARTED",
            from_status=before,
            to_status=row.status,
            key=key,
        )
        self.audit.record(
            action="start",
            resource_type="INSPECTION_TASK",
            resource_id=int(row.id),
            park_id=int(row.park_id),
            detail={"event_id": int(event.id)},
        )
        self._commit(code="INSPECTION_TASK_CONFLICT", message="巡检任务开始冲突")
        return self._task_dict(row, detail=True)

    def reassign_task(self, task_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("inspection:dispatch")
        row = self._require_task(task_id, for_update=True)
        _expected(row, data["expected_version"])
        if row.status not in {"PENDING", "IN_PROGRESS"}:
            raise AppError("终态巡检任务不可改派", code="INSPECTION_STATE_INVALID", status_code=409)
        assignee = int(data["assignee_user_id"])
        if not self.repo.active_user_allows_park(assignee, int(row.park_id)):
            raise AppError("执行人无该园区权限", code="ASSIGNEE_SCOPE_DENIED", status_code=409)
        previous = int(row.assignee_user_id)
        row.assignee_user_id = assignee
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        self._task_event(
            row,
            event_type="REASSIGNED",
            from_status=row.status,
            to_status=row.status,
            key=f"inspection-reassigned:{row.id}:{row.lock_version}",
            reason=bounded_text(data.get("reason"), field="reason", maximum=1000, required=True),
            detail={"from_user_id": previous, "to_user_id": assignee},
        )
        self.work_items.ensure_from_source(
            source_type="INSPECTION_TASK",
            source_id=str(row.id),
            item_type=INSPECTION_ITEM_TYPE,
            title=f"执行巡检任务 #{row.id}",
            park_id=int(row.park_id),
            priority="HIGH",
            assignee_user_id=assignee,
            due_at=row.window_due_at.isoformat(),
            deep_link="/facility-operations",
            commit=False,
        )
        self.audit.record(
            action="reassign",
            resource_type="INSPECTION_TASK",
            resource_id=int(row.id),
            park_id=int(row.park_id),
            detail={"from": previous, "to": assignee},
        )
        self.session.commit()
        return self._task_dict(row, detail=True)

    def _promote_exception(self, exception, *, reason: str) -> int:  # type: ignore[no-untyped-def]
        if exception.work_order_id is not None:
            return int(exception.work_order_id)
        task = self._require_task(int(exception.task_id))
        device = self._require_device(int(task.device_id))
        priority = "URGENT" if exception.severity == "CRITICAL" else "HIGH"
        order = self.work_orders.create_system_order(
            {
                "park_id": int(exception.park_id),
                "unit_id": device.unit_id,
                "title": f"巡检异常：{device.name}",
                "description": exception.summary,
                "category": "INSPECTION",
                "priority": priority,
                "quote_required": False,
                "request_source": "INSPECTION",
            },
            idempotency_key=f"inspection-exception:{exception.id}",
            commit=False,
        )
        exception.status = "PROMOTED"
        exception.work_order_id = int(order["id"])
        exception.promoted_by = self.ctx.user_id or None
        self.repo.save(exception)
        self.audit.record(
            action="promote",
            resource_type="INSPECTION_EXCEPTION",
            resource_id=int(exception.id),
            park_id=int(exception.park_id),
            detail={"work_order_id": int(order["id"]), "reason": reason},
        )
        return int(order["id"])

    def submit_task(self, task_id: int, data: dict[str, Any], *, key: str) -> dict[str, Any]:
        self._permission("inspection:execute")
        existing = self.repo.task_event_by_key(key)
        if existing is not None:
            if int(existing.task_id) != int(task_id) or existing.event_type != "SUBMITTED":
                raise AppError("Idempotency-Key 已用于不同请求", code="IDEMPOTENCY_KEY_REUSED", status_code=409)
            return self._task_dict(self._require_task(task_id), detail=True)
        row = self._require_task(task_id, for_update=True)
        if int(row.assignee_user_id) != int(self.ctx.user_id) and not self.ctx.has_permission(
            "inspection:dispatch"
        ):
            raise AppError("仅执行人可提交巡检", code="ASSIGNEE_REQUIRED", status_code=403)
        _expected(row, data["expected_version"])
        if row.status != "IN_PROGRESS":
            raise AppError("巡检任务尚未开始或已结束", code="INSPECTION_STATE_INVALID", status_code=409)
        snapshot_items = {
            str(item["item_code"]): item
            for item in (row.template_snapshot_json or {}).get("items", [])
        }
        supplied = data.get("results") or []
        result_map = {str(item.get("item_code") or "").strip().upper(): item for item in supplied}
        if len(result_map) != len(supplied) or set(result_map) != set(snapshot_items):
            raise AppError("巡检结果必须与任务快照逐项一致", code="INSPECTION_RESULT_MISMATCH", status_code=400)
        failed = False
        critical_exceptions = []
        for code, item in snapshot_items.items():
            supplied_item = result_map[code]
            text_value, number_value, passed = validate_result(item, supplied_item.get("value"))
            failed = failed or not passed
            evidence = [str(value).strip() for value in supplied_item.get("evidence_refs") or []]
            if len(evidence) > 20 or any(not value or len(value) > 255 for value in evidence):
                raise AppError("evidence_refs 无效", code="VALIDATION_ERROR", status_code=400)
            remark = bounded_text(
                supplied_item.get("remark"), field="remark", maximum=1000
            ) or None
            self.repo.create_result(
                park_id=int(row.park_id),
                task_id=int(row.id),
                item_code=code,
                label=item["label"],
                position=int(item["position"]),
                result_type=item["result_type"],
                text_value=text_value,
                number_value=number_value,
                passed=passed,
                critical=bool(item.get("critical")),
                evidence_refs_json=evidence,
                remark=remark,
                recorded_by=self.ctx.user_id or None,
                recorded_at=utc_now(),
            )
            if not passed:
                severity = "CRITICAL" if item.get("critical") else "HIGH"
                exception = self.repo.create_exception(
                    park_id=int(row.park_id),
                    task_id=int(row.id),
                    item_code=code,
                    severity=severity,
                    summary=remark or f"{item['label']} 检查未通过",
                    status="OPEN",
                )
                if severity == "CRITICAL":
                    critical_exceptions.append(exception)
        before = row.status
        target = "FAILED" if failed else "PASSED"
        row.status = transition_task(row.status, target)
        row.submitted_at = utc_now()
        row.completed_by = self.ctx.user_id or None
        row.idempotency_key = key
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        event = self._task_event(
            row,
            event_type="SUBMITTED",
            from_status=before,
            to_status=target,
            key=key,
            detail={"failed": failed, "result_count": len(result_map)},
        )
        self.work_items.complete_by_source(
            source_type="INSPECTION_TASK",
            source_id=str(row.id),
            item_type=INSPECTION_ITEM_TYPE,
            commit=False,
        )
        for exception in critical_exceptions:
            self._promote_exception(exception, reason="关键检查项未通过，自动转工单")
        self.audit.record(
            action="submit",
            resource_type="INSPECTION_TASK",
            resource_id=int(row.id),
            park_id=int(row.park_id),
            detail={"event_id": int(event.id), "status": target},
        )
        self._commit(code="INSPECTION_SUBMISSION_CONFLICT", message="巡检结果重复或并发冲突")
        return self._task_dict(row, detail=True)

    def promote_exception(self, exception_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("inspection:dispatch")
        exception = self.repo.get_exception(exception_id, for_update=True)
        if exception is None:
            raise AppError("巡检异常不存在", code="INSPECTION_EXCEPTION_NOT_FOUND", status_code=404)
        order_id = self._promote_exception(
            exception,
            reason=bounded_text(data.get("reason"), field="reason", maximum=1000, required=True),
        )
        self.session.commit()
        return {"exception_id": int(exception.id), "work_order_id": order_id, "status": exception.status}

    def sweep_missed(self, *, as_of: datetime | None = None) -> dict[str, Any]:
        self._permission("inspection:sweep")
        reference = _naive_utc(as_of, field="as_of") if as_of else utc_now()
        missed: list[int] = []
        work_orders: list[int] = []
        for row in self.repo.overdue_tasks(reference):
            before = row.status
            row.status = transition_task(row.status, "MISSED")
            row.lock_version = int(row.lock_version) + 1
            self.repo.save(row)
            self._task_event(
                row,
                event_type="MISSED",
                from_status=before,
                to_status="MISSED",
                key=f"inspection-missed:{row.id}",
                at=reference,
            )
            self.work_items.ensure_from_source(
                source_type="INSPECTION_TASK",
                source_id=str(row.id),
                item_type=INSPECTION_ITEM_TYPE,
                title=f"巡检逾期 #{row.id}",
                park_id=int(row.park_id),
                priority="URGENT",
                assignee_user_id=int(row.assignee_user_id),
                due_at=reference.isoformat(),
                deep_link="/facility-operations",
                commit=False,
            )
            schedule = self.repo.get_schedule(int(row.schedule_id))
            if schedule is not None and bool(schedule.missed_work_order):
                device = self._require_device(int(row.device_id))
                order = self.work_orders.create_system_order(
                    {
                        "park_id": int(row.park_id),
                        "unit_id": device.unit_id,
                        "title": f"巡检任务逾期：{device.name}",
                        "description": f"巡检任务 #{row.id} 未在时限内完成",
                        "category": "INSPECTION",
                        "priority": "HIGH",
                        "quote_required": False,
                        "request_source": "INSPECTION",
                    },
                    idempotency_key=f"inspection-missed:{row.id}",
                    commit=False,
                )
                work_orders.append(int(order["id"]))
            missed.append(int(row.id))
        self.audit.record(
            action="sweep_missed",
            resource_type="INSPECTION_TASK",
            resource_id=None,
            detail={"as_of": reference.isoformat(), "missed": len(missed)},
        )
        self.session.commit()
        return {"missed_ids": missed, "work_order_ids": work_orders, "as_of": reference.isoformat()}

    @staticmethod
    def _provider_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "code": row.code,
            "name": row.name,
            "adapter_kind": row.adapter_kind,
            "environment": row.environment,
            "status": row.status,
            "credential_ref": row.credential_ref,
            "severity_mapping": dict(row.severity_mapping_json or {}),
            "correlation_minutes": int(row.correlation_minutes),
            "last_health_at": row.last_health_at.isoformat() if row.last_health_at else None,
            "last_health_code": row.last_health_code,
            "lock_version": int(row.lock_version),
            "capability_state": (
                "SANDBOX_VERIFIED"
                if row.status == "SANDBOX"
                else "EXTERNAL_CONNECTION_NOT_VERIFIED"
                if row.status != "CONNECTED"
                else "CONNECTED"
            ),
        }

    def list_providers(self) -> list[dict[str, Any]]:
        self._permission("iot:provider_manage", "iot:alarm_read")
        return [self._provider_dict(row) for row in self.repo.list_providers()]

    def create_provider(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("iot:provider_manage")
        adapter = str(data.get("adapter_kind") or "SANDBOX").strip().upper()
        if adapter not in {"LOCAL", "SANDBOX", "HTTP"}:
            raise AppError("adapter_kind 无效", code="VALIDATION_ERROR", status_code=400)
        mapping = {
            str(key).strip().upper(): normalize_severity(value)
            for key, value in (data.get("severity_mapping") or {}).items()
        }
        credential_ref = bounded_text(
            data.get("credential_ref"), field="credential_ref", maximum=128
        ) or None
        if credential_ref and any(
            token in credential_ref.lower() for token in ("password=", "token=", "secret=")
        ):
            raise AppError("credential_ref 只能保存密钥引用", code="VALIDATION_ERROR", status_code=400)
        row = self.repo.create_provider(
            code=bounded_text(data.get("code"), field="code", maximum=64, required=True).upper(),
            name=bounded_text(data.get("name"), field="name", maximum=128, required=True),
            adapter_kind=adapter,
            environment=bounded_text(
                data.get("environment") or "LOCAL",
                field="environment",
                maximum=16,
                required=True,
            ).upper(),
            status="SANDBOX" if adapter in {"LOCAL", "SANDBOX"} else "NOT_CONNECTED",
            credential_ref=credential_ref,
            severity_mapping_json=mapping,
            correlation_minutes=int(data.get("correlation_minutes") or 30),
            lock_version=1,
        )
        if int(row.correlation_minutes) < 1 or int(row.correlation_minutes) > 10080:
            raise AppError("correlation_minutes 无效", code="VALIDATION_ERROR", status_code=400)
        self.audit.record(
            action="create",
            resource_type="IOT_PROVIDER",
            resource_id=int(row.id),
            detail={"code": row.code, "status": row.status, "adapter": adapter},
        )
        self._commit(code="IOT_PROVIDER_CONFLICT", message="IoT 提供方编码冲突")
        return self._provider_dict(row)

    @staticmethod
    def _binding_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "provider_id": int(row.provider_id),
            "device_id": int(row.device_id),
            "external_device_key": row.external_device_key,
            "status": row.status,
            "lock_version": int(row.lock_version),
            "activated_at": row.activated_at.isoformat(),
            "retired_at": row.retired_at.isoformat() if row.retired_at else None,
            "change_reason": row.change_reason,
        }

    def list_bindings(self, *, provider_id: int | None = None) -> list[dict[str, Any]]:
        self._permission("iot:binding_manage", "iot:alarm_read")
        return [self._binding_dict(row) for row in self.repo.list_bindings(provider_id=provider_id)]

    def create_binding(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("iot:binding_manage")
        provider = self.repo.get_provider(int(data["provider_id"]))
        if provider is None:
            raise AppError("IoT 提供方不存在", code="IOT_PROVIDER_NOT_FOUND", status_code=404)
        if provider.status not in {"SANDBOX", "CONNECTED"}:
            raise AppError("IoT 提供方尚未可用", code="IOT_PROVIDER_UNAVAILABLE", status_code=409)
        device = self._require_device(int(data["device_id"]))
        if device.status == "RETIRED":
            raise AppError("退役设备不可绑定", code="FACILITY_DEVICE_INVALID", status_code=409)
        now = utc_now()
        reason = bounded_text(data.get("reason"), field="reason", maximum=1000, required=True)
        row = self.repo.create_binding(
            park_id=int(device.park_id),
            provider_id=int(provider.id),
            device_id=int(device.id),
            external_device_key=bounded_text(
                data.get("external_device_key"),
                field="external_device_key",
                maximum=128,
                required=True,
            ),
            status="ACTIVE",
            lock_version=1,
            activated_at=now,
            changed_by=self.ctx.user_id or None,
            change_reason=reason,
        )
        self.repo.create_binding_history(
            binding_id=int(row.id),
            version_no=1,
            snapshot_json=self._binding_dict(row),
            action="ACTIVATED",
            reason=reason,
            changed_by=self.ctx.user_id or None,
            changed_at=now,
        )
        self.audit.record(
            action="bind",
            resource_type="IOT_DEVICE_BINDING",
            resource_id=int(row.id),
            park_id=int(row.park_id),
            detail={"provider_id": int(provider.id), "device_id": int(device.id)},
        )
        self._commit(code="IOT_BINDING_CONFLICT", message="IoT 设备绑定冲突")
        return self._binding_dict(row)

    def retire_binding(self, binding_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("iot:binding_manage")
        row = self.repo.get_binding(binding_id, for_update=True)
        if row is None:
            raise AppError("IoT 设备绑定不存在", code="IOT_BINDING_NOT_FOUND", status_code=404)
        _expected(row, data["expected_version"])
        if row.status == "RETIRED":
            return self._binding_dict(row)
        reason = bounded_text(data.get("reason"), field="reason", maximum=1000, required=True)
        row.status = "RETIRED"
        row.retired_at = utc_now()
        row.changed_by = self.ctx.user_id or None
        row.change_reason = reason
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        self.repo.create_binding_history(
            binding_id=int(row.id),
            version_no=int(row.lock_version),
            snapshot_json=self._binding_dict(row),
            action="RETIRED",
            reason=reason,
            changed_by=self.ctx.user_id or None,
            changed_at=row.retired_at,
        )
        self.audit.record(
            action="retire",
            resource_type="IOT_DEVICE_BINDING",
            resource_id=int(row.id),
            park_id=int(row.park_id),
            detail={"reason": reason},
        )
        self.session.commit()
        return self._binding_dict(row)

    @staticmethod
    def _safe_payload(value: Any) -> dict[str, str | int | float | bool | None]:
        if not isinstance(value, dict) or len(value) > 30:
            raise AppError("payload 必须为最多 30 项对象", code="VALIDATION_ERROR", status_code=400)
        blocked = ("password", "token", "secret", "credential", "phone", "email", "idcard")
        result: dict[str, str | int | float | bool | None] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key).strip()
            if not key or len(key) > 64 or any(term in key.lower() for term in blocked):
                continue
            if raw_value is None or isinstance(raw_value, (int, float, bool)):
                result[key] = raw_value
            elif isinstance(raw_value, str):
                result[key] = raw_value[:255]
        return result

    def _alarm_dict(self, row, *, detail: bool = False) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        result = {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "binding_id": int(row.binding_id),
            "device_id": int(row.device_id),
            "alarm_type": row.alarm_type,
            "title": row.title,
            "severity": row.severity,
            "status": row.status,
            "occurrence_count": int(row.occurrence_count),
            "first_seen_at": row.first_seen_at.isoformat(),
            "last_seen_at": row.last_seen_at.isoformat(),
            "work_order_id": row.work_order_id,
            "lock_version": int(row.lock_version),
            "resolution_reason": row.resolution_reason,
        }
        if detail:
            result["events"] = [
                {
                    "id": int(item.id),
                    "source_event_id": item.source_event_id,
                    "source_time": item.source_time.isoformat(),
                    "raw_severity": item.raw_severity,
                    "canonical_severity": item.canonical_severity,
                    "payload": item.safe_payload_json or {},
                }
                for item in self.repo.alarm_events(int(row.id))
            ]
            result["escalations"] = [
                {
                    "level": int(item.level),
                    "reason": item.reason,
                    "occurred_at": item.occurred_at.isoformat(),
                }
                for item in self.repo.alarm_escalations(int(row.id))
            ]
        return result

    def list_alarms(
        self,
        *,
        page: int,
        page_size: int,
        park_id: int | None = None,
        status: str | None = None,
        severity: str | None = None,
    ) -> dict[str, Any]:
        self._permission("iot:alarm_read")
        if park_id is not None:
            self._assert_park(park_id)
        normalized_status = str(status).upper() if status else None
        normalized_severity = normalize_severity(severity) if severity else None
        if normalized_status and normalized_status not in ALARM_STATUSES:
            raise AppError("status 无效", code="VALIDATION_ERROR", status_code=400)
        rows = self.repo.list_alarms(
            offset=(page - 1) * page_size,
            limit=page_size,
            park_id=park_id,
            status=normalized_status,
            severity=normalized_severity,
        )
        return {
            "items": [self._alarm_dict(row) for row in rows],
            "total": self.repo.count_alarms(
                park_id=park_id, status=normalized_status, severity=normalized_severity
            ),
            "page": page,
            "page_size": page_size,
        }

    def get_alarm(self, alarm_id: int) -> dict[str, Any]:
        self._permission("iot:alarm_read")
        row = self.repo.get_alarm(alarm_id)
        if row is None:
            raise AppError("IoT 告警不存在", code="IOT_ALARM_NOT_FOUND", status_code=404)
        return self._alarm_dict(row, detail=True)

    def _ensure_alarm_work_order(self, alarm) -> int:  # type: ignore[no-untyped-def]
        if alarm.work_order_id is not None:
            return int(alarm.work_order_id)
        device = self._require_device(int(alarm.device_id))
        order = self.work_orders.create_system_order(
            {
                "park_id": int(alarm.park_id),
                "unit_id": device.unit_id,
                "title": f"IoT 告警：{alarm.title}",
                "description": f"{device.name} / {alarm.alarm_type}",
                "category": "IOT_ALARM",
                "priority": "URGENT" if alarm.severity == "CRITICAL" else "HIGH",
                "quote_required": False,
                "request_source": "IOT_ALARM",
            },
            idempotency_key=f"iot-alarm:{alarm.id}",
            commit=False,
        )
        alarm.work_order_id = int(order["id"])
        self.repo.save(alarm)
        return int(order["id"])

    def ingest_alarm(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("iot:ingest")
        provider = self.repo.get_provider(int(data["provider_id"]), for_update=True)
        if provider is None:
            raise AppError("IoT 提供方不存在", code="IOT_PROVIDER_NOT_FOUND", status_code=404)
        if provider.status not in {"SANDBOX", "CONNECTED"}:
            raise AppError("IoT 提供方不可接收事件", code="IOT_PROVIDER_UNAVAILABLE", status_code=409)
        external_key = bounded_text(
            data.get("external_device_key"),
            field="external_device_key",
            maximum=128,
            required=True,
        )
        binding = self.repo.active_binding_by_external_key(
            int(provider.id), external_key, for_update=True
        )
        if binding is None:
            raise AppError("IoT 设备未绑定", code="IOT_BINDING_NOT_FOUND", status_code=404)
        source_event_id = bounded_text(
            data.get("source_event_id"), field="source_event_id", maximum=128, required=True
        )
        source_time = _naive_utc(data.get("source_time"), field="source_time")
        now = utc_now()
        if source_time > now + timedelta(minutes=5) or source_time < now - timedelta(days=30):
            raise AppError("source_time 超出允许窗口", code="IOT_EVENT_TIME_INVALID", status_code=400)
        safe_payload = self._safe_payload(data.get("payload") or {})
        digest_source = {
            "external_device_key": external_key,
            "alarm_type": str(data.get("alarm_type") or "").strip().upper(),
            "severity": str(data.get("severity") or "").strip().upper(),
            "source_time": source_time.isoformat(),
            "payload": safe_payload,
        }
        digest = sha256(
            json.dumps(digest_source, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        replay = self.repo.source_event(int(provider.id), source_event_id)
        if replay is not None:
            if replay.payload_digest != digest:
                raise AppError("source_event_id 已用于不同事件", code="IOT_EVENT_CONFLICT", status_code=409)
            alarm = self.repo.get_alarm(int(replay.alarm_id))
            if alarm is None:
                raise AppError("IoT 告警不存在", code="IOT_ALARM_NOT_FOUND", status_code=404)
            return {"replayed": True, "alarm": self._alarm_dict(alarm, detail=True)}
        alarm_type = bounded_text(
            data.get("alarm_type"), field="alarm_type", maximum=64, required=True
        ).upper()
        title = bounded_text(data.get("title"), field="title", maximum=255, required=True)
        severity = normalize_severity(data.get("severity"), provider.severity_mapping_json or {})
        alarm = self.repo.active_alarm(int(binding.id), alarm_type, for_update=True)
        correlation = timedelta(minutes=int(provider.correlation_minutes))
        if alarm is not None and source_time - alarm.last_seen_at > correlation:
            alarm.status = "RESOLVED"
            alarm.resolved_at = now
            alarm.resolution_reason = "关联窗口结束，后续事件另建告警"
            alarm.status = "CLOSED"
            alarm.closed_at = now
            alarm.lock_version = int(alarm.lock_version) + 1
            self.repo.save(alarm)
            self.work_items.complete_by_source(
                source_type="IOT_ALARM",
                source_id=str(alarm.id),
                item_type=ALARM_ITEM_TYPE,
                commit=False,
            )
            alarm = None
        if alarm is None:
            alarm = self.repo.create_alarm(
                park_id=int(binding.park_id),
                binding_id=int(binding.id),
                device_id=int(binding.device_id),
                alarm_type=alarm_type,
                title=title,
                severity=severity,
                status="OPEN",
                occurrence_count=1,
                first_seen_at=source_time,
                last_seen_at=source_time,
                lock_version=1,
            )
        else:
            alarm.occurrence_count = int(alarm.occurrence_count) + 1
            alarm.last_seen_at = max(alarm.last_seen_at, source_time)
            if severity_rank(severity) > severity_rank(alarm.severity):
                alarm.severity = severity
            alarm.title = title
            alarm.lock_version = int(alarm.lock_version) + 1
            self.repo.save(alarm)
        self.repo.create_alarm_event(
            park_id=int(binding.park_id),
            provider_id=int(provider.id),
            binding_id=int(binding.id),
            alarm_id=int(alarm.id),
            source_event_id=source_event_id,
            source_time=source_time,
            received_at=now,
            raw_severity=str(data.get("severity") or ""),
            canonical_severity=severity,
            alarm_type=alarm_type,
            title=title,
            payload_digest=digest,
            safe_payload_json=safe_payload,
        )
        self.work_items.ensure_from_source(
            source_type="IOT_ALARM",
            source_id=str(alarm.id),
            item_type=ALARM_ITEM_TYPE,
            title=f"处置 IoT 告警：{alarm.title}",
            description=f"已关联 {alarm.occurrence_count} 次事件",
            park_id=int(alarm.park_id),
            priority="URGENT" if alarm.severity == "CRITICAL" else "HIGH",
            deep_link="/facility-operations",
            commit=False,
        )
        if alarm.severity in {"HIGH", "CRITICAL"}:
            self._ensure_alarm_work_order(alarm)
        self.audit.record(
            action="ingest",
            resource_type="IOT_ALARM",
            resource_id=int(alarm.id),
            park_id=int(alarm.park_id),
            detail={
                "provider_id": int(provider.id),
                "source_event_id": source_event_id,
                "severity": severity,
                "occurrences": int(alarm.occurrence_count),
            },
        )
        self._commit(code="IOT_EVENT_CONFLICT", message="IoT 事件重复或告警关联冲突")
        return {"replayed": False, "alarm": self._alarm_dict(alarm, detail=True)}

    def transition_alarm(
        self, alarm_id: int, target: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        self._permission("iot:alarm_manage")
        row = self.repo.get_alarm(alarm_id, for_update=True)
        if row is None:
            raise AppError("IoT 告警不存在", code="IOT_ALARM_NOT_FOUND", status_code=404)
        _expected(row, data["expected_version"])
        target = str(target).upper()
        before = row.status
        row.status = transition_alarm(row.status, target)
        reason = bounded_text(data.get("reason"), field="reason", maximum=1000) or None
        now = utc_now()
        if target == "ACKNOWLEDGED":
            row.acknowledged_at = now
            row.acknowledged_by = self.ctx.user_id or None
        elif target == "RESOLVED":
            if not reason:
                raise AppError("解决原因必填", code="VALIDATION_ERROR", status_code=400)
            row.resolved_at = now
            row.resolution_reason = reason
            self.work_items.complete_by_source(
                source_type="IOT_ALARM",
                source_id=str(row.id),
                item_type=ALARM_ITEM_TYPE,
                commit=False,
            )
        elif target == "CLOSED":
            row.closed_at = now
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        self.audit.record(
            action=target.lower(),
            resource_type="IOT_ALARM",
            resource_id=int(row.id),
            park_id=int(row.park_id),
            detail={"from": before, "to": target, "reason": reason},
        )
        self._commit(code="IOT_ALARM_CONFLICT", message="IoT 告警并发更新冲突")
        return self._alarm_dict(row, detail=True)

    def sweep_alarm_escalations(self, *, as_of: datetime | None = None) -> dict[str, Any]:
        self._permission("iot:alarm_sweep")
        reference = _naive_utc(as_of, field="as_of") if as_of else utc_now()
        escalated: list[dict[str, int]] = []
        for alarm in self.repo.alarms_for_escalation(reference):
            age_minutes = int((reference - alarm.first_seen_at).total_seconds() // 60)
            thresholds = (10, 30, 120) if alarm.severity == "CRITICAL" else (30, 120, 360)
            target_level = sum(age_minutes >= threshold for threshold in thresholds)
            existing = {int(item.level) for item in self.repo.alarm_escalations(int(alarm.id))}
            for level in range(1, target_level + 1):
                if level in existing:
                    continue
                self.repo.create_escalation(
                    park_id=int(alarm.park_id),
                    alarm_id=int(alarm.id),
                    level=level,
                    reason=f"{alarm.severity} 告警持续 {age_minutes} 分钟未关闭",
                    created_by=self.ctx.user_id or None,
                    occurred_at=reference,
                )
                escalated.append({"alarm_id": int(alarm.id), "level": level})
            if target_level:
                self._ensure_alarm_work_order(alarm)
        self.audit.record(
            action="sweep_escalation",
            resource_type="IOT_ALARM",
            resource_id=None,
            detail={"as_of": reference.isoformat(), "created": len(escalated)},
        )
        self._commit(code="IOT_ESCALATION_CONFLICT", message="IoT 告警升级并发冲突")
        return {"escalations": escalated, "as_of": reference.isoformat()}

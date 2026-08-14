"""Workforce application orchestration over pure rules and scoped repositories."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.modules.workbench.application.work_item_service import WorkItemService
from app.modules.workflow.application.approval_service import ApprovalService
from app.modules.workforce.domain.rules import (
    clean_text,
    cycle_dates,
    employment_dates,
    enum_value,
    fingerprint,
    naive_utc,
    normalize_code,
    payload_hash,
    qualification_dates,
    shift_times,
)
from app.modules.workforce.infrastructure.repository import WorkforceRepository
from app.shared.tenant_context import TenantContext

EMPLOYEE_STATUSES = {"ACTIVE", "SUSPENDED", "LEFT"}
SUMMARY_STATUSES = {"NORMAL", "LATE", "EARLY", "ABSENT", "LEAVE", "ANOMALY", "ADJUSTED"}
APPROVAL_MAP = {
    "PENDING": "PENDING_APPROVAL",
    "APPROVED": "APPROVED",
    "REJECTED": "REJECTED",
    "RETURNED": "RETURNED",
    "WITHDRAWN": "CANCELLED",
}


class WorkforceService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.repo = WorkforceRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)
        self.approvals = ApprovalService(session, ctx)
        self.work_items = WorkItemService(session, ctx)
        settings = get_settings()
        self._fingerprint_secret = settings.pii_fingerprint_secret or settings.jwt_secret

    def _permission(self, *codes: str) -> None:
        if any(self.ctx.has_permission(code) for code in codes):
            return
        raise AppError("无操作权限", code="PERMISSION_DENIED", status_code=403)

    def _park(self, park_id: Any) -> int:
        value = int(park_id)
        if not self.repo.park_exists(value):
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        if not self.ctx.allows_park(value):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        return value

    def _commit(self, code: str, message: str) -> None:
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(message, code=code, status_code=409) from exc

    @staticmethod
    def _expected(row, value: Any) -> None:  # type: ignore[no-untyped-def]
        if int(row.lock_version) != int(value):
            raise AppError(
                "数据已被其他操作更新",
                code="VERSION_CONFLICT",
                status_code=409,
                data={"current_version": int(row.lock_version)},
            )

    def _employee(self, employee_id: int, *, for_update: bool = False):  # type: ignore[no-untyped-def]
        row = self.repo.get_employee(employee_id, for_update=for_update)
        if row is None:
            raise AppError("员工不存在", code="WORKFORCE_EMPLOYEE_NOT_FOUND", status_code=404)
        return row

    @staticmethod
    def _event_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "event_type": row.event_type,
            "reason": row.reason,
            "actor_user_id": row.actor_user_id,
            "occurred_at": row.occurred_at.isoformat(),
        }

    def _employee_dict(self, row, *, detail: bool = False) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        data = {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "employee_no": row.employee_no,
            "display_name": row.display_name,
            "department_name": row.department_name,
            "position_name": row.position_name,
            "user_id": row.user_id,
            "mobile_masked": row.mobile_masked,
            "identity_masked": row.identity_masked,
            "start_date": row.start_date.isoformat(),
            "end_date": row.end_date.isoformat() if row.end_date else None,
            "status": row.status,
            "lock_version": int(row.lock_version),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        if detail:
            data["events"] = [
                self._event_dict(event) for event in self.repo.employee_events(int(row.id))
            ]
        return data

    def list_employees(
        self,
        *,
        page: int,
        page_size: int,
        park_id: int | None,
        status: str | None,
        keyword: str | None,
    ) -> dict[str, Any]:
        self._permission("workforce:read", "workforce:manage")
        if park_id is not None:
            self._park(park_id)
        if status:
            enum_value(status, field="status", allowed=EMPLOYEE_STATUSES)
        page, page_size = max(1, page), min(max(1, page_size), 200)
        query = {
            "park_id": park_id,
            "status": status,
            "keyword": clean_text(keyword, field="keyword", maximum=100, required=False),
        }
        rows = self.repo.list_employees(offset=(page - 1) * page_size, limit=page_size, **query)
        return {
            "total": self.repo.count_employees(**query),
            "page": page,
            "page_size": page_size,
            "items": [self._employee_dict(row) for row in rows],
        }

    def get_employee(self, employee_id: int) -> dict[str, Any]:
        self._permission("workforce:read", "workforce:manage")
        return self._employee_dict(self._employee(employee_id), detail=True)

    def create_employee(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:manage")
        park_id = self._park(data["park_id"])
        start_date, end_date = data["start_date"], data.get("end_date")
        employment_dates(start_date, end_date)
        user_id = data.get("user_id")
        if user_id is not None and self.repo.active_user(int(user_id), park_id) is None:
            raise AppError(
                "用户不存在或无该园区范围", code="WORKFORCE_USER_SCOPE_INVALID", status_code=404
            )
        mobile_masked, mobile_fp = fingerprint(data.get("mobile"), pepper=self._fingerprint_secret)
        identity_masked, identity_fp = fingerprint(
            data.get("identity_number"), pepper=self._fingerprint_secret
        )
        row = self.repo.create_employee(
            park_id=park_id,
            employee_no=normalize_code(data["employee_no"], field="employee_no"),
            display_name=clean_text(data["display_name"], field="display_name", maximum=128),
            department_name=clean_text(
                data.get("department_name"), field="department_name", maximum=128, required=False
            ),
            position_name=clean_text(
                data.get("position_name"), field="position_name", maximum=128, required=False
            ),
            user_id=user_id,
            mobile_masked=mobile_masked,
            mobile_fingerprint=mobile_fp,
            identity_masked=identity_masked,
            identity_fingerprint=identity_fp,
            start_date=start_date,
            end_date=end_date,
            status="ACTIVE",
            lock_version=1,
            created_by=self.ctx.user_id or None,
        )
        self.repo.create_employee_event(
            park_id=park_id,
            employee_id=row.id,
            event_type="CREATED",
            reason="员工建档",
            actor_user_id=self.ctx.user_id or None,
            occurred_at=utc_now(),
        )
        self.audit.record(
            action="create",
            resource_type="WORKFORCE_EMPLOYEE",
            resource_id=row.id,
            park_id=park_id,
            detail={
                "employee_no": row.employee_no,
                "user_id": user_id,
                "pii_stored": "MASKED_AND_FINGERPRINT_ONLY",
            },
        )
        self._commit("WORKFORCE_EMPLOYEE_CONFLICT", "员工编号、身份绑定或身份指纹冲突")
        return self._employee_dict(row, detail=True)

    def update_employee(self, employee_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:manage")
        row = self._employee(employee_id, for_update=True)
        self._expected(row, data["expected_version"])
        if row.status == "LEFT":
            raise AppError(
                "已离职员工不可修改", code="WORKFORCE_EMPLOYEE_STATE_INVALID", status_code=409
            )
        if "display_name" in data:
            row.display_name = clean_text(data["display_name"], field="display_name", maximum=128)
        for field in ("department_name", "position_name"):
            if field in data:
                setattr(
                    row,
                    field,
                    clean_text(data.get(field), field=field, maximum=128, required=False),
                )
        if "user_id" in data:
            user_id = data.get("user_id")
            if (
                user_id is not None
                and self.repo.active_user(int(user_id), int(row.park_id)) is None
            ):
                raise AppError(
                    "用户不存在或无该园区范围", code="WORKFORCE_USER_SCOPE_INVALID", status_code=404
                )
            row.user_id = user_id
        if "mobile" in data:
            row.mobile_masked, row.mobile_fingerprint = fingerprint(
                data.get("mobile"), pepper=self._fingerprint_secret
            )
        if "identity_number" in data:
            row.identity_masked, row.identity_fingerprint = fingerprint(
                data.get("identity_number"), pepper=self._fingerprint_secret
            )
        if "end_date" in data:
            employment_dates(row.start_date, data.get("end_date"))
            row.end_date = data.get("end_date")
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        reason = clean_text(data["reason"], field="reason", maximum=1000)
        self.repo.create_employee_event(
            park_id=row.park_id,
            employee_id=row.id,
            event_type="UPDATED",
            reason=reason,
            actor_user_id=self.ctx.user_id or None,
            occurred_at=utc_now(),
        )
        self.audit.record(
            action="update",
            resource_type="WORKFORCE_EMPLOYEE",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"reason": reason, "version": row.lock_version},
        )
        self._commit("WORKFORCE_EMPLOYEE_CONFLICT", "员工更新冲突")
        return self._employee_dict(row, detail=True)

    def change_employee_status(self, employee_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:manage")
        row = self._employee(employee_id, for_update=True)
        self._expected(row, data["expected_version"])
        status = enum_value(data["status"], field="status", allowed=EMPLOYEE_STATUSES)
        if status == "LEFT":
            end_date = data.get("end_date") or utc_now().date()
            employment_dates(row.start_date, end_date)
            row.end_date, row.user_id = end_date, None
        elif row.status == "LEFT":
            raise AppError(
                "已离职员工不可直接恢复", code="WORKFORCE_EMPLOYEE_STATE_INVALID", status_code=409
            )
        row.status = status
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        reason = clean_text(data["reason"], field="reason", maximum=1000)
        self.repo.create_employee_event(
            park_id=row.park_id,
            employee_id=row.id,
            event_type=f"STATUS_{status}",
            reason=reason,
            actor_user_id=self.ctx.user_id or None,
            occurred_at=utc_now(),
        )
        self.audit.record(
            action="status",
            resource_type="WORKFORCE_EMPLOYEE",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"status": status, "reason": reason},
        )
        self._commit("WORKFORCE_EMPLOYEE_CONFLICT", "员工状态更新冲突")
        return self._employee_dict(row, detail=True)

    # Shift and roster
    @staticmethod
    def _shift_version_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "version_no": int(row.version_no),
            "start_time": row.start_time.isoformat(),
            "end_time": row.end_time.isoformat(),
            "cross_day": bool(row.cross_day),
            "break_minutes": int(row.break_minutes),
            "late_grace_minutes": int(row.late_grace_minutes),
            "early_grace_minutes": int(row.early_grace_minutes),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    def _shift_dict(self, row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "code": row.code,
            "name": row.name,
            "status": row.status,
            "current_version": int(row.current_version),
            "lock_version": int(row.lock_version),
            "versions": [
                self._shift_version_dict(item) for item in self.repo.shift_versions(int(row.id))
            ],
        }

    def list_shifts(self, park_id: int | None) -> list[dict[str, Any]]:
        self._permission("workforce:read", "workforce:schedule")
        if park_id is not None:
            self._park(park_id)
        return [self._shift_dict(row) for row in self.repo.list_shift_templates(park_id)]

    def create_shift(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:schedule")
        park_id = self._park(data["park_id"])
        shift_times(
            data["start_time"],
            data["end_time"],
            bool(data["cross_day"]),
            int(data["break_minutes"]),
        )
        row = self.repo.create_shift_template(
            park_id=park_id,
            code=normalize_code(data["code"], field="code"),
            name=clean_text(data["name"], field="name", maximum=128),
            status="ACTIVE",
            current_version=1,
            lock_version=1,
            created_by=self.ctx.user_id or None,
        )
        self.repo.create_shift_version(
            park_id=park_id,
            template_id=row.id,
            version_no=1,
            start_time=data["start_time"],
            end_time=data["end_time"],
            cross_day=data["cross_day"],
            break_minutes=data["break_minutes"],
            late_grace_minutes=data["late_grace_minutes"],
            early_grace_minutes=data["early_grace_minutes"],
            published_by=self.ctx.user_id or None,
        )
        self.audit.record(
            action="create",
            resource_type="WORKFORCE_SHIFT",
            resource_id=row.id,
            park_id=park_id,
            detail={"code": row.code, "version": 1},
        )
        self._commit("WORKFORCE_SHIFT_CONFLICT", "班次编码冲突")
        return self._shift_dict(row)

    def add_shift_version(self, template_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:schedule")
        row = self.repo.get_shift_template(template_id, for_update=True)
        if row is None:
            raise AppError("班次不存在", code="WORKFORCE_SHIFT_NOT_FOUND", status_code=404)
        self._expected(row, data["expected_version"])
        if row.status != "ACTIVE":
            raise AppError(
                "已停用班次不可发布版本", code="WORKFORCE_SHIFT_STATE_INVALID", status_code=409
            )
        shift_times(
            data["start_time"],
            data["end_time"],
            bool(data["cross_day"]),
            int(data["break_minutes"]),
        )
        version = int(row.current_version) + 1
        self.repo.create_shift_version(
            park_id=row.park_id,
            template_id=row.id,
            version_no=version,
            start_time=data["start_time"],
            end_time=data["end_time"],
            cross_day=data["cross_day"],
            break_minutes=data["break_minutes"],
            late_grace_minutes=data["late_grace_minutes"],
            early_grace_minutes=data["early_grace_minutes"],
            published_by=self.ctx.user_id or None,
        )
        if data.get("name"):
            row.name = clean_text(data["name"], field="name", maximum=128)
        row.current_version, row.lock_version = version, int(row.lock_version) + 1
        self.repo.save(row)
        self.audit.record(
            action="publish_version",
            resource_type="WORKFORCE_SHIFT",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"version": version, "reason": data["reason"]},
        )
        self._commit("WORKFORCE_SHIFT_CONFLICT", "班次版本发布冲突")
        return self._shift_dict(row)

    @staticmethod
    def _assignment_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "employee_id": int(row.employee_id),
            "shift_version_id": int(row.shift_version_id),
            "work_date": row.work_date.isoformat(),
            "status": row.status,
            "reason": row.reason,
            "lock_version": int(row.lock_version),
        }

    def list_assignments(
        self, *, employee_id: int | None, date_from: date, date_to: date
    ) -> list[dict[str, Any]]:
        self._permission("workforce:read", "workforce:schedule")
        if date_to < date_from or (date_to - date_from).days > 366:
            raise AppError("排班查询日期范围无效", code="VALIDATION_ERROR", status_code=400)
        if employee_id is not None:
            self._employee(employee_id)
        return [
            self._assignment_dict(row)
            for row in self.repo.list_assignments(
                employee_id=employee_id, date_from=date_from, date_to=date_to
            )
        ]

    def create_assignment(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:schedule")
        employee = self._employee(data["employee_id"], for_update=True)
        if (
            employee.status != "ACTIVE"
            or data["work_date"] < employee.start_date
            or (employee.end_date and data["work_date"] > employee.end_date)
        ):
            raise AppError(
                "员工在排班日期非在职状态", code="WORKFORCE_EMPLOYEE_INACTIVE", status_code=409
            )
        version = self.repo.get_shift_version(data["shift_version_id"])
        if version is None or int(version.park_id) != int(employee.park_id):
            raise AppError(
                "班次版本不存在", code="WORKFORCE_SHIFT_VERSION_NOT_FOUND", status_code=404
            )
        if self.repo.active_assignment(employee.id, data["work_date"], for_update=True) is not None:
            raise AppError(
                "员工当日已有有效排班", code="WORKFORCE_ASSIGNMENT_CONFLICT", status_code=409
            )
        if self.repo.approved_leave_on(employee.id, data["work_date"]) is not None:
            raise AppError(
                "员工当日存在已批准请假", code="WORKFORCE_LEAVE_CONFLICT", status_code=409
            )
        row = self.repo.create_assignment(
            park_id=employee.park_id,
            employee_id=employee.id,
            shift_version_id=version.id,
            work_date=data["work_date"],
            status="ACTIVE",
            reason=clean_text(data.get("reason"), field="reason", maximum=500, required=False),
            lock_version=1,
            assigned_by=self.ctx.user_id or None,
        )
        self.audit.record(
            action="assign",
            resource_type="WORKFORCE_ROSTER",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"employee_id": row.employee_id, "work_date": row.work_date},
        )
        self._commit("WORKFORCE_ASSIGNMENT_CONFLICT", "员工当日排班冲突")
        return self._assignment_dict(row)

    def cancel_assignment(self, assignment_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:schedule")
        row = self.repo.get_assignment(assignment_id, for_update=True)
        if row is None:
            raise AppError("排班不存在", code="WORKFORCE_ASSIGNMENT_NOT_FOUND", status_code=404)
        self._expected(row, data["expected_version"])
        if row.status != "ACTIVE":
            raise AppError("排班已取消", code="WORKFORCE_ASSIGNMENT_STATE_INVALID", status_code=409)
        row.status, row.reason, row.lock_version = (
            "CANCELLED",
            clean_text(data["reason"], field="reason", maximum=1000),
            int(row.lock_version) + 1,
        )
        self.repo.save(row)
        self.audit.record(
            action="cancel",
            resource_type="WORKFORCE_ROSTER",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"reason": row.reason},
        )
        self._commit("WORKFORCE_ASSIGNMENT_CONFLICT", "排班取消冲突")
        return self._assignment_dict(row)

    # Attendance
    def list_policies(self, park_id: int | None) -> list[dict[str, Any]]:
        self._permission("workforce:read", "workforce:attendance_admin")
        if park_id is not None:
            self._park(park_id)
        return [
            {
                "id": int(row.id),
                "park_id": int(row.park_id),
                "code": row.code,
                "name": row.name,
                "geofence_radius_m": row.geofence_radius_m,
                "allow_manual": row.allow_manual,
                "status": row.status,
                "lock_version": row.lock_version,
            }
            for row in self.repo.list_policies(park_id)
        ]

    def create_policy(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:attendance_admin")
        park_id = self._park(data["park_id"])
        row = self.repo.create_policy(
            park_id=park_id,
            code=normalize_code(data["code"], field="code"),
            name=clean_text(data["name"], field="name", maximum=128),
            geofence_radius_m=data["geofence_radius_m"],
            allow_manual=data["allow_manual"],
            status="ACTIVE",
            lock_version=1,
        )
        self.audit.record(
            action="create",
            resource_type="ATTENDANCE_POLICY",
            resource_id=row.id,
            park_id=park_id,
            detail={"code": row.code},
        )
        self._commit("ATTENDANCE_POLICY_CONFLICT", "考勤规则编码冲突")
        return {
            "id": int(row.id),
            "park_id": park_id,
            "code": row.code,
            "name": row.name,
            "geofence_radius_m": row.geofence_radius_m,
            "allow_manual": row.allow_manual,
            "status": row.status,
            "lock_version": row.lock_version,
        }

    def list_locations(self, park_id: int | None) -> list[dict[str, Any]]:
        self._permission(
            "workforce:read", "workforce:attendance_admin", "workforce:attendance_punch"
        )
        if park_id is not None:
            self._park(park_id)
        return [
            {
                "id": int(row.id),
                "park_id": int(row.park_id),
                "code": row.code,
                "name": row.name,
                "config_ref": row.config_ref,
                "radius_m": row.radius_m,
                "status": row.status,
            }
            for row in self.repo.list_locations(park_id)
        ]

    def create_location(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:attendance_admin")
        park_id = self._park(data["park_id"])
        row = self.repo.create_location(
            park_id=park_id,
            code=normalize_code(data["code"], field="code"),
            name=clean_text(data["name"], field="name", maximum=128),
            config_ref=clean_text(data["config_ref"], field="config_ref", maximum=128),
            radius_m=data["radius_m"],
            status="ACTIVE",
        )
        self.audit.record(
            action="create",
            resource_type="ATTENDANCE_LOCATION",
            resource_id=row.id,
            park_id=park_id,
            detail={"code": row.code, "config_ref": row.config_ref},
        )
        self._commit("ATTENDANCE_LOCATION_CONFLICT", "考勤地点编码冲突")
        return {
            "id": int(row.id),
            "park_id": park_id,
            "code": row.code,
            "name": row.name,
            "config_ref": row.config_ref,
            "radius_m": row.radius_m,
            "status": row.status,
        }

    @staticmethod
    def _punch_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "employee_id": int(row.employee_id),
            "location_id": row.location_id,
            "punch_type": row.punch_type,
            "punched_at": row.punched_at.isoformat(),
            "source": row.source,
            "location_result": row.location_result,
            "distance_m": row.distance_m,
            "device_fingerprint": row.device_fingerprint,
            "created_at": row.created_at.isoformat(),
        }

    def create_punch(self, data: dict[str, Any], *, key: str) -> dict[str, Any]:
        self._permission("workforce:attendance_punch")
        employee = self._employee(data["employee_id"])
        if employee.status != "ACTIVE":
            raise AppError("员工非在职状态", code="WORKFORCE_EMPLOYEE_INACTIVE", status_code=409)
        source = enum_value(data["source"], field="source", allowed={"MANUAL", "DEVICE", "MOBILE"})
        if source == "DEVICE" and not data.get("device_id"):
            raise AppError(
                "设备打卡必须提供设备标识", code="ATTENDANCE_DEVICE_REQUIRED", status_code=400
            )
        location = None
        if data.get("location_id") is not None:
            location = self.repo.get_location(int(data["location_id"]))
            if location is None or int(location.park_id) != int(employee.park_id):
                raise AppError(
                    "考勤地点不存在", code="ATTENDANCE_LOCATION_NOT_FOUND", status_code=404
                )
        distance = data.get("distance_m")
        if location is None or distance is None:
            location_result = "NOT_CHECKED"
        else:
            location_result = "INSIDE" if int(distance) <= int(location.radius_m) else "OUTSIDE"
        canonical = {
            "employee_id": int(employee.id),
            "punch_type": data["punch_type"],
            "punched_at": naive_utc(data["punched_at"]).isoformat(),
            "source": source,
            "location_id": int(location.id) if location else None,
            "distance_m": distance,
            "location_result": location_result,
            "device_fingerprint": hashlib.sha256(
                str(data.get("device_id") or "").encode()
            ).hexdigest()
            if data.get("device_id")
            else None,
        }
        digest = payload_hash(canonical)
        previous = self.repo.punch_by_key(key)
        if previous is not None:
            if previous.payload_hash != digest:
                raise AppError("幂等键已用于其他打卡", code="IDEMPOTENCY_CONFLICT", status_code=409)
            return self._punch_dict(previous)
        row = self.repo.create_punch(
            park_id=employee.park_id,
            employee_id=employee.id,
            location_id=location.id if location else None,
            punch_type=data["punch_type"],
            punched_at=naive_utc(data["punched_at"]),
            source=source,
            location_result=location_result,
            distance_m=distance,
            device_fingerprint=canonical["device_fingerprint"],
            idempotency_key=key,
            payload_hash=digest,
            recorded_by=self.ctx.user_id or None,
            created_at=utc_now(),
        )
        self.audit.record(
            action="punch",
            resource_type="ATTENDANCE_PUNCH",
            resource_id=row.id,
            park_id=row.park_id,
            detail={
                "employee_id": row.employee_id,
                "punch_type": row.punch_type,
                "location_result": row.location_result,
                "exact_coordinates_stored": False,
            },
        )
        self._commit("ATTENDANCE_PUNCH_CONFLICT", "打卡写入冲突")
        return self._punch_dict(row)

    @staticmethod
    def _summary_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "employee_id": int(row.employee_id),
            "work_date": row.work_date.isoformat(),
            "scheduled_minutes": row.scheduled_minutes,
            "worked_minutes": row.worked_minutes,
            "first_in_at": row.first_in_at.isoformat() if row.first_in_at else None,
            "last_out_at": row.last_out_at.isoformat() if row.last_out_at else None,
            "status": row.status,
            "anomaly_code": row.anomaly_code,
            "adjustment_reason": row.adjustment_reason,
            "lock_version": int(row.lock_version),
        }

    def generate_summary(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:attendance_admin")
        employee = self._employee(data["employee_id"], for_update=True)
        work_date = data["work_date"]
        assignment = self.repo.active_assignment(employee.id, work_date)
        leave = self.repo.approved_leave_on(employee.id, work_date)
        punches = list(self.repo.punches_for_day(employee.id, work_date))
        first_in = next((p.punched_at for p in punches if p.punch_type == "IN"), None)
        last_out = next((p.punched_at for p in reversed(punches) if p.punch_type == "OUT"), None)
        scheduled = 0
        if assignment is not None:
            version = self.repo.get_shift_version(int(assignment.shift_version_id))
            if version is not None:
                start = datetime.combine(work_date, version.start_time)
                end = datetime.combine(
                    work_date + (timedelta(days=1) if version.cross_day else timedelta()),
                    version.end_time,
                )
                scheduled = max(
                    0, int((end - start).total_seconds() // 60) - int(version.break_minutes)
                )
        worked = (
            int((last_out - first_in).total_seconds() // 60)
            if first_in and last_out and last_out > first_in
            else 0
        )
        if leave is not None:
            status, anomaly = "LEAVE", None
        elif assignment is None:
            status, anomaly = ("NORMAL", None) if punches else ("ANOMALY", "NO_ROSTER")
        elif first_in is None and last_out is None:
            status, anomaly = "ABSENT", "NO_PUNCH"
        elif first_in is None or last_out is None:
            status, anomaly = "ANOMALY", "MISSING_IN" if first_in is None else "MISSING_OUT"
        else:
            status, anomaly = "NORMAL", None
        row = self.repo.get_summary(employee.id, work_date, for_update=True)
        if row is None:
            row = self.repo.create_summary(
                park_id=employee.park_id,
                employee_id=employee.id,
                work_date=work_date,
                scheduled_minutes=scheduled,
                worked_minutes=worked,
                first_in_at=first_in,
                last_out_at=last_out,
                status=status,
                anomaly_code=anomaly,
                lock_version=1,
            )
        else:
            (
                row.scheduled_minutes,
                row.worked_minutes,
                row.first_in_at,
                row.last_out_at,
                row.status,
                row.anomaly_code,
            ) = scheduled, worked, first_in, last_out, status, anomaly
            row.adjustment_reason, row.adjusted_by, row.lock_version = (
                None,
                None,
                int(row.lock_version) + 1,
            )
            self.repo.save(row)
        if anomaly:
            self.work_items.ensure_from_source(
                source_type="ATTENDANCE_SUMMARY",
                source_id=str(row.id),
                item_type="ATTENDANCE_ANOMALY",
                title=f"考勤异常：{employee.display_name} {work_date.isoformat()}",
                description=anomaly,
                park_id=employee.park_id,
                priority="HIGH",
                assignee_user_id=None,
                deep_link="/workforce",
                commit=False,
            )
        self.audit.record(
            action="generate",
            resource_type="ATTENDANCE_SUMMARY",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"status": status, "anomaly": anomaly},
        )
        self._commit("ATTENDANCE_SUMMARY_CONFLICT", "考勤汇总生成冲突")
        return self._summary_dict(row)

    def list_summaries(
        self, *, employee_id: int | None, date_from: date, date_to: date, status: str | None
    ) -> list[dict[str, Any]]:
        self._permission("workforce:read", "workforce:attendance_admin")
        if date_to < date_from or (date_to - date_from).days > 366:
            raise AppError("考勤查询日期范围无效", code="VALIDATION_ERROR", status_code=400)
        if employee_id is not None:
            self._employee(employee_id)
        if status:
            enum_value(status, field="status", allowed=SUMMARY_STATUSES)
        return [
            self._summary_dict(row)
            for row in self.repo.list_summaries(
                employee_id=employee_id, date_from=date_from, date_to=date_to, status=status
            )
        ]

    def adjust_summary(self, summary_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:attendance_adjust")
        row = self.repo.get_summary_by_id(summary_id, for_update=True)
        if row is None:
            raise AppError("考勤汇总不存在", code="ATTENDANCE_SUMMARY_NOT_FOUND", status_code=404)
        self._expected(row, data["expected_version"])
        prior = {
            "status": row.status,
            "worked_minutes": row.worked_minutes,
            "anomaly_code": row.anomaly_code,
        }
        requested = enum_value(data["status"], field="status", allowed=SUMMARY_STATUSES)
        row.status = "ADJUSTED" if requested != "ADJUSTED" else requested
        row.worked_minutes, row.adjustment_reason, row.adjusted_by = (
            int(data["worked_minutes"]),
            clean_text(data["reason"], field="reason", maximum=1000),
            self.ctx.user_id or None,
        )
        row.anomaly_code, row.lock_version = None, int(row.lock_version) + 1
        self.repo.save(row)
        self.audit.record(
            action="adjust",
            resource_type="ATTENDANCE_SUMMARY",
            resource_id=row.id,
            park_id=row.park_id,
            detail={
                "prior": prior,
                "requested_status": requested,
                "worked_minutes": row.worked_minutes,
                "reason": row.adjustment_reason,
            },
        )
        self._commit("ATTENDANCE_SUMMARY_CONFLICT", "考勤调整冲突")
        return self._summary_dict(row)

    # Leave approval
    @staticmethod
    def _leave_dict(row, approval=None) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "employee_id": int(row.employee_id),
            "leave_type": row.leave_type,
            "start_at": row.start_at.isoformat(),
            "end_at": row.end_at.isoformat(),
            "reason": row.reason,
            "status": row.status,
            "approval_id": row.approval_id,
            "approval_status": approval.status if approval else None,
            "lock_version": int(row.lock_version),
            "cancelled_at": row.cancelled_at.isoformat() if row.cancelled_at else None,
        }

    def list_leaves(self, status: str | None) -> list[dict[str, Any]]:
        self._permission("workforce:read", "workforce:leave_request", "workforce:leave_review")
        return [
            self._leave_dict(row, self.repo.approval(row.approval_id))
            for row in self.repo.list_leaves(status)
        ]

    def create_leave(self, data: dict[str, Any], *, key: str) -> dict[str, Any]:
        self._permission("workforce:leave_request")
        employee = self._employee(data["employee_id"])
        start, end = naive_utc(data["start_at"]), naive_utc(data["end_at"])
        definition_code = normalize_code(
            data["definition_code"], field="definition_code", maximum=64
        )
        if end <= start:
            raise AppError(
                "请假结束时间必须晚于开始时间", code="WORKFORCE_LEAVE_DATE_INVALID", status_code=400
            )
        canonical = {
            "employee_id": int(employee.id),
            "leave_type": data["leave_type"],
            "start_at": start.isoformat(),
            "end_at": end.isoformat(),
            "reason": data["reason"],
            "definition_code": definition_code,
        }
        digest = payload_hash(canonical)
        previous = self.repo.leave_by_key(key)
        if previous is not None:
            if previous.payload_hash != digest:
                raise AppError("幂等键已用于其他请假", code="IDEMPOTENCY_CONFLICT", status_code=409)
            return self._leave_dict(previous, self.repo.approval(previous.approval_id))
        row = self.repo.create_leave(
            park_id=employee.park_id,
            employee_id=employee.id,
            leave_type=data["leave_type"],
            start_at=start,
            end_at=end,
            reason=clean_text(data["reason"], field="reason", maximum=1000),
            status="PENDING_APPROVAL",
            request_key=key,
            payload_hash=digest,
            requested_by=self.ctx.user_id,
            lock_version=1,
        )
        self.session.flush()
        approval = self.approvals.create(
            {
                "biz_type": "WORKFORCE_LEAVE",
                "biz_id": str(row.id),
                "title": f"请假申请：{employee.display_name}",
                "park_id": employee.park_id,
                "definition_code": definition_code,
                "idempotency_key": f"workforce-leave:{key}",
                "priority": "MEDIUM",
                "snapshot": {
                    "employee_id": int(employee.id),
                    "leave_type": row.leave_type,
                    "start_at": start,
                    "end_at": end,
                },
            }
        )
        row.approval_id = int(approval["id"])
        self.repo.save(row)
        self.audit.record(
            action="submit",
            resource_type="WORKFORCE_LEAVE",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"employee_id": row.employee_id, "approval_id": row.approval_id},
        )
        self._commit("WORKFORCE_LEAVE_CONFLICT", "请假申请冲突")
        return self._leave_dict(row, self.repo.approval(row.approval_id))

    def refresh_leave(self, leave_id: int) -> dict[str, Any]:
        self._permission("workforce:leave_request", "workforce:leave_review")
        row = self.repo.get_leave(leave_id, for_update=True)
        if row is None:
            raise AppError("请假申请不存在", code="WORKFORCE_LEAVE_NOT_FOUND", status_code=404)
        approval = self.repo.approval(row.approval_id)
        if approval is None:
            raise AppError("请假审批关联缺失", code="APPROVAL_LINK_MISSING", status_code=409)
        status = APPROVAL_MAP.get(str(approval.status), "PENDING_APPROVAL")
        if row.status != status and row.status != "CANCELLED":
            row.status, row.lock_version = status, int(row.lock_version) + 1
            self.repo.save(row)
            self.audit.record(
                action="reconcile_approval",
                resource_type="WORKFORCE_LEAVE",
                resource_id=row.id,
                park_id=row.park_id,
                detail={"approval_status": approval.status, "status": status},
            )
            self._commit("WORKFORCE_LEAVE_CONFLICT", "请假状态同步冲突")
        return self._leave_dict(row, approval)

    def cancel_leave(self, leave_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:leave_request")
        row = self.repo.get_leave(leave_id, for_update=True)
        if row is None:
            raise AppError("请假申请不存在", code="WORKFORCE_LEAVE_NOT_FOUND", status_code=404)
        self._expected(row, data["expected_version"])
        if row.status in {"REJECTED", "CANCELLED"}:
            raise AppError(
                "当前请假状态不可取消", code="WORKFORCE_LEAVE_STATE_INVALID", status_code=409
            )
        row.status, row.cancelled_at, row.lock_version = (
            "CANCELLED",
            utc_now(),
            int(row.lock_version) + 1,
        )
        self.repo.save(row)
        self.audit.record(
            action="cancel",
            resource_type="WORKFORCE_LEAVE",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"reason": data["reason"]},
        )
        self._commit("WORKFORCE_LEAVE_CONFLICT", "请假取消冲突")
        return self._leave_dict(row, self.repo.approval(row.approval_id))

    # Performance
    @staticmethod
    def _cycle_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "code": row.code,
            "name": row.name,
            "start_date": row.start_date.isoformat(),
            "end_date": row.end_date.isoformat(),
            "status": row.status,
            "lock_version": int(row.lock_version),
        }

    def list_cycles(self, park_id: int | None) -> list[dict[str, Any]]:
        self._permission(
            "workforce:read", "workforce:performance_manage", "workforce:performance_review"
        )
        if park_id is not None:
            self._park(park_id)
        return [self._cycle_dict(row) for row in self.repo.list_cycles(park_id)]

    def create_cycle(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:performance_manage")
        park_id = self._park(data["park_id"])
        cycle_dates(data["start_date"], data["end_date"])
        row = self.repo.create_cycle(
            park_id=park_id,
            code=normalize_code(data["code"], field="code"),
            name=clean_text(data["name"], field="name", maximum=128),
            start_date=data["start_date"],
            end_date=data["end_date"],
            status="DRAFT",
            lock_version=1,
        )
        self.audit.record(
            action="create",
            resource_type="PERFORMANCE_CYCLE",
            resource_id=row.id,
            park_id=park_id,
            detail={"code": row.code},
        )
        self._commit("PERFORMANCE_CYCLE_CONFLICT", "绩效周期编码冲突")
        return self._cycle_dict(row)

    def change_cycle_status(self, cycle_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:performance_manage")
        row = self.repo.get_cycle(cycle_id, for_update=True)
        if row is None:
            raise AppError("绩效周期不存在", code="PERFORMANCE_CYCLE_NOT_FOUND", status_code=404)
        self._expected(row, data["expected_version"])
        target = data["status"]
        allowed = {"DRAFT": {"ACTIVE"}, "ACTIVE": {"CLOSED"}, "CLOSED": set()}
        if target not in allowed[row.status]:
            raise AppError(
                "绩效周期状态流转无效", code="PERFORMANCE_CYCLE_STATE_INVALID", status_code=409
            )
        row.status, row.lock_version = target, int(row.lock_version) + 1
        self.repo.save(row)
        self.audit.record(
            action="status",
            resource_type="PERFORMANCE_CYCLE",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"status": target, "reason": data["reason"]},
        )
        self._commit("PERFORMANCE_CYCLE_CONFLICT", "绩效周期更新冲突")
        return self._cycle_dict(row)

    @staticmethod
    def _goal_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "cycle_id": int(row.cycle_id),
            "employee_id": int(row.employee_id),
            "code": row.code,
            "title": row.title,
            "description": row.description,
            "weight": row.weight,
            "target_value": row.target_value,
            "status": row.status,
        }

    def list_goals(self, cycle_id: int, employee_id: int | None) -> list[dict[str, Any]]:
        self._permission(
            "workforce:read", "workforce:performance_manage", "workforce:performance_review"
        )
        if self.repo.get_cycle(cycle_id) is None:
            raise AppError("绩效周期不存在", code="PERFORMANCE_CYCLE_NOT_FOUND", status_code=404)
        if employee_id is not None:
            self._employee(employee_id)
        return [self._goal_dict(row) for row in self.repo.list_goals(cycle_id, employee_id)]

    def create_goal(self, cycle_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:performance_manage")
        cycle = self.repo.get_cycle(cycle_id, for_update=True)
        if cycle is None:
            raise AppError("绩效周期不存在", code="PERFORMANCE_CYCLE_NOT_FOUND", status_code=404)
        if cycle.status != "DRAFT":
            raise AppError(
                "仅草稿周期可维护目标", code="PERFORMANCE_CYCLE_STATE_INVALID", status_code=409
            )
        employee = self._employee(data["employee_id"])
        if employee.park_id != cycle.park_id:
            raise AppError("员工与绩效周期园区不匹配", code="PARK_SCOPE_MISMATCH", status_code=404)
        if self.repo.goal_weight(cycle.id, employee.id) + int(data["weight"]) > 100:
            raise AppError(
                "目标权重总和不得超过 100", code="PERFORMANCE_GOAL_WEIGHT_EXCEEDED", status_code=409
            )
        row = self.repo.create_goal(
            park_id=cycle.park_id,
            cycle_id=cycle.id,
            employee_id=employee.id,
            code=normalize_code(data["code"], field="code"),
            title=clean_text(data["title"], field="title", maximum=255),
            description=clean_text(
                data.get("description"), field="description", maximum=5000, required=False
            ),
            weight=data["weight"],
            target_value=clean_text(
                data.get("target_value"), field="target_value", maximum=128, required=False
            ),
            status="DRAFT",
        )
        self.audit.record(
            action="create",
            resource_type="PERFORMANCE_GOAL",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"employee_id": row.employee_id, "weight": row.weight},
        )
        self._commit("PERFORMANCE_GOAL_CONFLICT", "绩效目标冲突")
        return self._goal_dict(row)

    @staticmethod
    def _review_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "cycle_id": int(row.cycle_id),
            "employee_id": int(row.employee_id),
            "reviewer_user_id": int(row.reviewer_user_id),
            "rating": row.rating,
            "comment": row.comment,
            "status": row.status,
            "published_at": row.published_at.isoformat() if row.published_at else None,
            "acknowledged_at": row.acknowledged_at.isoformat() if row.acknowledged_at else None,
            "acknowledgement": row.acknowledgement,
            "lock_version": int(row.lock_version),
        }

    def list_reviews(self, cycle_id: int | None) -> list[dict[str, Any]]:
        self._permission("workforce:read", "workforce:performance_review")
        return [self._review_dict(row) for row in self.repo.list_reviews(cycle_id)]

    def create_review(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:performance_review")
        cycle = self.repo.get_cycle(data["cycle_id"])
        if cycle is None:
            raise AppError("绩效周期不存在", code="PERFORMANCE_CYCLE_NOT_FOUND", status_code=404)
        if cycle.status != "ACTIVE":
            raise AppError(
                "绩效周期未启用", code="PERFORMANCE_CYCLE_STATE_INVALID", status_code=409
            )
        employee = self._employee(data["employee_id"])
        if employee.park_id != cycle.park_id:
            raise AppError("员工与绩效周期园区不匹配", code="PARK_SCOPE_MISMATCH", status_code=404)
        if employee.user_id is not None and int(employee.user_id) == int(self.ctx.user_id):
            raise AppError(
                "不得评价本人", code="PERFORMANCE_SELF_REVIEW_FORBIDDEN", status_code=403
            )
        if self.repo.goal_weight(cycle.id, employee.id) != 100:
            raise AppError(
                "员工绩效目标权重必须等于 100",
                code="PERFORMANCE_GOAL_WEIGHT_INCOMPLETE",
                status_code=409,
            )
        row = self.repo.create_review(
            park_id=cycle.park_id,
            cycle_id=cycle.id,
            employee_id=employee.id,
            employee_user_id=employee.user_id,
            reviewer_user_id=self.ctx.user_id,
            rating=data["rating"],
            comment=clean_text(data["comment"], field="comment", maximum=2000),
            status="DRAFT",
            lock_version=1,
        )
        self.audit.record(
            action="create",
            resource_type="PERFORMANCE_REVIEW",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"employee_id": row.employee_id, "rating": row.rating},
        )
        self._commit("PERFORMANCE_REVIEW_CONFLICT", "员工周期评价已存在")
        return self._review_dict(row)

    def publish_review(self, review_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:performance_review")
        row = self.repo.get_review(review_id, for_update=True)
        if row is None:
            raise AppError("绩效评价不存在", code="PERFORMANCE_REVIEW_NOT_FOUND", status_code=404)
        self._expected(row, data["expected_version"])
        if row.status != "DRAFT":
            raise AppError(
                "绩效评价已发布", code="PERFORMANCE_REVIEW_STATE_INVALID", status_code=409
            )
        if row.employee_user_id is not None and int(row.employee_user_id) == int(self.ctx.user_id):
            raise AppError(
                "不得评价本人", code="PERFORMANCE_SELF_REVIEW_FORBIDDEN", status_code=403
            )
        row.status, row.published_at, row.lock_version = (
            "PUBLISHED",
            utc_now(),
            int(row.lock_version) + 1,
        )
        self.repo.save(row)
        self.audit.record(
            action="publish",
            resource_type="PERFORMANCE_REVIEW",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"reason": data["reason"], "rating": row.rating},
        )
        self._commit("PERFORMANCE_REVIEW_CONFLICT", "绩效评价发布冲突")
        return self._review_dict(row)

    def acknowledge_review(self, review_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:performance_acknowledge")
        row = self.repo.get_review(review_id, for_update=True)
        if row is None:
            raise AppError("绩效评价不存在", code="PERFORMANCE_REVIEW_NOT_FOUND", status_code=404)
        self._expected(row, data["expected_version"])
        if row.status != "PUBLISHED":
            raise AppError(
                "仅已发布评价可确认", code="PERFORMANCE_REVIEW_STATE_INVALID", status_code=409
            )
        if row.employee_user_id is None or int(row.employee_user_id) != int(self.ctx.user_id):
            raise AppError("仅被评价员工可确认", code="PERFORMANCE_ACK_FORBIDDEN", status_code=403)
        row.status, row.acknowledged_at, row.acknowledgement, row.lock_version = (
            "ACKNOWLEDGED",
            utc_now(),
            clean_text(data["acknowledgement"], field="acknowledgement", maximum=1000),
            int(row.lock_version) + 1,
        )
        self.repo.save(row)
        self.audit.record(
            action="acknowledge",
            resource_type="PERFORMANCE_REVIEW",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"acknowledgement": row.acknowledgement},
        )
        self._commit("PERFORMANCE_REVIEW_CONFLICT", "绩效评价确认冲突")
        return self._review_dict(row)

    # Qualifications
    def list_qualification_types(self, include_retired: bool) -> list[dict[str, Any]]:
        self._permission("workforce:read", "workforce:qualification_manage")
        return [
            {
                "id": int(row.id),
                "code": row.code,
                "name": row.name,
                "validity_months": row.validity_months,
                "reminder_days": row.reminder_days,
                "status": row.status,
            }
            for row in self.repo.list_qualification_types(include_retired)
        ]

    def create_qualification_type(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:qualification_manage")
        if not self.ctx.has_all_park_access:
            raise AppError("资质类型需租户级范围", code="PARK_SCOPE_DENIED", status_code=403)
        row = self.repo.create_qualification_type(
            code=normalize_code(data["code"], field="code"),
            name=clean_text(data["name"], field="name", maximum=128),
            validity_months=data.get("validity_months"),
            reminder_days=data["reminder_days"],
            status="ACTIVE",
        )
        self.audit.record(
            action="create",
            resource_type="QUALIFICATION_TYPE",
            resource_id=row.id,
            detail={"code": row.code},
        )
        self._commit("QUALIFICATION_TYPE_CONFLICT", "资质类型编码冲突")
        return {
            "id": int(row.id),
            "code": row.code,
            "name": row.name,
            "validity_months": row.validity_months,
            "reminder_days": row.reminder_days,
            "status": row.status,
        }

    def _qualification_dict(self, row, *, detail: bool = False) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        data = {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "employee_id": int(row.employee_id),
            "qualification_type_id": int(row.qualification_type_id),
            "attachment_id": int(row.attachment_id),
            "credential_masked": row.credential_masked,
            "issuer": row.issuer,
            "effective_on": row.effective_on.isoformat(),
            "expires_on": row.expires_on.isoformat() if row.expires_on else None,
            "status": row.status,
            "verified_by": row.verified_by,
            "verified_at": row.verified_at.isoformat() if row.verified_at else None,
            "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
            "revoke_reason": row.revoke_reason,
            "lock_version": int(row.lock_version),
        }
        if detail:
            data["events"] = [
                {
                    "id": int(event.id),
                    "event_type": event.event_type,
                    "reason": event.reason,
                    "actor_user_id": event.actor_user_id,
                    "occurred_at": event.occurred_at.isoformat(),
                }
                for event in self.repo.qualification_events(int(row.id))
            ]
        return data

    def list_qualifications(
        self, employee_id: int | None, status: str | None
    ) -> list[dict[str, Any]]:
        self._permission(
            "workforce:read", "workforce:qualification_manage", "workforce:qualification_verify"
        )
        if employee_id is not None:
            self._employee(employee_id)
        return [
            self._qualification_dict(row)
            for row in self.repo.list_qualifications(employee_id, status)
        ]

    def create_qualification(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:qualification_manage")
        employee = self._employee(data["employee_id"])
        qtype = self.repo.get_qualification_type(data["qualification_type_id"])
        if qtype is None or qtype.status != "ACTIVE":
            raise AppError("资质类型不存在", code="QUALIFICATION_TYPE_NOT_FOUND", status_code=404)
        attachment = self.repo.get_attachment(data["attachment_id"], employee.park_id)
        if (
            attachment is None
            or attachment.biz_type != "WORKFORCE_QUALIFICATION"
            or attachment.biz_id != str(employee.id)
        ):
            raise AppError(
                "资质附件不存在或归属不匹配",
                code="QUALIFICATION_ATTACHMENT_INVALID",
                status_code=404,
            )
        qualification_dates(data["effective_on"], data.get("expires_on"))
        masked, digest = fingerprint(data["credential_number"], pepper=self._fingerprint_secret)
        assert masked is not None and digest is not None
        row = self.repo.create_qualification(
            park_id=employee.park_id,
            employee_id=employee.id,
            qualification_type_id=qtype.id,
            attachment_id=attachment.id,
            credential_masked=masked,
            credential_fingerprint=digest,
            issuer=clean_text(data["issuer"], field="issuer", maximum=255),
            effective_on=data["effective_on"],
            expires_on=data.get("expires_on"),
            status="DRAFT",
            lock_version=1,
        )
        self.repo.create_qualification_event(
            park_id=employee.park_id,
            qualification_id=row.id,
            event_type="CREATED",
            reason="资质建档",
            actor_user_id=self.ctx.user_id or None,
            occurred_at=utc_now(),
        )
        self.audit.record(
            action="create",
            resource_type="EMPLOYEE_QUALIFICATION",
            resource_id=row.id,
            park_id=row.park_id,
            detail={
                "employee_id": row.employee_id,
                "credential_stored": "MASKED_AND_FINGERPRINT_ONLY",
            },
        )
        self._commit("QUALIFICATION_CONFLICT", "员工资质冲突")
        return self._qualification_dict(row, detail=True)

    def verify_qualification(self, qualification_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:qualification_verify")
        row = self.repo.get_qualification(qualification_id, for_update=True)
        if row is None:
            raise AppError(
                "员工资质不存在", code="EMPLOYEE_QUALIFICATION_NOT_FOUND", status_code=404
            )
        self._expected(row, data["expected_version"])
        if row.status != "DRAFT":
            raise AppError("仅草稿资质可核验", code="QUALIFICATION_STATE_INVALID", status_code=409)
        row.status, row.verified_by, row.verified_at, row.lock_version = (
            "VERIFIED",
            self.ctx.user_id or None,
            utc_now(),
            int(row.lock_version) + 1,
        )
        self.repo.save(row)
        reason = clean_text(data["reason"], field="reason", maximum=1000)
        self.repo.create_qualification_event(
            park_id=row.park_id,
            qualification_id=row.id,
            event_type="VERIFIED",
            reason=reason,
            actor_user_id=self.ctx.user_id or None,
            occurred_at=utc_now(),
        )
        self.audit.record(
            action="verify",
            resource_type="EMPLOYEE_QUALIFICATION",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"reason": reason},
        )
        self._commit("QUALIFICATION_CONFLICT", "员工资质核验冲突")
        return self._qualification_dict(row, detail=True)

    def revoke_qualification(self, qualification_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("workforce:qualification_verify")
        row = self.repo.get_qualification(qualification_id, for_update=True)
        if row is None:
            raise AppError(
                "员工资质不存在", code="EMPLOYEE_QUALIFICATION_NOT_FOUND", status_code=404
            )
        self._expected(row, data["expected_version"])
        if row.status not in {"VERIFIED", "EXPIRED"}:
            raise AppError(
                "当前资质状态不可撤销", code="QUALIFICATION_STATE_INVALID", status_code=409
            )
        reason = clean_text(data["reason"], field="reason", maximum=1000)
        row.status, row.revoked_by, row.revoked_at, row.revoke_reason, row.lock_version = (
            "REVOKED",
            self.ctx.user_id or None,
            utc_now(),
            reason,
            int(row.lock_version) + 1,
        )
        self.repo.save(row)
        self.repo.create_qualification_event(
            park_id=row.park_id,
            qualification_id=row.id,
            event_type="REVOKED",
            reason=reason,
            actor_user_id=self.ctx.user_id or None,
            occurred_at=utc_now(),
        )
        self.audit.record(
            action="revoke",
            resource_type="EMPLOYEE_QUALIFICATION",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"reason": reason},
        )
        self._commit("QUALIFICATION_CONFLICT", "员工资质撤销冲突")
        return self._qualification_dict(row, detail=True)

    def sweep_qualifications(self, due_on: date) -> dict[str, Any]:
        self._permission("workforce:qualification_verify")
        items = list(self.repo.due_qualifications(due_on))
        for row in items:
            row.status, row.lock_version = "EXPIRED", int(row.lock_version) + 1
            self.repo.save(row)
            self.repo.create_qualification_event(
                park_id=row.park_id,
                qualification_id=row.id,
                event_type="EXPIRED",
                reason=f"到期扫描 {due_on.isoformat()}",
                actor_user_id=self.ctx.user_id or None,
                occurred_at=utc_now(),
            )
            employee = self._employee(row.employee_id)
            self.work_items.ensure_from_source(
                source_type="EMPLOYEE_QUALIFICATION",
                source_id=str(row.id),
                item_type="QUALIFICATION_EXPIRED",
                title=f"员工资质已到期：{employee.display_name}",
                description=f"到期日 {row.expires_on}",
                park_id=row.park_id,
                priority="HIGH",
                assignee_user_id=employee.user_id,
                deep_link="/workforce",
                commit=False,
            )
            self.audit.record(
                action="expire",
                resource_type="EMPLOYEE_QUALIFICATION",
                resource_id=row.id,
                park_id=row.park_id,
                detail={"due_on": due_on},
            )
        self._commit("QUALIFICATION_SWEEP_CONFLICT", "资质到期扫描冲突")
        return {
            "due_on": due_on.isoformat(),
            "expired": len(items),
            "qualification_ids": [int(row.id) for row in items],
        }

    def overview(self) -> dict[str, Any]:
        self._permission("workforce:read")
        today = utc_now().date()
        employees = self.repo.count_employees(park_id=None, status="ACTIVE", keyword=None)
        anomalies = len(
            self.repo.list_summaries(
                employee_id=None, date_from=today, date_to=today, status="ANOMALY"
            )
        )
        leaves = len(self.repo.list_leaves("APPROVED"))
        due = len(self.repo.due_qualifications(today + timedelta(days=30)))
        return {
            "active_employees": employees,
            "today_anomalies": anomalies,
            "approved_leave_records": leaves,
            "qualifications_due_30d": due,
            "device_integration": {"status": "NOT_CONNECTED", "production_contacted": False},
            "payroll_engine": {"status": "NOT_IMPLEMENTED", "summary_ready": True},
        }

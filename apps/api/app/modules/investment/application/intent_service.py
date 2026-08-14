"""Versioned lead intent applications backed by the shared approval engine."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.modules.investment.domain.entities import IntentSnapshot, IntentUnitSnapshot
from app.modules.investment.domain.rules import validate_intent_snapshot
from app.modules.investment.infrastructure.completion_repository import IntentRepository
from app.modules.investment.infrastructure.lead_repository import LeadRepository
from app.modules.park_property.infrastructure.unit_repository import UnitRepository
from app.modules.workflow.application.approval_service import ApprovalService
from app.shared.tenant_context import TenantContext


class IntentService:
    """Own immutable commercial snapshots while Approval remains the decision authority."""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.intents = IntentRepository(session, ctx)
        self.leads = LeadRepository(session, ctx)
        self.units = UnitRepository(session, ctx)
        self.approvals = ApprovalService(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def _require_permission(self, permission: str) -> None:
        if not self.ctx.has_permission(permission):
            raise AppError("无意向申请权限", code="PERMISSION_DENIED", status_code=403)

    def _lead(self, lead_id: int, *, for_update: bool = False):
        row = self.leads.get_by_id(lead_id, for_update=for_update)
        if row is None:
            raise AppError("线索不存在", code="LEAD_NOT_FOUND", status_code=404)
        return row

    def _assert_write(self, lead) -> None:
        self._require_permission("lead.intent.write")
        if self.ctx.has_permission("lead:manage"):
            return
        if int(lead.owner_user_id or 0) != int(self.ctx.user_id or 0):
            raise AppError("只能维护本人负责线索的意向", code="PERMISSION_DENIED", status_code=403)

    @staticmethod
    def _parse_date(value: Any, field: str) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError as exc:
                raise AppError(f"{field} 无效", code="VALIDATION_ERROR", status_code=400) from exc
        raise AppError(f"{field} 无效", code="VALIDATION_ERROR", status_code=400)

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

    def _snapshot(self, *, park_id: int, data: dict[str, Any]) -> IntentSnapshot:
        raw_units = data.get("units")
        if not isinstance(raw_units, list):
            raise AppError("units 必须为数组", code="VALIDATION_ERROR", status_code=400)
        try:
            requested = {
                int(item["unit_id"]): Decimal(str(item["requested_area"]))
                for item in raw_units
                if isinstance(item, dict)
            }
            price = Decimal(str(data.get("proposed_unit_price")))
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise AppError("意向单元或价格无效", code="VALIDATION_ERROR", status_code=400) from exc
        if len(requested) != len(raw_units):
            raise AppError("意向单元重复或格式无效", code="VALIDATION_ERROR", status_code=400)
        unit_rows = self.units.get_currents_for_update(sorted(requested))
        if len(unit_rows) != len(requested):
            raise AppError("意向单元不存在或已失效", code="INTENT_UNIT_INVALID", status_code=409)
        snapshots: list[IntentUnitSnapshot] = []
        for unit in unit_rows:
            if int(unit.park_id) != int(park_id):
                raise AppError("意向单元与线索园区不一致", code="INTENT_UNIT_PARK_INVALID", status_code=409)
            area = requested[int(unit.id)]
            if area > Decimal(str(unit.rentable_area)):
                raise AppError("意向面积超过单元可租面积", code="INTENT_AREA_INVALID", status_code=409)
            snapshots.append(
                IntentUnitSnapshot(
                    unit_id=int(unit.id),
                    unit_version=int(unit.version_no),
                    requested_area=area,
                )
            )
        snapshot = IntentSnapshot(
            starts_on=self._parse_date(data.get("starts_on"), "starts_on"),
            ends_on=self._parse_date(data.get("ends_on"), "ends_on"),
            valid_until=self._parse_datetime(data.get("valid_until"), "valid_until"),
            proposed_unit_price=price,
            currency=str(data.get("currency") or "CNY").strip().upper(),
            units=tuple(snapshots),
            remark=(str(data.get("remark") or "").strip() or None),
        )
        try:
            return validate_intent_snapshot(snapshot)
        except ValueError as exc:
            raise AppError(str(exc), code="VALIDATION_ERROR", status_code=400) from exc

    @staticmethod
    def _snapshot_payload(snapshot: IntentSnapshot) -> dict[str, Any]:
        return {
            "starts_on": snapshot.starts_on.isoformat(),
            "ends_on": snapshot.ends_on.isoformat(),
            "valid_until": snapshot.valid_until.isoformat(),
            "proposed_unit_price": str(snapshot.proposed_unit_price),
            "currency": snapshot.currency,
            "remark": snapshot.remark,
            "units": [
                {
                    "unit_id": unit.unit_id,
                    "unit_version": unit.unit_version,
                    "requested_area": str(unit.requested_area),
                }
                for unit in snapshot.units
            ],
        }

    @classmethod
    def _checksum(cls, snapshot: IntentSnapshot) -> str:
        canonical = json.dumps(
            cls._snapshot_payload(snapshot), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _authoritative_status(self, application) -> str:
        if application.approval_request_id is None:
            return application.status
        approval = self.intents.approval(int(application.approval_request_id))
        if approval is None:
            return "WITHDRAWN"
        return str(approval.status)

    def _version_dict(self, row) -> dict[str, Any]:
        return {
            "id": int(row.id),
            "version": int(row.version),
            "starts_on": row.starts_on.isoformat(),
            "ends_on": row.ends_on.isoformat(),
            "valid_until": row.valid_until.isoformat(),
            "proposed_unit_price": str(row.proposed_unit_price),
            "currency": row.currency,
            "remark": row.remark,
            "checksum": row.checksum,
            "units": [
                {
                    "unit_id": int(unit.unit_id),
                    "unit_version": int(unit.unit_version),
                    "requested_area": str(unit.requested_area),
                }
                for unit in self.intents.units(int(row.id))
            ],
        }

    def _to_dict(self, application, *, include_versions: bool = True) -> dict[str, Any]:
        status = self._authoritative_status(application)
        result: dict[str, Any] = {
            "id": int(application.id),
            "park_id": int(application.park_id),
            "lead_id": int(application.lead_id),
            "status": status,
            "current_version": int(application.current_version),
            "approval_request_id": application.approval_request_id,
            "approval_deep_link": (
                f"/approvals/{int(application.approval_request_id)}"
                if application.approval_request_id
                else None
            ),
            "submitted_at": application.submitted_at.isoformat() if application.submitted_at else None,
            "lock_version": int(application.lock_version),
        }
        if include_versions:
            result["versions"] = [
                self._version_dict(row) for row in self.intents.versions(int(application.id))
            ]
        return result

    def get_for_lead(self, lead_id: int) -> dict[str, Any] | None:
        self._require_permission("lead.intent.read")
        self._lead(lead_id)
        row = self.intents.get_for_lead(lead_id)
        return self._to_dict(row) if row is not None else None

    def get(self, intent_id: int) -> dict[str, Any]:
        self._require_permission("lead.intent.read")
        row = self.intents.get(intent_id)
        if row is None:
            raise AppError("意向申请不存在", code="INTENT_NOT_FOUND", status_code=404)
        self._lead(int(row.lead_id))
        return self._to_dict(row)

    def _persist_version(self, application, snapshot: IntentSnapshot, *, version: int):
        row = self.intents.create_version(
            application_id=int(application.id),
            version=version,
            starts_on=snapshot.starts_on,
            ends_on=snapshot.ends_on,
            valid_until=snapshot.valid_until,
            proposed_unit_price=snapshot.proposed_unit_price,
            currency=snapshot.currency,
            remark=snapshot.remark,
            checksum=self._checksum(snapshot),
            created_by=self.ctx.user_id or None,
        )
        for unit in snapshot.units:
            self.intents.create_unit(
                intent_version_id=int(row.id),
                unit_id=unit.unit_id,
                unit_version=unit.unit_version,
                requested_area=unit.requested_area,
            )
        return row

    def create(self, lead_id: int, data: dict[str, Any]) -> dict[str, Any]:
        lead = self._lead(lead_id, for_update=True)
        self._assert_write(lead)
        if self.intents.get_for_lead(lead_id) is not None:
            raise AppError("线索已存在意向申请", code="INTENT_ALREADY_EXISTS", status_code=409)
        snapshot = self._snapshot(park_id=int(lead.park_id), data=data)
        application = self.intents.create_application(
            park_id=int(lead.park_id),
            lead_id=int(lead.id),
            status="DRAFT",
            current_version=1,
            lock_version=1,
            created_by=self.ctx.user_id or None,
            updated_by=self.ctx.user_id or None,
        )
        self._persist_version(application, snapshot, version=1)
        self.audit.record(
            action="create",
            resource_type="LEAD_INTENT",
            resource_id=application.id,
            park_id=application.park_id,
            detail={"lead_id": int(lead.id), "checksum": self._checksum(snapshot)},
        )
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError("意向申请并发冲突", code="INTENT_CONFLICT", status_code=409) from exc
        return self._to_dict(application)

    def create_version(self, intent_id: int, data: dict[str, Any]) -> dict[str, Any]:
        application = self.intents.get(intent_id, for_update=True)
        if application is None:
            raise AppError("意向申请不存在", code="INTENT_NOT_FOUND", status_code=404)
        lead = self._lead(int(application.lead_id), for_update=True)
        self._assert_write(lead)
        if int(application.lock_version) != int(data.get("expected_version") or 0):
            raise AppError("意向申请版本冲突", code="VERSION_CONFLICT", status_code=409)
        if self._authoritative_status(application) != "DRAFT":
            raise AppError("仅草稿意向可新增版本", code="INTENT_STATUS_INVALID", status_code=409)
        snapshot = self._snapshot(park_id=int(application.park_id), data=data)
        version = int(application.current_version) + 1
        self._persist_version(application, snapshot, version=version)
        application.current_version = version
        application.lock_version += 1
        application.updated_by = self.ctx.user_id or None
        self.intents.save(application)
        self.audit.record(
            action="create_version",
            resource_type="LEAD_INTENT",
            resource_id=application.id,
            park_id=application.park_id,
            detail={"version": version, "checksum": self._checksum(snapshot)},
        )
        self.session.commit()
        return self._to_dict(application)

    def submit(self, intent_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._require_permission("lead.intent.submit")
        application = self.intents.get(intent_id, for_update=True)
        if application is None:
            raise AppError("意向申请不存在", code="INTENT_NOT_FOUND", status_code=404)
        lead = self._lead(int(application.lead_id), for_update=True)
        self._assert_write(lead)
        if int(application.lock_version) != int(data.get("expected_version") or 0):
            raise AppError("意向申请版本冲突", code="VERSION_CONFLICT", status_code=409)
        if application.approval_request_id is not None:
            return self._to_dict(application)
        if application.status != "DRAFT":
            raise AppError("当前意向不可提交", code="INTENT_STATUS_INVALID", status_code=409)
        version = self.intents.version(int(application.id), int(application.current_version))
        if version is None:
            raise AppError("意向版本不存在", code="INTENT_VERSION_NOT_FOUND", status_code=409)
        snapshot = self._version_dict(version)
        approval = self.approvals.create(
            {
                "biz_type": "LEAD_INTENT",
                "biz_id": str(application.id),
                "title": f"招商意向审批：{str(lead.name)[:120]}",
                "definition_code": str(data.get("definition_code") or "").strip(),
                "idempotency_key": str(data.get("idempotency_key") or "").strip(),
                "park_id": int(application.park_id),
                "priority": str(data.get("priority") or "HIGH").upper(),
                "remark": str(data.get("remark") or "").strip() or None,
                "snapshot": {
                    "intent_id": int(application.id),
                    "intent_version_id": int(version.id),
                    "version": int(version.version),
                    "checksum": version.checksum,
                    "starts_on": snapshot["starts_on"],
                    "ends_on": snapshot["ends_on"],
                    "valid_until": snapshot["valid_until"],
                    "proposed_unit_price": snapshot["proposed_unit_price"],
                    "currency": snapshot["currency"],
                    "units": snapshot["units"],
                },
            }
        )
        application.approval_request_id = int(approval["id"])
        application.status = "PENDING"
        application.submitted_at = utc_now()
        application.lock_version += 1
        application.updated_by = self.ctx.user_id or None
        self.intents.save(application)
        self.audit.record(
            action="submit",
            resource_type="LEAD_INTENT",
            resource_id=application.id,
            park_id=application.park_id,
            detail={"approval_request_id": int(approval["id"]), "version": int(version.version)},
        )
        self.session.commit()
        return self._to_dict(application)

    def assert_approved_for_unit(self, *, intent_id: int, lead_id: int, unit_id: int):
        application = self.intents.get(intent_id, for_update=True)
        if application is None or int(application.lead_id) != int(lead_id):
            raise AppError("意向申请与线索不匹配", code="INTENT_LOCK_GATE_DENIED", status_code=409)
        approval = (
            self.intents.approval(int(application.approval_request_id))
            if application.approval_request_id is not None
            else None
        )
        if approval is None or approval.status != "APPROVED":
            raise AppError("意向尚未批准", code="INTENT_LOCK_GATE_DENIED", status_code=409)
        version = self.intents.version(int(application.id), int(application.current_version))
        if version is None or version.valid_until <= utc_now():
            raise AppError("已批准意向已过期", code="INTENT_EXPIRED", status_code=409)
        unit = self.units.get_current_for_update(unit_id)
        if unit is None or int(unit.park_id) != int(application.park_id):
            raise AppError("目标单元不存在或已失效", code="INTENT_UNIT_STALE", status_code=409)
        approved_unit = next(
            (item for item in self.intents.units(int(version.id)) if int(item.unit_id) == int(unit_id)),
            None,
        )
        if approved_unit is None or int(approved_unit.unit_version) != int(unit.version_no):
            raise AppError("目标单元不在当前批准意向或版本已变化", code="INTENT_UNIT_STALE", status_code=409)
        return application, version

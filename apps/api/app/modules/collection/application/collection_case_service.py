"""功能说明：催缴案件最小实现（过程记录）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.modules.billing.domain.rules import collectible_open_amount, effective_due_date
from app.modules.billing.infrastructure.bill_repository import BillRepository
from app.modules.collection.infrastructure.collection_case_repository import (
    CollectionCaseRepository,
)
from app.modules.collection.infrastructure.receivables_repository import ReceivablesRepository
from app.modules.park_property.infrastructure.park_repository import ParkRepository
from app.modules.party.infrastructure.party_repository import PartyRepository
from app.shared.tenant_context import TenantContext


class CollectionCaseService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.cases = CollectionCaseRepository(session, ctx)
        self.parks = ParkRepository(session, ctx)
        self.parties = PartyRepository(session, ctx)
        self.bills = BillRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)
        self.receivables = ReceivablesRepository(session, ctx)

    def _to_dict(self, m) -> dict[str, Any]:
        return {
            "id": m.id,
            "park_id": m.park_id,
            "party_id": m.party_id,
            "bill_id": m.bill_id,
            "status": m.status,
            "active_bill_key": m.active_bill_key,
            "level": m.level,
            "assignee_user_id": m.assignee_user_id,
            "amount_snapshot": str(m.amount_snapshot),
            "overdue_days": m.overdue_days,
            "effective_due_date": m.effective_due_date.isoformat()
            if m.effective_due_date
            else None,
            "strategy_code": m.strategy_code,
            "next_action_at": m.next_action_at.isoformat() if m.next_action_at else None,
            "last_contact_at": m.last_contact_at.isoformat() if m.last_contact_at else None,
            "resolution_code": m.resolution_code,
            "closed_at": m.closed_at.isoformat() if m.closed_at else None,
            "lock_version": m.lock_version,
            "remark": m.remark,
        }

    def list_cases(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        park_id: int | None = None,
        bill_id: int | None = None,
    ) -> dict[str, Any]:
        if not self.ctx.has_permission("collection:read"):
            raise AppError("无催缴查看权限", code="PERMISSION_DENIED", status_code=403)
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        items = self.cases.list(
            offset=(page - 1) * page_size,
            limit=page_size,
            status=status,
            park_id=park_id,
            bill_id=bill_id,
        )
        total = self.cases.count(status=status, park_id=park_id, bill_id=bill_id)
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [self._to_dict(i) for i in items],
        }

    def create_case(self, data: dict[str, Any]) -> dict[str, Any]:
        if not self.ctx.has_permission("collection:write"):
            raise AppError("无催缴维护权限", code="PERMISSION_DENIED", status_code=403)
        park_id = int(data["park_id"])
        party_id = int(data["party_id"])
        bill_id = int(data["bill_id"])
        if not self.parks.exists_in_tenant(park_id):
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        if not self.ctx.allows_park(park_id):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        if self.parties.get_by_id(party_id) is None:
            raise AppError("主体不存在", code="PARTY_NOT_FOUND", status_code=404)
        bill = self.bills.get_by_id(bill_id)
        if bill is None:
            raise AppError("账单不存在", code="BILL_NOT_FOUND", status_code=404)
        if int(bill.park_id) != park_id or int(bill.party_id) != party_id:
            raise AppError(
                "账单与园区/主体不一致", code="COLLECTION_BILL_MISMATCH", status_code=400
            )
        try:
            amount_snapshot = collectible_open_amount(
                bill.total_amount, bill.paid_amount, bill.waiver_amount, bill.bad_debt_amount
            )
        except ValueError as exc:
            raise AppError(str(exc), code="BILL_RECEIVABLE_INVALID", status_code=409) from exc
        if amount_snapshot <= 0 or bill.status not in {"ISSUED", "PARTIALLY_PAID"}:
            raise AppError("账单无可催收余额", code="COLLECTION_BILL_NOT_OPEN", status_code=409)
        if self.receivables.active_cases_for_bill(bill_id, for_update=True):
            raise AppError(
                "账单已有活动催缴案件", code="COLLECTION_CASE_DUPLICATE", status_code=409
            )
        try:
            model = self.cases.create(
                park_id=park_id,
                party_id=party_id,
                bill_id=bill_id,
                level=str(data.get("level") or "L1"),
                assignee_user_id=int(data["assignee_id"])
                if data.get("assignee_id") is not None
                else None,
                remark=data.get("remark"),
            )
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(
                "账单已有活动催缴案件",
                code="COLLECTION_CASE_DUPLICATE",
                status_code=409,
            ) from exc
        model.active_bill_key = str(bill_id)
        model.amount_snapshot = amount_snapshot
        model.effective_due_date = effective_due_date(bill.due_date, bill.deferred_due_date)
        model.strategy_code = "MANUAL"
        model.lock_version = 1
        self.audit.record(
            action="create",
            resource_type="COLLECTION_CASE",
            resource_id=model.id,
            park_id=park_id,
            detail={"bill_id": bill_id},
        )
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(
                "账单已有活动催缴案件",
                code="COLLECTION_CASE_DUPLICATE",
                status_code=409,
            ) from exc
        return self._to_dict(model)

    def get_case(self, case_id: int) -> dict[str, Any]:
        if not self.ctx.has_permission("collection:read"):
            raise AppError("无催缴查看权限", code="PERMISSION_DENIED", status_code=403)
        model = self.cases.get_by_id(case_id)
        if model is None:
            raise AppError("催缴案件不存在", code="COLLECTION_CASE_NOT_FOUND", status_code=404)
        return self._to_dict(model)

    def update_case(self, case_id: int, data: dict[str, Any]) -> dict[str, Any]:
        if not self.ctx.has_permission("collection:write"):
            raise AppError("无催缴维护权限", code="PERMISSION_DENIED", status_code=403)
        model = self.cases.get_by_id(case_id, for_update=True)
        if model is None:
            raise AppError("催缴案件不存在", code="COLLECTION_CASE_NOT_FOUND", status_code=404)
        if int(model.lock_version or 1) != int(data["expected_version"]):
            raise AppError(
                "催缴案件版本冲突",
                code="COLLECTION_CASE_VERSION_CONFLICT",
                status_code=409,
            )
        if data.get("status"):
            status = str(data["status"]).strip().upper()
            if status not in {"OPEN", "PAUSED", "CLOSED"}:
                raise AppError("催缴状态无效", code="VALIDATION_ERROR", status_code=400)
            model.status = status
            if status == "CLOSED":
                model.active_bill_key = None
                model.closed_at = utc_now()
                model.resolution_code = str(data.get("resolution_code") or "MANUAL_CLOSE")
            else:
                model.active_bill_key = str(model.bill_id)
                model.closed_at = None
                model.resolution_code = None
        if data.get("level"):
            model.level = str(data["level"])
        if "assignee_id" in data:
            model.assignee_user_id = (
                int(data["assignee_id"]) if data["assignee_id"] is not None else None
            )
        if "remark" in data:
            model.remark = data.get("remark")
        model.lock_version = int(model.lock_version or 1) + 1
        self.cases.save(model)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(
                "账单已有活动催缴案件",
                code="COLLECTION_CASE_DUPLICATE",
                status_code=409,
            ) from exc
        return self._to_dict(model)

    def list_records(self, case_id: int) -> list[dict[str, Any]]:
        if not self.ctx.has_permission("collection:read"):
            raise AppError("无催缴查看权限", code="PERMISSION_DENIED", status_code=403)
        if self.receivables.case(case_id) is None:
            raise AppError("催缴案件不存在", code="COLLECTION_CASE_NOT_FOUND", status_code=404)
        return [
            {
                "id": int(row.id),
                "case_id": int(row.case_id),
                "action_type": row.action_type,
                "status": row.status,
                "channel": row.channel,
                "note": row.note,
                "source_ref": row.source_ref,
                "external_ref": row.external_ref,
                "next_follow_up_at": row.next_follow_up_at.isoformat()
                if row.next_follow_up_at
                else None,
                "created_at": row.created_at.isoformat(),
            }
            for row in self.receivables.records(case_id)
        ]

    def add_record(self, case_id: int, data: dict[str, Any]) -> dict[str, Any]:
        if not self.ctx.has_permission("collection:write"):
            raise AppError("无催缴维护权限", code="PERMISSION_DENIED", status_code=403)
        case = self.receivables.case(case_id, for_update=True)
        if case is None:
            raise AppError("催缴案件不存在", code="COLLECTION_CASE_NOT_FOUND", status_code=404)
        action = str(data.get("action_type") or "").strip().upper()
        if action not in {"CALL", "VISIT", "SMS", "WECHAT", "EMAIL", "NOTICE", "NOTE"}:
            raise AppError("催缴动作无效", code="VALIDATION_ERROR", status_code=400)
        channel = str(data.get("channel") or action).strip().upper()
        status = "NOT_CONFIGURED" if action in {"SMS", "WECHAT", "EMAIL"} else "COMPLETED"
        follow_up = data.get("next_follow_up_at")
        try:
            next_follow_up = (
                datetime.fromisoformat(str(follow_up).replace("Z", "+00:00")).replace(tzinfo=None)
                if follow_up
                else None
            )
        except ValueError as exc:
            raise AppError(
                "next_follow_up_at 无效", code="VALIDATION_ERROR", status_code=400
            ) from exc
        row = self.receivables.create_record(
            case_id=int(case.id),
            action_type=action,
            status=status,
            channel=channel,
            note=str(data.get("note") or "").strip() or None,
            source_ref=str(data.get("source_ref") or "").strip() or None,
            external_ref=None,
            next_follow_up_at=next_follow_up,
            created_by=self.ctx.user_id,
            created_at=utc_now(),
        )
        case.last_contact_at = utc_now()
        case.next_action_at = next_follow_up
        case.lock_version = int(case.lock_version or 1) + 1
        self.audit.record(
            action="add_record",
            resource_type="COLLECTION_CASE",
            resource_id=case.id,
            park_id=case.park_id,
            detail={"action_type": action, "status": status},
        )
        self.session.commit()
        records = self.list_records(case_id)
        return next(item for item in records if item["id"] == int(row.id))

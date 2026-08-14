"""Deterministic current Lease schedule to issued Bill orchestration."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.infrastructure.platform.idempotency import (
    begin_idempotent,
    complete_idempotent,
    normalize_idempotency_key,
    request_hash,
)
from app.infrastructure.platform.number_sequence import next_number
from app.modules.billing.domain.entities import BillEntity, BillLineEntity
from app.modules.billing.domain.rules import FEE_CODES, money
from app.modules.billing.infrastructure.bill_repository import BillLineRepository, BillRepository
from app.modules.billing.infrastructure.mappers import BillLineMapper, BillMapper
from app.modules.billing.infrastructure.schedule_billing_repository import (
    ScheduleBillingRepository,
)
from app.modules.workbench.application.automation_service import WorkbenchAutomationService
from app.modules.workbench.application.work_item_service import WorkItemService
from app.shared.tenant_context import TenantContext


class ScheduleBillingService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.schedules = ScheduleBillingRepository(session, ctx)
        self.bills = BillRepository(session, ctx)
        self.lines = BillLineRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)
        self.work_items = WorkItemService(session, ctx)
        self.events = WorkbenchAutomationService(session, ctx)

    @staticmethod
    def _date(value: str | date) -> date:
        try:
            return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])
        except ValueError as exc:
            raise AppError("as_of 无效", code="VALIDATION_ERROR", status_code=400) from exc

    @staticmethod
    def _key(row, contract) -> tuple:
        return (
            int(contract.id),
            int(contract.park_id),
            int(contract.party_id),
            int(row.contract_version_no),
            row.period_start,
            row.period_end,
            row.due_date,
            row.currency,
        )

    def _plan(self, *, as_of: date, park_id: int | None, for_update: bool) -> dict[str, Any]:
        groups: dict[tuple, list[tuple[Any, Any]]] = defaultdict(list)
        conflicts: list[dict[str, Any]] = []
        eligible = self.schedules.eligible(as_of=as_of, park_id=park_id, for_update=for_update)
        overlaps = self.schedules.billed_overlaps([schedule for schedule, _ in eligible])
        for schedule, contract in eligible:
            overlap = overlaps.get(
                (
                    int(schedule.contract_id),
                    str(schedule.charge_code),
                    schedule.period_start,
                    schedule.period_end,
                )
            )
            if overlap is not None:
                conflicts.append(
                    {
                        "schedule_id": int(schedule.id),
                        "billed_schedule_id": int(overlap.id),
                        "bill_id": int(overlap.bill_id),
                        "code": "BILLED_PERIOD_VERSION_CONFLICT",
                    }
                )
                continue
            groups[self._key(schedule, contract)].append((schedule, contract))
        planned: list[dict[str, Any]] = []
        for key, rows in groups.items():
            contract = rows[0][1]
            schedules = [item[0] for item in rows]
            planned.append(
                {
                    "group_key": (
                        f"{key[0]}:v{key[3]}:{key[4].isoformat()}:{key[5].isoformat()}:"
                        f"{key[6].isoformat()}:{key[7]}"
                    ),
                    "contract_id": key[0],
                    "contract_no": contract.contract_no,
                    "park_id": key[1],
                    "party_id": key[2],
                    "contract_version_no": key[3],
                    "period_start": key[4].isoformat(),
                    "period_end": key[5].isoformat(),
                    "due_date": key[6].isoformat(),
                    "currency": key[7],
                    "total_amount": str(
                        money(sum(Decimal(str(x.gross_amount)) for x in schedules))
                    ),
                    "schedule_ids": [int(x.id) for x in schedules],
                    "rows": rows,
                }
            )
        planned.sort(key=lambda row: row["group_key"])
        return {"groups": planned, "conflicts": conflicts}

    @staticmethod
    def _public_plan(plan: dict[str, Any]) -> dict[str, Any]:
        groups = [
            {key: value for key, value in row.items() if key != "rows"} for row in plan["groups"]
        ]
        return {
            "group_count": len(groups),
            "schedule_count": sum(len(row["schedule_ids"]) for row in groups),
            "total_amount": str(money(sum(Decimal(row["total_amount"]) for row in groups))),
            "groups": groups,
            "conflicts": plan["conflicts"],
        }

    def preview(self, *, as_of: str | date, park_id: int | None) -> dict[str, Any]:
        if not self.ctx.has_permission("bill:read"):
            raise AppError("无账单查看权限", code="PERMISSION_DENIED", status_code=403)
        if park_id is not None and not self.ctx.allows_park(int(park_id)):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        plan = self._plan(as_of=self._date(as_of), park_id=park_id, for_update=False)
        return {"mode": "PREVIEW", **self._public_plan(plan)}

    def apply(
        self, *, as_of: str | date, park_id: int | None, idempotency_key: str | None
    ) -> dict[str, Any]:
        if not self.ctx.has_permission("bill:generate"):
            raise AppError("无自动出账权限", code="PERMISSION_DENIED", status_code=403)
        if park_id is not None and not self.ctx.allows_park(int(park_id)):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        day = self._date(as_of)
        idem_key = normalize_idempotency_key(idempotency_key)
        if not idem_key:
            raise AppError("Idempotency-Key 必填", code="IDEMPOTENCY_KEY_REQUIRED", status_code=400)
        body_hash = request_hash({"as_of": day.isoformat(), "park_id": park_id})
        cached = begin_idempotent(
            self.session,
            tenant_id=self.ctx.tenant_id,
            user_id=self.ctx.user_id,
            operation="billing.schedule.apply",
            idem_key=idem_key,
            body_hash=body_hash,
        )
        if cached is not None:
            if any(
                not self.ctx.allows_park(int(row["park_id"])) for row in cached.get("bills", [])
            ):
                raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
            return cached
        plan = self._plan(as_of=day, park_id=park_id, for_update=True)
        now = utc_now()
        created: list[dict[str, Any]] = []
        try:
            for group in plan["groups"]:
                sequence = next_number(
                    self.session,
                    tenant_id=self.ctx.tenant_id,
                    biz_type="BILL",
                    period_key=group["period_start"][:7].replace("-", ""),
                )
                bill_no = f"B{group['period_start'][:7].replace('-', '')}{sequence:04d}"
                model = BillMapper.new_model(
                    BillEntity(
                        tenant_id=self.ctx.tenant_id,
                        park_id=group["park_id"],
                        party_id=group["party_id"],
                        contract_id=group["contract_id"],
                        bill_no=bill_no,
                        title=f"{group['contract_no']} {group['period_start']} 应收",
                        period_start=date.fromisoformat(group["period_start"]),
                        period_end=date.fromisoformat(group["period_end"]),
                        due_date=date.fromisoformat(group["due_date"]),
                        status="ISSUED",
                        total_amount=Decimal(group["total_amount"]),
                        source="LEASE_SCHEDULE",
                        source_ref=group["group_key"],
                        issued_at=now,
                        created_by=self.ctx.user_id,
                    )
                )
                self.bills.add(model)
                for index, (schedule, _) in enumerate(group["rows"]):
                    normalized = str(schedule.charge_code).strip().upper()
                    fee_code = normalized if normalized in FEE_CODES else "OTHER"
                    self.lines.add(
                        BillLineMapper.new_model(
                            BillLineEntity(
                                tenant_id=self.ctx.tenant_id,
                                bill_id=int(model.id),
                                fee_code=fee_code,
                                source_schedule_id=int(schedule.id),
                                description=f"合同计划 {schedule.charge_code}",
                                quantity=Decimal(1),
                                unit_price=Decimal(str(schedule.gross_amount)),
                                amount=Decimal(str(schedule.gross_amount)),
                                sort_order=index,
                            )
                        )
                    )
                    self.schedules.mark_billed(schedule, bill_id=int(model.id), billed_at=now)
                self.work_items.ensure_from_source(
                    source_type="BILL",
                    source_id=str(model.id),
                    item_type="BILL_UNPAID",
                    title=f"账单待收款 {bill_no}",
                    park_id=int(model.park_id),
                    priority="HIGH",
                    due_at=datetime.combine(model.due_date, datetime.min.time()).isoformat(),
                    commit=False,
                )
                self.events.emit_event(
                    event_type="BILL_ISSUED",
                    source_type="BILL",
                    source_id=str(model.id),
                    idempotency_key=f"schedule-bill-issued:{model.id}",
                    park_id=int(model.park_id),
                    payload={
                        "title": f"自动账单已签发 {bill_no}",
                        "amount": str(model.total_amount),
                        "deep_link": "/bills",
                        "park_id": int(model.park_id),
                    },
                    commit=False,
                    enforce_permission=False,
                )
                self.audit.record(
                    action="generate_from_schedule",
                    resource_type="BILL",
                    resource_id=model.id,
                    park_id=model.park_id,
                    detail={
                        "contract_id": model.contract_id,
                        "schedule_count": len(group["schedule_ids"]),
                    },
                )
                created.append(
                    {
                        "id": int(model.id),
                        "bill_no": bill_no,
                        "park_id": int(model.park_id),
                        "contract_id": int(model.contract_id),
                        "total_amount": str(model.total_amount),
                        "schedule_ids": group["schedule_ids"],
                    }
                )
            result = {
                "mode": "APPLY",
                "as_of": day.isoformat(),
                "created_count": len(created),
                "bills": created,
                "conflicts": plan["conflicts"],
            }
            complete_idempotent(
                self.session,
                tenant_id=self.ctx.tenant_id,
                operation="billing.schedule.apply",
                idem_key=idem_key,
                resource_type="BILLING_RUN",
                resource_id=idem_key,
                response=result,
            )
            self.session.commit()
            return result
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(
                "自动出账并发冲突", code="BILLING_RUN_CONFLICT", status_code=409
            ) from exc

"""功能说明：Bill 应用服务（人工出账）。"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.business_logging import log_business_success
from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.modules.billing.domain.entities import BillEntity, BillLineEntity
from app.modules.billing.domain.rules import (
    assert_fee_code,
    assert_transition,
    is_overdue,
    line_amount,
    money,
    open_amount,
    status_from_paid,
)
from app.modules.billing.infrastructure.bill_repository import BillLineRepository, BillRepository
from app.modules.billing.infrastructure.mappers import BillLineMapper, BillMapper
from app.modules.park_property.infrastructure.park_repository import ParkRepository
from app.modules.party.infrastructure.party_repository import PartyRepository
from app.modules.workbench.application.automation_service import WorkbenchAutomationService
from app.modules.workbench.application.work_item_service import WorkItemService
from app.shared.tenant_context import TenantContext

logger = logging.getLogger(__name__)

BILL_COLLECT_ITEM_TYPE = "BILL_UNPAID"


class BillService:
    """功能说明：编排账单草稿/签发/作废。"""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.bills = BillRepository(session, ctx)
        self.lines = BillLineRepository(session, ctx)
        self.parks = ParkRepository(session, ctx)
        self.parties = PartyRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)
        self.work_items = WorkItemService(session, ctx)
        self.events = WorkbenchAutomationService(session, ctx)

    def _open_collect_todo(self, model) -> None:
        """签发后幂等打开「账单待收款」待办（同事务 flush）。"""

        bill_no = model.bill_no or str(model.id)
        title = f"账单待收款 {bill_no}"
        due = None
        if model.due_date is not None:
            due = datetime.combine(model.due_date, datetime.min.time()).isoformat()
        self.work_items.ensure_from_source(
            source_type="BILL",
            source_id=str(model.id),
            item_type=BILL_COLLECT_ITEM_TYPE,
            title=title,
            description=f"party_id={model.party_id} open collect",
            park_id=int(model.park_id) if model.park_id is not None else None,
            priority="HIGH",
            due_at=due,
            commit=False,
        )

    def _close_collect_todo_paid(self, bill_id: int) -> None:
        self.work_items.complete_by_source(
            source_type="BILL",
            source_id=str(bill_id),
            item_type=BILL_COLLECT_ITEM_TYPE,
            commit=False,
        )

    def _cancel_collect_todo(self, bill_id: int) -> None:
        self.work_items.cancel_by_source(
            source_type="BILL",
            source_id=str(bill_id),
            item_type=BILL_COLLECT_ITEM_TYPE,
            commit=False,
        )

    def _require(self, bill_id: int, *, for_update: bool = False):
        m = self.bills.get_by_id(bill_id, for_update=for_update)
        if m is None:
            raise AppError("账单不存在", code="BILL_NOT_FOUND", status_code=404)
        return m

    def _parse_date(self, value: Any, field: str) -> date:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value[:10])
        raise AppError(f"{field} 无效", code="VALIDATION_ERROR", status_code=400)

    def _to_dict(self, model, *, with_lines: bool = False) -> dict[str, Any]:
        e = BillMapper.to_entity(model)
        oa = open_amount(e.total_amount, e.paid_amount)
        data = {
            "id": e.id,
            "tenant_id": e.tenant_id,
            "park_id": e.park_id,
            "party_id": e.party_id,
            "contract_id": e.contract_id,
            "bill_no": e.bill_no,
            "title": e.title,
            "period_start": e.period_start.isoformat(),
            "period_end": e.period_end.isoformat(),
            "due_date": e.due_date.isoformat() if e.due_date else None,
            "status": e.status,
            "total_amount": str(money(e.total_amount)),
            "paid_amount": str(money(e.paid_amount)),
            "open_amount": str(money(oa)),
            "is_overdue": is_overdue(
                status=e.status,
                due_date=e.due_date,
                total_amount=e.total_amount,
                paid_amount=e.paid_amount,
            ),
            "currency": e.currency,
            "source": e.source,
            "remark": e.remark,
        }
        if with_lines:
            data["lines"] = [
                {
                    "id": ln.id,
                    "fee_code": ln.fee_code,
                    "description": ln.description,
                    "quantity": str(ln.quantity),
                    "unit_price": str(ln.unit_price),
                    "amount": str(ln.amount),
                }
                for ln in self.lines.list_for_bill(int(model.id))
            ]
        return data

    def _replace_lines(self, bill_id: int, lines: list[dict[str, Any]]) -> Decimal:
        self.lines.delete_for_bill(bill_id)
        total = Decimal("0")
        for i, raw in enumerate(lines or []):
            try:
                fee = assert_fee_code(str(raw.get("fee_code") or "OTHER"))
            except ValueError as exc:
                raise AppError(str(exc), code="VALIDATION_ERROR", status_code=400) from exc
            qty = Decimal(str(raw.get("quantity") or 0))
            price = Decimal(str(raw.get("unit_price") or 0))
            amt_in = raw.get("amount")
            amt = line_amount(qty, price, Decimal(str(amt_in)) if amt_in is not None else None)
            total += amt
            self.lines.add(
                BillLineMapper.new_model(
                    BillLineEntity(
                        tenant_id=self.ctx.tenant_id,
                        bill_id=bill_id,
                        fee_code=fee,
                        description=str(raw.get("description") or ""),
                        quantity=qty,
                        unit_price=price,
                        amount=amt,
                        sort_order=int(raw.get("sort_order") or i),
                    )
                )
            )
        return money(total)

    def list_bills(self, **kwargs) -> dict[str, Any]:
        page = max(int(kwargs.get("page") or 1), 1)
        page_size = min(max(int(kwargs.get("page_size") or 20), 1), 200)
        status = kwargs.get("status")
        park_id = kwargs.get("park_id")
        party_id = kwargs.get("party_id")
        items = self.bills.list(
            offset=(page - 1) * page_size,
            limit=page_size,
            status=status,
            park_id=park_id,
            party_id=party_id,
        )
        total = self.bills.count(status=status, park_id=park_id, party_id=party_id)
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [self._to_dict(b) for b in items],
        }

    def get_bill(self, bill_id: int) -> dict[str, Any]:
        return self._to_dict(self._require(bill_id), with_lines=True)

    def create_bill(self, data: dict[str, Any]) -> dict[str, Any]:
        if not self.ctx.has_permission("bill:write"):
            raise AppError("无账单写权限", code="PERMISSION_DENIED", status_code=403)
        park_id = int(data["park_id"])
        party_id = int(data["party_id"])
        if not self.parks.exists_in_tenant(park_id):
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        if not self.ctx.allows_park(park_id):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        if self.parties.get_by_id(party_id) is None:
            raise AppError("主体不存在", code="PARTY_NOT_FOUND", status_code=404)
        ps = self._parse_date(data.get("period_start"), "period_start")
        pe = self._parse_date(data.get("period_end"), "period_end")
        if pe < ps:
            raise AppError("period_end 不得早于 period_start", code="VALIDATION_ERROR", status_code=400)
        dup = self.bills.find_duplicate_period(party_id, ps, pe)
        if dup:
            raise AppError("同期账单已存在", code="BILL_DUPLICATE_PERIOD", status_code=409)
        from app.infrastructure.platform.number_sequence import next_number

        bill_no = (data.get("bill_no") or "").strip()
        if not bill_no:
            seq = next_number(
                self.session,
                tenant_id=self.ctx.tenant_id,
                biz_type="BILL",
                period_key=ps.strftime("%Y%m"),
            )
            bill_no = f"B{ps.strftime('%Y%m')}{seq:04d}"
        due = data.get("due_date")
        model = BillMapper.new_model(
            BillEntity(
                tenant_id=self.ctx.tenant_id,
                park_id=park_id,
                party_id=party_id,
                contract_id=int(data["contract_id"]) if data.get("contract_id") else None,
                bill_no=bill_no,
                title=data.get("title"),
                period_start=ps,
                period_end=pe,
                due_date=self._parse_date(due, "due_date") if due else None,
                status="DRAFT",
                source=str(data.get("source") or "MANUAL"),
                remark=data.get("remark"),
                created_by=self.ctx.user_id,
            )
        )
        self.bills.add(model)
        total = self._replace_lines(int(model.id), data.get("lines") or [])
        model.total_amount = total
        self.bills.save(model)
        self.audit.record(
            action="create",
            resource_type="BILL",
            resource_id=model.id,
            park_id=park_id,
            detail={"bill_no": bill_no},
        )
        self.session.commit()
        log_business_success(
            logger, "创建账单草稿", ctx=self.ctx, module="billing", action="create", resource_id=model.id, park_id=park_id
        )
        return self.get_bill(int(model.id))

    def update_bill(self, bill_id: int, data: dict[str, Any]) -> dict[str, Any]:
        if not self.ctx.has_permission("bill:write"):
            raise AppError("无账单写权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(bill_id)
        if model.status != "DRAFT":
            raise AppError("仅草稿可编辑", code="BILL_STATUS_INVALID", status_code=400)
        if "title" in data:
            model.title = data["title"]
        if "remark" in data:
            model.remark = data["remark"]
        if "due_date" in data:
            due = data["due_date"]
            model.due_date = self._parse_date(due, "due_date") if due else None
        if "lines" in data:
            model.total_amount = self._replace_lines(int(model.id), data.get("lines") or [])
        self.bills.save(model)
        self.audit.record(
            action="update",
            resource_type="BILL",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"fields": sorted(data.keys())},
        )
        self.session.commit()
        return self.get_bill(bill_id)

    def issue(self, bill_id: int, *, idempotency_key: str | None = None) -> dict[str, Any]:
        """签发账单。

        缓存命中：先做动作权限 + 园区可见性，再返回首次 response_json（非当前状态）。
        未命中：行锁后校验当前业务状态（可签发性）再执行副作用。
        """

        if not self.ctx.has_permission("bill:issue"):
            raise AppError("无账单签发权限", code="PERMISSION_DENIED", status_code=403)
        from app.infrastructure.platform.idempotency import (
            begin_idempotent,
            complete_idempotent,
            normalize_idempotency_key,
            request_hash,
        )

        idem_key = normalize_idempotency_key(idempotency_key)
        # Access only: resource must be visible under current park scope (any status).
        self._require(bill_id, for_update=False)

        op = "bills.issue"
        body_hash = request_hash({"bill_id": bill_id})
        if idem_key:
            cached = begin_idempotent(
                self.session,
                tenant_id=self.ctx.tenant_id,
                user_id=self.ctx.user_id,
                operation=op,
                idem_key=idem_key,
                body_hash=body_hash,
            )
            if cached is not None:
                # First-response snapshot; do not re-read current VOID/PAID etc.
                return cached

        # Fresh create path: lock and enforce current business state.
        model = self._require(bill_id, for_update=True)
        try:
            model.status = assert_transition(model.status, "ISSUED")
        except ValueError as exc:
            raise AppError(str(exc), code="BILL_STATUS_INVALID", status_code=400) from exc
        if not self.lines.list_for_bill(bill_id):
            raise AppError("签发前须有明细行", code="BILL_LINES_REQUIRED", status_code=400)
        model.issued_at = utc_now()
        self.bills.save(model)
        self.audit.record(
            action="issue",
            resource_type="BILL",
            resource_id=model.id,
            park_id=model.park_id,
            detail={},
        )
        self._open_collect_todo(model)
        self.events.emit_event(
            event_type="BILL_ISSUED",
            source_type="BILL",
            source_id=str(model.id),
            idempotency_key=f"bill-issued:{model.id}",
            park_id=int(model.park_id) if model.park_id is not None else None,
            payload={
                "title": f"账单已签发 {model.bill_no or model.id}",
                "description": "账单进入待收款状态",
                "priority": "HIGH",
                "amount": str(model.total_amount or 0),
                "due_at": model.due_date.isoformat() if model.due_date else None,
                "deep_link": "/bills",
                "park_id": int(model.park_id) if model.park_id is not None else None,
            },
            commit=False,
            enforce_permission=False,
        )
        result = self.get_bill(bill_id)
        if idem_key:
            complete_idempotent(
                self.session,
                tenant_id=self.ctx.tenant_id,
                operation=op,
                idem_key=idem_key,
                resource_type="BILL",
                resource_id=str(bill_id),
                response=result,
            )
        self.session.commit()
        return result

    def void(self, bill_id: int) -> dict[str, Any]:
        if not self.ctx.has_permission("bill:issue"):
            raise AppError("无账单签发权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(bill_id)
        if Decimal(str(model.paid_amount or 0)) > 0:
            raise AppError("已收款账单不可作废", code="BILL_HAS_PAYMENT", status_code=409)
        try:
            model.status = assert_transition(model.status, "VOID")
        except ValueError as exc:
            raise AppError(str(exc), code="BILL_STATUS_INVALID", status_code=400) from exc
        model.overdue_since = None
        self.bills.save(model)
        self._cancel_collect_todo(bill_id)
        self.audit.record(
            action="void",
            resource_type="BILL",
            resource_id=model.id,
            park_id=model.park_id,
            detail={},
        )
        self.session.commit()
        return self.get_bill(bill_id)

    def discard(self, bill_id: int) -> dict[str, Any]:
        if not self.ctx.has_permission("bill:write"):
            raise AppError("无账单写权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(bill_id)
        try:
            model.status = assert_transition(model.status, "DISCARDED")
        except ValueError as exc:
            raise AppError(str(exc), code="BILL_STATUS_INVALID", status_code=400) from exc
        self.bills.save(model)
        self.audit.record(
            action="discard",
            resource_type="BILL",
            resource_id=model.id,
            park_id=model.park_id,
            detail={},
        )
        self.session.commit()
        return self.get_bill(bill_id)

    def apply_payment_delta(self, bill_id: int, delta: Decimal, *, already_locked: bool = False) -> None:
        """功能说明：收款核销回写 paid_amount 与 status（由 Payment 调用，同事务）。

        PostgreSQL 下对账单行 FOR UPDATE，防止并发丢失更新与超额核销。
        """

        model = self._require(bill_id, for_update=not already_locked)
        paid = money(Decimal(str(model.paid_amount or 0)) + Decimal(str(delta)))
        if paid < 0:
            raise AppError("核销金额非法", code="ALLOCATION_INVALID", status_code=400)
        total = money(model.total_amount)
        if paid > total:
            raise AppError("核销超过账单金额", code="ALLOCATION_EXCEEDS_BILL", status_code=409)
        model.paid_amount = paid
        model.status = status_from_paid(total, paid, model.status if model.status != "DRAFT" else "ISSUED")
        if model.status == "PAID":
            model.overdue_since = None
            self._close_collect_todo_paid(bill_id)
        elif model.status in {"ISSUED", "PARTIALLY_PAID"}:
            # 冲正或部分未结：重新打开收款待办
            self._open_collect_todo(model)
        self.bills.save(model)

    def lock_bills_ordered(self, bill_ids: list[int]) -> dict[int, Any]:
        """按 ID 升序锁定多张账单，降低死锁概率。"""

        locked: dict[int, Any] = {}
        for bid in sorted({int(x) for x in bill_ids}):
            locked[bid] = self._require(bid, for_update=True)
        return locked

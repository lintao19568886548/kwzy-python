"""功能说明：收款登记与核销应用服务（园区一致 + 并发安全 + 幂等）。"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.business_logging import log_business_success
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
from app.modules.billing.application.bill_service import BillService
from app.modules.billing.domain.rules import money
from app.modules.collection.domain.rules import (
    assert_allocations_within_payment,
    assert_method,
)
from app.modules.collection.infrastructure.payment_repository import (
    PaymentAllocationRepository,
    PaymentRepository,
)
from app.modules.park_property.infrastructure.park_repository import ParkRepository
from app.modules.party.infrastructure.party_repository import PartyRepository
from app.shared.tenant_context import TenantContext

logger = logging.getLogger(__name__)


class PaymentService:
    """功能说明：编排收款登记与账单核销。"""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.payments = PaymentRepository(session, ctx)
        self.allocs = PaymentAllocationRepository(session, ctx)
        self.bills = BillService(session, ctx)
        self.parks = ParkRepository(session, ctx)
        self.parties = PartyRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def _require(self, payment_id: int, *, for_update: bool = False):
        m = self.payments.get_by_id(payment_id, for_update=for_update)
        if m is None:
            raise AppError("收款单不存在", code="PAYMENT_NOT_FOUND", status_code=404)
        return m

    def _parse_dt(self, value: Any) -> datetime:
        if value is None or value == "":
            raise AppError("paid_at 必填", code="VALIDATION_ERROR", status_code=422)
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", ""))
        raise AppError("paid_at 无效", code="VALIDATION_ERROR", status_code=422)

    def _to_dict(self, model, *, with_alloc: bool = False) -> dict[str, Any]:
        data = {
            "id": model.id,
            "tenant_id": model.tenant_id,
            "park_id": model.park_id,
            "party_id": model.party_id,
            "payment_no": model.payment_no,
            "amount": str(model.amount),
            "method": model.method,
            "paid_at": model.paid_at.isoformat() if model.paid_at else None,
            "status": model.status,
            "remark": model.remark,
        }
        if with_alloc:
            data["allocations"] = [
                {"id": a.id, "bill_id": a.bill_id, "amount": str(a.amount)}
                for a in self.allocs.list_for_payment(int(model.id))
            ]
        return data

    def list_payments(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        party_id: Optional[int] = None,
        park_id: Optional[int] = None,
    ) -> dict[str, Any]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        items = self.payments.list(
            offset=(page - 1) * page_size,
            limit=page_size,
            party_id=party_id,
            park_id=park_id,
        )
        total = self.payments.count(party_id=party_id, park_id=park_id)
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [self._to_dict(p) for p in items],
        }

    def get_payment(self, payment_id: int) -> dict[str, Any]:
        return self._to_dict(self._require(payment_id), with_alloc=True)

    def _payment_request_hash(self, data: dict[str, Any]) -> str:
        """覆盖 PaymentCreate 全部业务字段（含 remark），不含 Token/密码。"""

        allocations = data.get("allocations") or []
        # normalize allocation dicts to stable order of keys
        alloc_norm = []
        for raw in allocations:
            if hasattr(raw, "model_dump"):
                raw = raw.model_dump()
            alloc_norm.append(
                {
                    "bill_id": raw.get("bill_id"),
                    "amount": raw.get("amount"),
                }
            )
        body_for_hash = {
            "amount": data.get("amount"),
            "allocations": alloc_norm,
            "method": data.get("method"),
            "paid_at": data.get("paid_at"),
            "park_id": data.get("park_id"),
            "party_id": data.get("party_id"),
            "payment_no": data.get("payment_no"),
            "remark": data.get("remark"),
        }
        return request_hash(body_for_hash)

    def _authorize_payment_create_access(self, data: dict[str, Any]) -> dict[str, Any]:
        """动作权限外的访问授权：tenant 园区、主体、账单可见性与请求结构。

        不含 Bill 业务状态（DRAFT/VOID 等）——状态校验仅在新创建路径行锁后执行。
        幂等缓存重放也走此路径，确保授权始终执行且不因后续 VOID/冲正而失败。
        """

        park_id = int(data["park_id"])
        party_id = int(data["party_id"])
        if not self.parks.exists_in_tenant(park_id):
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        if not self.ctx.allows_park(park_id):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        if self.parties.get_by_id(party_id) is None:
            raise AppError("主体不存在", code="PARTY_NOT_FOUND", status_code=404)
        try:
            method = assert_method(str(data.get("method") or "TRANSFER"))
        except ValueError as exc:
            raise AppError(str(exc), code="VALIDATION_ERROR", status_code=400) from exc
        amount = money(data.get("amount") or 0)
        if amount <= 0:
            raise AppError("收款金额须大于 0", code="VALIDATION_ERROR", status_code=400)
        paid_at = self._parse_dt(data.get("paid_at"))
        allocations = data.get("allocations") or []
        if hasattr(allocations, "__iter__") and allocations and hasattr(allocations[0], "model_dump"):
            allocations = [a.model_dump() if hasattr(a, "model_dump") else a for a in allocations]
        alloc_sum = money(sum(Decimal(str(a.get("amount") or 0)) for a in allocations))
        try:
            assert_allocations_within_payment(amount, alloc_sum)
        except ValueError as exc:
            raise AppError(str(exc), code="ALLOCATION_INVALID", status_code=400) from exc

        for raw in allocations:
            bill_id = int(raw["bill_id"])
            a_amt = money(raw.get("amount") or 0)
            if a_amt <= 0:
                raise AppError("核销金额须大于 0", code="VALIDATION_ERROR", status_code=400)
            # Scoped visibility only (BillRepository.get_by_id) — not business status.
            bill_model = self.bills.bills.get_by_id(bill_id)
            if bill_model is None:
                raise AppError("账单不存在", code="BILL_NOT_FOUND", status_code=404)
            if int(bill_model.party_id) != party_id:
                raise AppError("账单主体与收款主体不一致", code="PARTY_MISMATCH", status_code=400)
            if int(bill_model.park_id) != park_id:
                raise AppError(
                    "账单园区与收款园区不一致",
                    code="PAYMENT_BILL_PARK_MISMATCH",
                    status_code=409,
                )

        return {
            "park_id": park_id,
            "party_id": party_id,
            "method": method,
            "amount": amount,
            "paid_at": paid_at,
            "allocations": allocations,
        }

    def _assert_payment_create_business_state(
        self,
        *,
        park_id: int,
        party_id: int,
        locked_bills: dict[int, Any],
        allocations: list[dict[str, Any]],
    ) -> None:
        """新创建路径：行锁后校验当前业务状态（不可核销状态等）。"""

        for raw in allocations:
            bill_id = int(raw["bill_id"])
            bill = locked_bills[bill_id]
            if int(bill.party_id) != party_id:
                raise AppError("账单主体与收款主体不一致", code="PARTY_MISMATCH", status_code=400)
            if int(bill.park_id) != park_id:
                raise AppError(
                    "账单园区与收款园区不一致",
                    code="PAYMENT_BILL_PARK_MISMATCH",
                    status_code=409,
                )
            if bill.status in {"DRAFT", "VOID", "DISCARDED"}:
                raise AppError("账单状态不可核销", code="BILL_STATUS_INVALID", status_code=400)

    def create_payment(
        self, data: dict[str, Any], *, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        """功能说明：登记收款并核销账单（同园、可幂等、可并发）。

        幂等缓存命中：仍校验动作权限与数据范围，但返回首次缓存响应（非当前状态）。
        """

        if not self.ctx.has_permission("payment:write"):
            raise AppError("无收款登记权限", code="PERMISSION_DENIED", status_code=403)

        idem_key = normalize_idempotency_key(idempotency_key)
        op = "payments.create"
        body_hash = self._payment_request_hash(data)

        # Authorization ALWAYS before cache return (cannot skip park scope).
        authorized = self._authorize_payment_create_access(data)
        park_id = authorized["park_id"]
        party_id = authorized["party_id"]
        method = authorized["method"]
        amount = authorized["amount"]
        paid_at = authorized["paid_at"]
        allocations = authorized["allocations"]

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
                cached_id = int(cached.get("id") or 0)
                if cached_id <= 0:
                    raise AppError("幂等缓存无效", code="IDEMPOTENCY_CACHE_INVALID", status_code=409)
                # Access recheck only: resource must remain visible under current park scope.
                if self.payments.get_by_id(cached_id) is None:
                    raise AppError("收款单不存在", code="PAYMENT_NOT_FOUND", status_code=404)
                # Return first-response snapshot, not current Payment status.
                return cached

        bill_ids = [int(a["bill_id"]) for a in allocations]
        locked = self.bills.lock_bills_ordered(bill_ids) if bill_ids else {}
        self._assert_payment_create_business_state(
            park_id=park_id,
            party_id=party_id,
            locked_bills=locked,
            allocations=allocations,
        )

        pno = (data.get("payment_no") or "").strip()
        if not pno:
            seq = next_number(
                self.session,
                tenant_id=self.ctx.tenant_id,
                biz_type="PAYMENT",
                period_key=paid_at.strftime("%Y%m%d"),
            )
            pno = f"P{paid_at.strftime('%Y%m%d')}{seq:04d}"

        try:
            model = self.payments.create(
                park_id=park_id,
                party_id=party_id,
                payment_no=pno,
                amount=amount,
                method=method,
                paid_at=paid_at,
                operator_id=self.ctx.user_id,
                remark=data.get("remark"),
            )

            for raw in allocations:
                bill_id = int(raw["bill_id"])
                a_amt = money(raw.get("amount") or 0)
                self.bills.apply_payment_delta(bill_id, a_amt, already_locked=True)
                self.allocs.create(
                    payment_id=int(model.id),
                    bill_id=bill_id,
                    amount=a_amt,
                    created_at=utc_now(),
                )

            self.audit.record(
                action="create",
                resource_type="PAYMENT",
                resource_id=model.id,
                park_id=park_id,
                detail={"payment_no": pno, "amount": str(amount)},
            )
            result = self.get_payment(int(model.id))
            if idem_key:
                complete_idempotent(
                    self.session,
                    tenant_id=self.ctx.tenant_id,
                    operation=op,
                    idem_key=idem_key,
                    resource_type="PAYMENT",
                    resource_id=str(model.id),
                    response=result,
                )
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(
                "收款编号冲突",
                code="PAYMENT_NO_CONFLICT",
                status_code=409,
            ) from exc
        log_business_success(
            logger,
            "收款登记成功",
            ctx=self.ctx,
            module="collection",
            action="create_payment",
            resource_id=model.id,
            park_id=park_id,
        )
        return result

    def reverse_payment(self, payment_id: int) -> dict[str, Any]:
        """功能说明：冲正收款并回退核销（行锁防重复冲正）。"""

        if not self.ctx.has_permission("payment:write"):
            raise AppError("无收款登记权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(payment_id, for_update=True)
        if model.status != "CONFIRMED":
            raise AppError("仅已确认收款可冲正", code="PAYMENT_STATUS_INVALID", status_code=400)
        allocs = self.allocs.list_for_payment(payment_id)
        bill_ids = [int(a.bill_id) for a in allocs]
        self.bills.lock_bills_ordered(bill_ids)
        for a in allocs:
            self.bills.apply_payment_delta(int(a.bill_id), -money(a.amount), already_locked=True)
        model.status = "REVERSED"
        self.payments.save(model)
        self.audit.record(
            action="reverse",
            resource_type="PAYMENT",
            resource_id=model.id,
            park_id=model.park_id,
            detail={},
        )
        self.session.commit()
        return self.get_payment(payment_id)

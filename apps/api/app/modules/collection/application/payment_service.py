"""功能说明：收款登记与核销应用服务。"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.business_logging import log_business_success
from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
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

    def _require(self, payment_id: int):
        m = self.payments.get_by_id(payment_id)
        if m is None:
            raise AppError("收款单不存在", code="PAYMENT_NOT_FOUND", status_code=404)
        return m

    def _parse_dt(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", ""))
        return utc_now()

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
        self, *, page: int = 1, page_size: int = 20, party_id: Optional[int] = None
    ) -> dict[str, Any]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        items = self.payments.list(offset=(page - 1) * page_size, limit=page_size, party_id=party_id)
        total = self.payments.count(party_id=party_id)
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [self._to_dict(p) for p in items],
        }

    def get_payment(self, payment_id: int) -> dict[str, Any]:
        return self._to_dict(self._require(payment_id), with_alloc=True)

    def create_payment(self, data: dict[str, Any]) -> dict[str, Any]:
        """功能说明：
            登记收款并核销账单。

        业务规则：
            Payment=收款登记；非在线支付订单。
        """

        if not self.ctx.has_permission("payment:write"):
            raise AppError("无收款登记权限", code="PERMISSION_DENIED", status_code=403)
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
        allocations = data.get("allocations") or []
        alloc_sum = money(sum(Decimal(str(a.get("amount") or 0)) for a in allocations))
        try:
            assert_allocations_within_payment(amount, alloc_sum)
        except ValueError as exc:
            raise AppError(str(exc), code="ALLOCATION_INVALID", status_code=400) from exc

        pno = (data.get("payment_no") or "").strip() or f"P{utc_now().strftime('%Y%m%d')}{self.payments.next_seq():04d}"
        model = self.payments.create(
            park_id=park_id,
            party_id=party_id,
            payment_no=pno,
            amount=amount,
            method=method,
            paid_at=self._parse_dt(data.get("paid_at")),
            operator_id=self.ctx.user_id,
            remark=data.get("remark"),
        )

        for raw in allocations:
            bill_id = int(raw["bill_id"])
            a_amt = money(raw.get("amount") or 0)
            if a_amt <= 0:
                raise AppError("核销金额须大于 0", code="VALIDATION_ERROR", status_code=400)
            bill = self.bills._require(bill_id)
            if int(bill.party_id) != party_id:
                raise AppError("账单主体与收款主体不一致", code="PARTY_MISMATCH", status_code=400)
            if bill.status in {"DRAFT", "VOID", "DISCARDED"}:
                raise AppError("账单状态不可核销", code="BILL_STATUS_INVALID", status_code=400)
            self.bills.apply_payment_delta(bill_id, a_amt)
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
        self.session.commit()
        log_business_success(
            logger,
            "收款登记成功",
            ctx=self.ctx,
            module="collection",
            action="create_payment",
            resource_id=model.id,
            park_id=park_id,
        )
        return self.get_payment(int(model.id))

    def reverse_payment(self, payment_id: int) -> dict[str, Any]:
        """功能说明：冲正收款并回退核销。"""

        if not self.ctx.has_permission("payment:write"):
            raise AppError("无收款登记权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(payment_id)
        if model.status != "CONFIRMED":
            raise AppError("仅已确认收款可冲正", code="PAYMENT_STATUS_INVALID", status_code=400)
        for a in self.allocs.list_for_payment(payment_id):
            self.bills.apply_payment_delta(int(a.bill_id), -money(a.amount))
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

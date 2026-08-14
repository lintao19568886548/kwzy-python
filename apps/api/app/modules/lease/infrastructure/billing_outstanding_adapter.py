"""Scoped Billing outstanding reader; it performs no financial writes."""

from __future__ import annotations

from datetime import timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.billing import Bill
from app.modules.lease.application.billing_ports import BillingOutstandingSnapshot
from app.shared.tenant_context import TenantContext


class SqlAlchemyBillingOutstandingAdapter:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def for_contract(self, contract_id: int) -> BillingOutstandingSnapshot:
        amount = self.session.scalar(
            select(
                func.coalesce(func.sum(Bill.total_amount - Bill.paid_amount), 0)
            ).where(
                Bill.tenant_id == self.ctx.tenant_id,
                Bill.contract_id == int(contract_id),
                Bill.status.in_(["ISSUED", "PARTIALLY_PAID", "OVERDUE"]),
            )
        )
        return BillingOutstandingSnapshot(
            amount=Decimal(str(amount or 0)),
            currency="CNY",
            source="BILLING_SCOPED_READ",
            as_of=utc_now().replace(tzinfo=timezone.utc),
        )

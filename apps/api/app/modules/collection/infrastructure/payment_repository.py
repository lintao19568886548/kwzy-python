"""功能说明：Payment 仓储。"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.models.collection import Payment, PaymentAllocation
from app.shared.tenant_context import ParkScopeMode, TenantContext


class PaymentRepository:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def _scope(self, stmt):
        stmt = stmt.where(Payment.tenant_id == self.ctx.tenant_id)
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(Payment.park_id.in_(list(self.ctx.park_ids)))
        return stmt.where(False)

    def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        party_id: Optional[int] = None,
        park_id: Optional[int] = None,
    ) -> Sequence[Payment]:
        stmt = self._scope(select(Payment))
        if party_id is not None:
            stmt = stmt.where(Payment.party_id == int(party_id))
        if park_id is not None:
            stmt = stmt.where(Payment.park_id == int(park_id))
        return list(self.session.scalars(stmt.order_by(Payment.id.desc()).offset(offset).limit(limit)).all())

    def count(self, *, party_id: Optional[int] = None, park_id: Optional[int] = None) -> int:
        vis = self._scope(select(Payment.id))
        if party_id is not None:
            vis = vis.where(Payment.party_id == int(party_id))
        if park_id is not None:
            vis = vis.where(Payment.park_id == int(park_id))
        return int(self.session.scalar(select(func.count()).select_from(vis.subquery())) or 0)

    def get_by_id(self, payment_id: int, *, for_update: bool = False) -> Optional[Payment]:
        stmt = self._scope(select(Payment).where(Payment.id == payment_id))
        if for_update:
            dialect = self.session.bind.dialect.name if self.session.bind is not None else ""
            if dialect == "postgresql":
                stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def add(self, model: Payment) -> Payment:
        model.tenant_id = self.ctx.tenant_id
        self.session.add(model)
        self.session.flush()
        return model

    def create(
        self,
        *,
        park_id: int,
        party_id: int,
        payment_no: str,
        amount,
        method: str,
        paid_at,
        operator_id,
        remark,
    ) -> Payment:
        model = Payment(
            park_id=park_id,
            party_id=party_id,
            payment_no=payment_no,
            amount=amount,
            method=method,
            paid_at=paid_at,
            status="CONFIRMED",
            operator_id=operator_id,
            remark=remark,
        )
        return self.add(model)

    def save(self, model: Payment) -> Payment:
        if int(model.tenant_id) != self.ctx.tenant_id:
            raise AppError("租户不匹配", code="TENANT_MISMATCH", status_code=403)
        self.session.add(model)
        self.session.flush()
        return model


class PaymentAllocationRepository:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def list_for_payment(self, payment_id: int) -> list[PaymentAllocation]:
        return list(
            self.session.scalars(
                select(PaymentAllocation).where(
                    PaymentAllocation.tenant_id == self.ctx.tenant_id,
                    PaymentAllocation.payment_id == payment_id,
                )
            ).all()
        )

    def add(self, model: PaymentAllocation) -> PaymentAllocation:
        model.tenant_id = self.ctx.tenant_id
        self.session.add(model)
        self.session.flush()
        return model

    def create(self, *, payment_id: int, bill_id: int, amount, created_at) -> PaymentAllocation:
        return self.add(
            PaymentAllocation(
                payment_id=payment_id,
                bill_id=bill_id,
                amount=amount,
                created_at=created_at,
            )
        )

"""功能说明：Bill 仓储（tenant + park scope）。"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.models.billing import Bill, BillLine
from app.shared.tenant_context import ParkScopeMode, TenantContext


class BillRepository:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def _scope(self, stmt):
        stmt = stmt.where(Bill.tenant_id == self.ctx.tenant_id)
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(Bill.park_id.in_(list(self.ctx.park_ids)))
        return stmt.where(False)

    def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        party_id: Optional[int] = None,
    ) -> Sequence[Bill]:
        stmt = self._scope(select(Bill))
        if status:
            stmt = stmt.where(Bill.status == status)
        if park_id is not None:
            stmt = stmt.where(Bill.park_id == int(park_id))
        if party_id is not None:
            stmt = stmt.where(Bill.party_id == int(party_id))
        return list(
            self.session.scalars(stmt.order_by(Bill.id.desc()).offset(offset).limit(limit)).all()
        )

    def count(
        self,
        *,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        party_id: Optional[int] = None,
    ) -> int:
        vis = self._scope(select(Bill.id))
        if status:
            vis = vis.where(Bill.status == status)
        if park_id is not None:
            vis = vis.where(Bill.park_id == int(park_id))
        if party_id is not None:
            vis = vis.where(Bill.party_id == int(party_id))
        return int(self.session.scalar(select(func.count()).select_from(vis.subquery())) or 0)

    def get_by_id(self, bill_id: int, *, for_update: bool = False) -> Optional[Bill]:
        stmt = self._scope(select(Bill).where(Bill.id == bill_id))
        if for_update:
            dialect = self.session.bind.dialect.name if self.session.bind is not None else ""
            if dialect == "postgresql":
                stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def find_duplicate_period(
        self, party_id: int, period_start, period_end, *, exclude_id: Optional[int] = None
    ) -> Optional[Bill]:
        stmt = select(Bill).where(
            Bill.tenant_id == self.ctx.tenant_id,
            Bill.party_id == party_id,
            Bill.period_start == period_start,
            Bill.period_end == period_end,
            Bill.status.notin_(["DISCARDED", "VOID"]),
        )
        if exclude_id:
            stmt = stmt.where(Bill.id != exclude_id)
        return self.session.scalars(stmt).first()

    def add(self, model: Bill) -> Bill:
        model.tenant_id = self.ctx.tenant_id
        self.session.add(model)
        self.session.flush()
        return model

    def save(self, model: Bill) -> Bill:
        if int(model.tenant_id) != self.ctx.tenant_id:
            raise AppError("租户不匹配", code="TENANT_MISMATCH", status_code=403)
        self.session.add(model)
        self.session.flush()
        return model


class BillLineRepository:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def list_for_bill(self, bill_id: int) -> list[BillLine]:
        return list(
            self.session.scalars(
                select(BillLine)
                .where(BillLine.tenant_id == self.ctx.tenant_id, BillLine.bill_id == bill_id)
                .order_by(BillLine.sort_order, BillLine.id)
            ).all()
        )

    def delete_for_bill(self, bill_id: int) -> None:
        for row in self.list_for_bill(bill_id):
            self.session.delete(row)
        self.session.flush()

    def add(self, model: BillLine) -> BillLine:
        model.tenant_id = self.ctx.tenant_id
        self.session.add(model)
        self.session.flush()
        return model

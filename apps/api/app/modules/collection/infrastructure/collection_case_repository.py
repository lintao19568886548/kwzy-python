"""功能说明：催缴案件仓储。"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.collection_case import CollectionCase
from app.shared.tenant_context import ParkScopeMode, TenantContext


class CollectionCaseRepository:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def _scope(self, stmt):
        stmt = stmt.where(CollectionCase.tenant_id == self.ctx.tenant_id)
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(CollectionCase.park_id.in_(list(self.ctx.park_ids)))
        return stmt.where(False)

    def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        bill_id: Optional[int] = None,
    ) -> Sequence[CollectionCase]:
        stmt = self._scope(select(CollectionCase))
        if status:
            stmt = stmt.where(CollectionCase.status == status)
        if park_id is not None:
            stmt = stmt.where(CollectionCase.park_id == int(park_id))
        if bill_id is not None:
            stmt = stmt.where(CollectionCase.bill_id == int(bill_id))
        return list(
            self.session.scalars(
                stmt.order_by(CollectionCase.id.desc()).offset(offset).limit(limit)
            ).all()
        )

    def count(
        self,
        *,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        bill_id: Optional[int] = None,
    ) -> int:
        vis = self._scope(select(CollectionCase.id))
        if status:
            vis = vis.where(CollectionCase.status == status)
        if park_id is not None:
            vis = vis.where(CollectionCase.park_id == int(park_id))
        if bill_id is not None:
            vis = vis.where(CollectionCase.bill_id == int(bill_id))
        return int(self.session.scalar(select(func.count()).select_from(vis.subquery())) or 0)

    def get_by_id(self, case_id: int) -> Optional[CollectionCase]:
        return self.session.scalars(
            self._scope(select(CollectionCase).where(CollectionCase.id == case_id))
        ).first()

    def create(
        self,
        *,
        park_id: int,
        party_id: int,
        bill_id: int,
        level: str,
        assignee_user_id: Optional[int],
        remark: Optional[str],
    ) -> CollectionCase:
        model = CollectionCase(
            tenant_id=self.ctx.tenant_id,
            park_id=park_id,
            party_id=party_id,
            bill_id=bill_id,
            status="OPEN",
            level=level,
            assignee_user_id=assignee_user_id,
            remark=remark,
        )
        self.session.add(model)
        self.session.flush()
        return model

    def save(self, model: CollectionCase) -> CollectionCase:
        self.session.add(model)
        self.session.flush()
        return model

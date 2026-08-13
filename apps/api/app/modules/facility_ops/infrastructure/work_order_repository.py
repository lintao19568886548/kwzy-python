"""功能说明：WorkOrder 仓储。"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.models.facility_ops import WorkOrder
from app.shared.tenant_context import ParkScopeMode, TenantContext


class WorkOrderRepository:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def _scope(self, stmt):
        stmt = stmt.where(WorkOrder.tenant_id == self.ctx.tenant_id)
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(WorkOrder.park_id.in_(list(self.ctx.park_ids)))
        return stmt.where(False)

    def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
    ) -> Sequence[WorkOrder]:
        stmt = self._scope(select(WorkOrder))
        if status:
            stmt = stmt.where(WorkOrder.status == status)
        if park_id is not None:
            stmt = stmt.where(WorkOrder.park_id == int(park_id))
        return list(
            self.session.scalars(stmt.order_by(WorkOrder.id.desc()).offset(offset).limit(limit)).all()
        )

    def count(self, *, status: Optional[str] = None, park_id: Optional[int] = None) -> int:
        vis = self._scope(select(WorkOrder.id))
        if status:
            vis = vis.where(WorkOrder.status == status)
        if park_id is not None:
            vis = vis.where(WorkOrder.park_id == int(park_id))
        return int(self.session.scalar(select(func.count()).select_from(vis.subquery())) or 0)

    def get_by_id(self, work_order_id: int, *, for_update: bool = False) -> Optional[WorkOrder]:
        stmt = self._scope(select(WorkOrder).where(WorkOrder.id == work_order_id))
        if for_update:
            dialect = self.session.bind.dialect.name if self.session.bind is not None else ""
            if dialect == "postgresql":
                stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def add(self, model: WorkOrder) -> WorkOrder:
        model.tenant_id = self.ctx.tenant_id
        self.session.add(model)
        self.session.flush()
        return model

    def create(
        self,
        *,
        park_id: int,
        title: str,
        description: Optional[str],
        category: str,
        priority: str,
        reporter_user_id: Optional[int],
        assignee_user_id: Optional[int],
        unit_id: Optional[int],
        due_at,
    ) -> WorkOrder:
        model = WorkOrder(
            park_id=park_id,
            title=title,
            description=description,
            category=category,
            priority=priority,
            status="OPEN",
            reporter_user_id=reporter_user_id,
            assignee_user_id=assignee_user_id,
            unit_id=unit_id,
            due_at=due_at,
            source_type="MANUAL",
            source_id="",
        )
        return self.add(model)

    def save(self, model: WorkOrder) -> WorkOrder:
        if int(model.tenant_id) != self.ctx.tenant_id:
            raise AppError("租户不匹配", code="TENANT_MISMATCH", status_code=403)
        self.session.add(model)
        self.session.flush()
        return model

"""功能说明：Lead 仓储（tenant + park scope）。"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.models.investment import Lead
from app.shared.tenant_context import ParkScopeMode, TenantContext


class LeadRepository:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def _scope(self, stmt):
        stmt = stmt.where(Lead.tenant_id == self.ctx.tenant_id)
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(Lead.park_id.in_(list(self.ctx.park_ids)))
        return stmt.where(False)

    def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        keyword: Optional[str] = None,
    ) -> Sequence[Lead]:
        stmt = self._scope(select(Lead))
        if status:
            stmt = stmt.where(Lead.status == status)
        if park_id is not None:
            stmt = stmt.where(Lead.park_id == int(park_id))
        if keyword:
            kw = f"%{keyword.strip()}%"
            stmt = stmt.where(
                (Lead.name.like(kw))
                | (Lead.contact_phone.like(kw))
                | (Lead.contact_name.like(kw))
            )
        return list(
            self.session.scalars(stmt.order_by(Lead.id.desc()).offset(offset).limit(limit)).all()
        )

    def count(
        self,
        *,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        keyword: Optional[str] = None,
    ) -> int:
        vis = self._scope(select(Lead.id))
        if status:
            vis = vis.where(Lead.status == status)
        if park_id is not None:
            vis = vis.where(Lead.park_id == int(park_id))
        if keyword:
            kw = f"%{keyword.strip()}%"
            vis = vis.where(
                (Lead.name.like(kw))
                | (Lead.contact_phone.like(kw))
                | (Lead.contact_name.like(kw))
            )
        return int(self.session.scalar(select(func.count()).select_from(vis.subquery())) or 0)

    def get_by_id(self, lead_id: int, *, for_update: bool = False) -> Optional[Lead]:
        stmt = self._scope(select(Lead).where(Lead.id == lead_id))
        if for_update:
            dialect = self.session.bind.dialect.name if self.session.bind is not None else ""
            if dialect == "postgresql":
                stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def add(self, model: Lead) -> Lead:
        model.tenant_id = self.ctx.tenant_id
        self.session.add(model)
        self.session.flush()
        return model

    def create(
        self,
        *,
        park_id: int,
        name: str,
        contact_phone: str,
        contact_name: Optional[str],
        agent_name: Optional[str],
        intent_level: Optional[str],
        intent_area,
        status: str,
        remark: Optional[str],
        owner_user_id: Optional[int],
    ) -> Lead:
        model = Lead(
            park_id=park_id,
            name=name,
            contact_phone=contact_phone,
            contact_name=contact_name,
            agent_name=agent_name,
            intent_level=intent_level,
            intent_area=intent_area,
            status=status,
            remark=remark,
            owner_user_id=owner_user_id,
        )
        return self.add(model)

    def save(self, model: Lead) -> Lead:
        if int(model.tenant_id) != self.ctx.tenant_id:
            raise AppError("租户不匹配", code="TENANT_MISMATCH", status_code=403)
        self.session.add(model)
        self.session.flush()
        return model

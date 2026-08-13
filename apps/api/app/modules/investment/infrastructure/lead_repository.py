"""功能说明：Lead 仓储（tenant + park scope）。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.models.investment import Lead
from app.shared.tenant_context import ParkScopeMode, TenantContext


class LeadRepository:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def _base_scope(self, stmt):
        stmt = stmt.where(Lead.tenant_id == self.ctx.tenant_id)
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(Lead.park_id.in_(list(self.ctx.park_ids)))
        return stmt.where(False)

    def _scope(self, stmt, *, manage: bool = False):
        stmt = self._base_scope(stmt)
        if manage or self.ctx.has_permission("lead:manage"):
            return stmt
        return stmt.where(
            or_(
                Lead.owner_user_id == self.ctx.user_id,
                Lead.pool_status == "PUBLIC",
            )
        )

    @staticmethod
    def _filters(
        stmt,
        *,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        keyword: Optional[str] = None,
        owner_user_id: Optional[int] = None,
        pool_status: Optional[str] = None,
        source_type: Optional[str] = None,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
        include_merged: bool = False,
    ):
        if status:
            stmt = stmt.where(Lead.status == status)
        elif not include_merged:
            stmt = stmt.where(Lead.status != "MERGED")
        if park_id is not None:
            stmt = stmt.where(Lead.park_id == int(park_id))
        if owner_user_id is not None:
            stmt = stmt.where(Lead.owner_user_id == int(owner_user_id))
        if pool_status:
            stmt = stmt.where(Lead.pool_status == pool_status)
        if source_type:
            stmt = stmt.where(Lead.source_type == source_type)
        if created_from is not None:
            stmt = stmt.where(Lead.created_at >= created_from)
        if created_to is not None:
            stmt = stmt.where(Lead.created_at < created_to)
        if keyword:
            kw = f"%{keyword.strip()}%"
            stmt = stmt.where(
                (Lead.name.like(kw))
                | (Lead.contact_phone.like(kw))
                | (Lead.contact_name.like(kw))
            )
        return stmt

    def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        keyword: Optional[str] = None,
        owner_user_id: Optional[int] = None,
        pool_status: Optional[str] = None,
        source_type: Optional[str] = None,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
        include_merged: bool = False,
    ) -> Sequence[Lead]:
        stmt = self._filters(
            self._scope(select(Lead)),
            status=status,
            park_id=park_id,
            keyword=keyword,
            owner_user_id=owner_user_id,
            pool_status=pool_status,
            source_type=source_type,
            created_from=created_from,
            created_to=created_to,
            include_merged=include_merged,
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
        owner_user_id: Optional[int] = None,
        pool_status: Optional[str] = None,
        source_type: Optional[str] = None,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
        include_merged: bool = False,
    ) -> int:
        vis = self._filters(
            self._scope(select(Lead.id)),
            status=status,
            park_id=park_id,
            keyword=keyword,
            owner_user_id=owner_user_id,
            pool_status=pool_status,
            source_type=source_type,
            created_from=created_from,
            created_to=created_to,
            include_merged=include_merged,
        )
        return int(self.session.scalar(select(func.count()).select_from(vis.subquery())) or 0)

    def all_filtered(self, **filters) -> Sequence[Lead]:
        return list(
            self.session.scalars(
                self._filters(self._scope(select(Lead)), **filters).order_by(Lead.id)
            ).all()
        )

    def get_by_id(
        self,
        lead_id: int,
        *,
        for_update: bool = False,
        manage: bool = False,
    ) -> Optional[Lead]:
        stmt = self._scope(select(Lead).where(Lead.id == lead_id), manage=manage)
        if for_update:
            dialect = self.session.bind.dialect.name if self.session.bind is not None else ""
            if dialect == "postgresql":
                stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def get_pair_for_update(self, first_id: int, second_id: int) -> list[Lead]:
        stmt = self._scope(
            select(Lead).where(Lead.id.in_([first_id, second_id])),
            manage=True,
        ).order_by(Lead.id)
        if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return list(self.session.scalars(stmt).all())

    def duplicate_candidates(
        self,
        *,
        normalized_name: str,
        normalized_phone: str,
        source_type: Optional[str] = None,
        source_ref: Optional[str] = None,
        exclude_id: Optional[int] = None,
        limit: int = 20,
    ) -> Sequence[Lead]:
        predicates = [
            Lead.normalized_phone == normalized_phone,
            Lead.normalized_name == normalized_name,
        ]
        if source_type and source_ref:
            predicates.append(
                (Lead.source_type == source_type) & (Lead.source_ref == source_ref)
            )
        # Duplicate prevention is tenant/park scoped but intentionally not owner scoped;
        # service serialization masks candidates the caller may not fully view.
        stmt = self._base_scope(select(Lead).where(or_(*predicates)))
        stmt = stmt.where(Lead.status != "MERGED")
        if exclude_id is not None:
            stmt = stmt.where(Lead.id != int(exclude_id))
        return list(self.session.scalars(stmt.order_by(Lead.id.desc()).limit(limit)).all())

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
        normalized_name: str = "",
        normalized_phone: str = "",
        source_type: str = "MANUAL",
        source_ref: Optional[str] = None,
        duplicate_override_reason: Optional[str] = None,
        pool_status: str = "PRIVATE",
        desired_usage: Optional[str] = None,
        budget_unit_price=None,
        assigned_at: Optional[datetime] = None,
        next_follow_up_at: Optional[datetime] = None,
        recycle_due_at: Optional[datetime] = None,
    ) -> Lead:
        model = Lead(
            park_id=park_id,
            name=name,
            contact_phone=contact_phone,
            contact_name=contact_name,
            agent_name=agent_name,
            intent_level=intent_level,
            intent_area=intent_area,
            desired_usage=desired_usage,
            budget_unit_price=budget_unit_price,
            status=status,
            normalized_name=normalized_name,
            normalized_phone=normalized_phone,
            source_type=source_type,
            source_ref=source_ref,
            duplicate_override_reason=duplicate_override_reason,
            pool_status=pool_status,
            remark=remark,
            owner_user_id=owner_user_id,
            assigned_at=assigned_at,
            next_follow_up_at=next_follow_up_at,
            recycle_due_at=recycle_due_at,
            lock_version=1,
        )
        return self.add(model)

    def save(self, model: Lead) -> Lead:
        if int(model.tenant_id) != self.ctx.tenant_id:
            raise AppError("租户不匹配", code="TENANT_MISMATCH", status_code=403)
        self.session.add(model)
        self.session.flush()
        return model

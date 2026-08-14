"""功能说明：审批仓储。"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.workflow import ApprovalEvent, ApprovalRequest
from app.shared.tenant_context import ParkScopeMode, TenantContext


class ApprovalRepository:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def _scope(self, stmt):
        stmt = stmt.where(ApprovalRequest.tenant_id == self.ctx.tenant_id)
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(
                (ApprovalRequest.park_id.is_(None))
                | (ApprovalRequest.park_id.in_(list(self.ctx.park_ids)))
            )
        return stmt.where(ApprovalRequest.park_id.is_(None))

    def list(
        self, *, status: Optional[str] = None, offset: int = 0, limit: int = 20
    ) -> Sequence[ApprovalRequest]:
        stmt = self._scope(select(ApprovalRequest))
        if status:
            stmt = stmt.where(ApprovalRequest.status == status)
        return list(
            self.session.scalars(
                stmt.order_by(ApprovalRequest.id.desc()).offset(offset).limit(limit)
            ).all()
        )

    def count(self, *, status: Optional[str] = None) -> int:
        vis = self._scope(select(ApprovalRequest.id))
        if status:
            vis = vis.where(ApprovalRequest.status == status)
        return int(self.session.scalar(select(func.count()).select_from(vis.subquery())) or 0)

    def get_by_id(
        self, approval_id: int, *, for_update: bool = False
    ) -> Optional[ApprovalRequest]:
        stmt = self._scope(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))
        if for_update:
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def get_by_biz(self, biz_type: str, biz_id: str) -> Optional[ApprovalRequest]:
        return self.session.scalars(
            select(ApprovalRequest).where(
                ApprovalRequest.tenant_id == self.ctx.tenant_id,
                ApprovalRequest.biz_type == biz_type,
                ApprovalRequest.biz_id == biz_id,
            )
        ).first()

    def list_for_lease(
        self, contract_id: int, *, related_approval_ids: set[int]
    ) -> Sequence[ApprovalRequest]:
        conditions = [
            (
                (ApprovalRequest.biz_type == "LEASE_CONTRACT_VERSION")
                & ApprovalRequest.biz_id.like(f"{int(contract_id)}:%")
            )
        ]
        if related_approval_ids:
            conditions.append(ApprovalRequest.id.in_(sorted(related_approval_ids)))
        stmt = self._scope(select(ApprovalRequest)).where(or_(*conditions))
        return list(self.session.scalars(stmt.order_by(ApprovalRequest.id)).all())

    def create(
        self,
        *,
        park_id: Optional[int],
        biz_type: str,
        biz_id: str,
        title: str,
        applicant_user_id: Optional[int],
        remark: Optional[str],
    ) -> ApprovalRequest:
        model = ApprovalRequest(
            tenant_id=self.ctx.tenant_id,
            park_id=park_id,
            biz_type=biz_type,
            biz_id=biz_id,
            title=title,
            status="PENDING",
            applicant_user_id=applicant_user_id,
            remark=remark,
        )
        self.session.add(model)
        self.session.flush()
        return model

    def save(self, model: ApprovalRequest) -> ApprovalRequest:
        self.session.add(model)
        self.session.flush()
        return model

    def add_event(
        self,
        *,
        approval_id: int,
        action: str,
        actor_user_id: Optional[int],
        remark: Optional[str],
    ) -> ApprovalEvent:
        ev = ApprovalEvent(
            tenant_id=self.ctx.tenant_id,
            approval_id=approval_id,
            action=action,
            actor_user_id=actor_user_id,
            remark=remark,
        )
        self.session.add(ev)
        self.session.flush()
        return ev

    def list_events(self, approval_id: int) -> Sequence[ApprovalEvent]:
        return list(
            self.session.scalars(
                select(ApprovalEvent)
                .where(
                    ApprovalEvent.tenant_id == self.ctx.tenant_id,
                    ApprovalEvent.approval_id == approval_id,
                )
                .order_by(ApprovalEvent.id.asc())
            ).all()
        )

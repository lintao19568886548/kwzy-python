"""功能说明：审批仓储。"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.workflow import ApprovalRequest
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

    def get_by_id(self, approval_id: int) -> Optional[ApprovalRequest]:
        return self.session.scalars(
            self._scope(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))
        ).first()

    def get_by_biz(self, biz_type: str, biz_id: str) -> Optional[ApprovalRequest]:
        return self.session.scalars(
            select(ApprovalRequest).where(
                ApprovalRequest.tenant_id == self.ctx.tenant_id,
                ApprovalRequest.biz_type == biz_type,
                ApprovalRequest.biz_id == biz_id,
            )
        ).first()

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

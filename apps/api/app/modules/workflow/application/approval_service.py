"""功能说明：最小审批申请服务（PENDING→APPROVED/REJECTED）。"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.modules.workflow.infrastructure.approval_repository import ApprovalRepository
from app.shared.tenant_context import TenantContext


class ApprovalService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.repo = ApprovalRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def list_approvals(
        self, *, status: Optional[str] = None, page: int = 1, page_size: int = 20
    ) -> dict[str, Any]:
        if not self.ctx.has_permission("approval:read"):
            raise AppError("无审批查看权限", code="PERMISSION_DENIED", status_code=403)
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        items = self.repo.list(status=status, offset=(page - 1) * page_size, limit=page_size)
        total = self.repo.count(status=status)
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [self._to_dict(i) for i in items],
        }

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        if not self.ctx.has_permission("approval:write"):
            raise AppError("无审批申请权限", code="PERMISSION_DENIED", status_code=403)
        biz_type = str(data.get("biz_type") or "").strip()
        biz_id = str(data.get("biz_id") or "").strip()
        title = str(data.get("title") or "").strip()
        if not biz_type or not biz_id or not title:
            raise AppError("biz_type/biz_id/title 必填", code="VALIDATION_ERROR", status_code=400)
        existing = self.repo.get_by_biz(biz_type, biz_id)
        if existing is not None:
            raise AppError("该业务已存在审批单", code="APPROVAL_DUPLICATE", status_code=409)
        try:
            model = self.repo.create(
                park_id=int(data["park_id"]) if data.get("park_id") is not None else None,
                biz_type=biz_type,
                biz_id=biz_id,
                title=title,
                applicant_user_id=self.ctx.user_id or None,
                remark=data.get("remark"),
            )
            self.audit.record(
                action="create",
                resource_type="APPROVAL",
                resource_id=model.id,
                park_id=model.park_id,
                detail={"biz_type": biz_type, "biz_id": biz_id},
            )
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(
                "该业务已存在审批单", code="APPROVAL_DUPLICATE", status_code=409
            ) from exc
        return self._to_dict(model)

    def decide(self, approval_id: int, *, approve: bool, remark: Optional[str] = None) -> dict:
        if not self.ctx.has_permission("approval:decide"):
            raise AppError("无审批决定权限", code="PERMISSION_DENIED", status_code=403)
        model = self.repo.get_by_id(approval_id)
        if model is None:
            raise AppError("审批单不存在", code="APPROVAL_NOT_FOUND", status_code=404)
        if model.status != "PENDING":
            raise AppError("非待审状态", code="APPROVAL_STATUS_INVALID", status_code=400)
        model.status = "APPROVED" if approve else "REJECTED"
        model.approver_user_id = self.ctx.user_id or None
        model.decision_remark = remark
        self.repo.save(model)
        self.audit.record(
            action="approve" if approve else "reject",
            resource_type="APPROVAL",
            resource_id=model.id,
            park_id=model.park_id,
            detail={},
        )
        self.session.commit()
        return self._to_dict(model)

    def _to_dict(self, m) -> dict[str, Any]:
        return {
            "id": m.id,
            "park_id": m.park_id,
            "biz_type": m.biz_type,
            "biz_id": m.biz_id,
            "title": m.title,
            "status": m.status,
            "applicant_user_id": m.applicant_user_id,
            "approver_user_id": m.approver_user_id,
            "remark": m.remark,
            "decision_remark": m.decision_remark,
        }

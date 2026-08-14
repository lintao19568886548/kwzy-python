"""Workflow-backed, commit-free Lease approval adapter."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.workflow.infrastructure.approval_repository import ApprovalRepository
from app.shared.tenant_context import TenantContext

LEASE_MANAGED_APPROVAL_TYPES = frozenset(
    {"LEASE_CONTRACT_VERSION", "LEASE_CHANGE_ORDER", "LEASE_EXIT_SETTLEMENT"}
)


class WorkflowApprovalCommandAdapter:
    """Write approval rows without committing the caller's Lease transaction."""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.repository = ApprovalRepository(session, ctx)
        self.ctx = ctx

    def submit(
        self,
        *,
        park_id: int,
        biz_type: str,
        biz_id: str,
        title: str,
        remark: Optional[str],
    ):
        normalized = (biz_type or "").strip().upper()
        if normalized not in LEASE_MANAGED_APPROVAL_TYPES:
            raise AppError("审批类型不属于租赁域", code="APPROVAL_BIZ_TYPE_INVALID", status_code=400)
        if self.repository.get_by_biz(normalized, biz_id) is not None:
            raise AppError("该修订已存在审批", code="APPROVAL_DUPLICATE", status_code=409)
        model = self.repository.create(
            park_id=int(park_id),
            biz_type=normalized,
            biz_id=str(biz_id),
            title=title,
            applicant_user_id=self.ctx.user_id or None,
            remark=remark,
        )
        self.repository.add_event(
            approval_id=int(model.id),
            action="SUBMIT",
            actor_user_id=self.ctx.user_id or None,
            remark=remark,
        )
        return model

    def decide(
        self,
        approval_id: int,
        *,
        approve: bool,
        remark: Optional[str],
        override_reason: Optional[str] = None,
    ):
        model = self.get(approval_id, for_update=True)
        if model.status != "PENDING":
            raise AppError("非待审状态", code="APPROVAL_STATUS_INVALID", status_code=409)
        same_actor = int(model.applicant_user_id or 0) == int(self.ctx.user_id or 0)
        if same_actor:
            if not self.ctx.has_permission("lease:approve_override"):
                raise AppError(
                    "申请人与审批人必须分离",
                    code="LEASE_SELF_APPROVAL_FORBIDDEN",
                    status_code=403,
                )
            if not (override_reason or "").strip():
                raise AppError("越权审批必须填写原因", code="LEASE_APPROVAL_OVERRIDE_REASON_REQUIRED", status_code=400)
        model.status = "APPROVED" if approve else "REJECTED"
        model.approver_user_id = self.ctx.user_id or None
        model.decision_remark = remark
        self.repository.save(model)
        event_remark = remark
        if same_actor:
            event_remark = f"override={override_reason}; decision={remark or ''}"
        self.repository.add_event(
            approval_id=int(model.id),
            action="APPROVE" if approve else "REJECT",
            actor_user_id=self.ctx.user_id or None,
            remark=event_remark,
        )
        return model

    def withdraw(self, approval_id: int, *, remark: Optional[str]):
        model = self.get(approval_id, for_update=True)
        if model.status != "PENDING":
            raise AppError("仅待审可撤回", code="APPROVAL_STATUS_INVALID", status_code=409)
        if int(model.applicant_user_id or 0) != int(self.ctx.user_id or 0):
            raise AppError("仅申请人可撤回", code="PERMISSION_DENIED", status_code=403)
        model.status = "WITHDRAWN"
        self.repository.save(model)
        self.repository.add_event(
            approval_id=int(model.id),
            action="WITHDRAW",
            actor_user_id=self.ctx.user_id or None,
            remark=remark,
        )
        return model

    def get(self, approval_id: int, *, for_update: bool = False):
        model = self.repository.get_by_id(approval_id, for_update=for_update)
        if model is None or model.biz_type not in LEASE_MANAGED_APPROVAL_TYPES:
            raise AppError("审批单不存在", code="APPROVAL_NOT_FOUND", status_code=404)
        return model

    def events(self, approval_id: int):
        self.get(approval_id)
        return self.repository.list_events(approval_id)

    def timeline_for_contract(
        self, contract_id: int, *, related_approval_ids: set[int]
    ) -> list[dict]:
        timeline: list[dict] = []
        for request in self.repository.list_for_lease(
            contract_id, related_approval_ids=related_approval_ids
        ):
            timeline.append(
                {
                    "approval_id": int(request.id),
                    "biz_type": request.biz_type,
                    "biz_id": request.biz_id,
                    "title": request.title,
                    "status": request.status,
                    "applicant_user_id": request.applicant_user_id,
                    "approver_user_id": request.approver_user_id,
                    "created_at": request.created_at.isoformat() if request.created_at else None,
                    "events": [
                        {
                            "id": int(event.id),
                            "action": event.action,
                            "actor_user_id": event.actor_user_id,
                            "remark": event.remark,
                            "created_at": event.created_at.isoformat() if event.created_at else None,
                        }
                        for event in self.repository.list_events(int(request.id))
                    ],
                }
            )
        return timeline

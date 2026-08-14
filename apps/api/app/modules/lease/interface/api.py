"""功能说明：
    Lease REST 路由。

业务职责：
    Interface；鉴权与 envelope；业务在 LeaseService。
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.session import get_db
from app.modules.lease.application.contract_lifecycle_service import ContractLifecycleService
from app.modules.lease.application.lease_service import LeaseService
from app.modules.lease.interface.schemas import (
    LeaseApprovalCommand,
    LeaseApplyDue,
    LeaseChargeReplace,
    LeaseChangeApply,
    LeaseChangeCreate,
    LeaseChangeDecision,
    LeaseChangeEdit,
    LeaseCreate,
    LeaseDocumentCommand,
    LeaseDocumentCreate,
    LeaseExitClearance,
    LeaseExitClose,
    LeaseExitCreate,
    LeaseExitDecision,
    LeaseExitEdit,
    LeaseExitSubmit,
    LeaseExitWithdraw,
    LeaseSchedulePreview,
    LeaseUpdate,
    LeaseVersionCommand,
)
from app.shared.deps import TenantContext, get_tenant_context, require_permissions
from app.shared.response import ok

router = APIRouter(tags=["Leases"])


def _svc(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> LeaseService:
    """功能说明：构造 LeaseService。"""

    return LeaseService(db, ctx)


def _lifecycle_svc(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> ContractLifecycleService:
    return ContractLifecycleService(db, ctx)


@router.get(
    "/leases/summary",
    dependencies=[Depends(require_permissions("lease:read"))],
)
def get_lease_summary(
    park_id: Optional[int] = None,
    as_of: Optional[str] = None,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    day = svc._date(as_of, "as_of") if as_of else None
    return ok(svc.summary(park_id=park_id, as_of=day))


@router.get(
    "/leases/selectors",
    dependencies=[Depends(require_permissions("lease:read"))],
)
def get_lease_selectors(
    park_id: Optional[int] = None,
    keyword: Optional[str] = Query(default=None, max_length=100),
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(svc.selectors(park_id=park_id, keyword=keyword))


@router.get(
    "/parties/{party_id}/lease-profile",
    dependencies=[Depends(require_permissions("lease:read"))],
)
def get_party_lease_profile(
    party_id: int,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(svc.party_profile(party_id))


@router.get(
    "/leases/{contract_id}/lifecycle",
    dependencies=[Depends(require_permissions("lease:read"))],
)
def get_lease_lifecycle(
    contract_id: int, svc: ContractLifecycleService = Depends(_lifecycle_svc)
) -> dict:
    return ok(svc.detail(contract_id))


@router.post(
    "/leases/{contract_id}/schedule-preview",
    dependencies=[Depends(require_permissions("lease:read"))],
)
def preview_lease_schedule(
    contract_id: int,
    body: LeaseSchedulePreview,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    charges = [row.model_dump() for row in body.charges] if body.charges is not None else None
    return ok(
        svc.preview_schedule(
            contract_id,
            expected_version=body.expected_version,
            charges=charges,
        )
    )


@router.put("/leases/{contract_id}/charges")
def replace_lease_charges(
    contract_id: int,
    body: LeaseChargeReplace,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.replace_draft_charges(
            contract_id,
            expected_version=body.expected_version,
            charges=[row.model_dump() for row in body.charges],
        ),
        message="updated",
    )


@router.post("/leases/{contract_id}/lifecycle/submit")
def submit_lease_v2(
    contract_id: int,
    body: LeaseVersionCommand,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.submit(
            contract_id,
            expected_version=body.expected_version,
            remark=body.remark,
        ),
        message="submitted",
    )


@router.post("/leases/{contract_id}/lifecycle/approve")
def approve_lease_v2(
    contract_id: int,
    body: LeaseApprovalCommand,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.decide(
            contract_id,
            approval_id=body.approval_id,
            approve=True,
            expected_version=body.expected_version,
            remark=body.remark,
            override_reason=body.override_reason,
        ),
        message="approved",
    )


@router.post("/leases/{contract_id}/lifecycle/reject")
def reject_lease_v2(
    contract_id: int,
    body: LeaseApprovalCommand,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.decide(
            contract_id,
            approval_id=body.approval_id,
            approve=False,
            expected_version=body.expected_version,
            remark=body.remark,
            override_reason=body.override_reason,
        ),
        message="rejected",
    )


@router.post("/leases/{contract_id}/lifecycle/withdraw")
def withdraw_lease_v2(
    contract_id: int,
    body: LeaseApprovalCommand,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.withdraw(
            contract_id,
            approval_id=body.approval_id,
            expected_version=body.expected_version,
            remark=body.remark,
        ),
        message="withdrawn",
    )


@router.post("/leases/{contract_id}/documents")
def add_lease_document(
    contract_id: int,
    body: LeaseDocumentCreate,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.add_document(
            contract_id,
            expected_version=body.expected_version,
            attachment_id=body.attachment_id,
            document_type=body.document_type,
            checksum=body.checksum,
            is_main=body.is_main,
            exit_settlement_id=body.exit_settlement_id,
        ),
        message="created",
    )


@router.post("/leases/{contract_id}/documents/{document_id}/approve")
def approve_lease_document(
    contract_id: int,
    document_id: int,
    body: LeaseDocumentCommand,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.advance_document(
            contract_id,
            document_id,
            expected_version=body.expected_version,
            target_status="APPROVED",
        ),
        message="approved",
    )


@router.post("/leases/{contract_id}/documents/{document_id}/sign")
def sign_lease_document(
    contract_id: int,
    document_id: int,
    body: LeaseDocumentCommand,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.advance_document(
            contract_id,
            document_id,
            expected_version=body.expected_version,
            target_status="SIGNED",
        ),
        message="signed",
    )


@router.post("/leases/{contract_id}/lifecycle/activate")
def activate_lease_v2(
    contract_id: int,
    body: LeaseDocumentCommand,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.activate(contract_id, expected_version=body.expected_version),
        message="activated",
    )


@router.post("/leases/{contract_id}/changes")
def create_lease_change(
    contract_id: int,
    body: LeaseChangeCreate,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.create_change(
            contract_id,
            expected_version=body.expected_version,
            change_type=body.change_type,
            effective_date=body.effective_date,
            reason=body.reason,
            proposed_snapshot=body.proposed_snapshot,
            target_party_eligible=body.target_party_eligible,
        ),
        message="created",
    )


@router.put("/lease-changes/{change_id}")
def edit_lease_change(
    change_id: int,
    body: LeaseChangeEdit,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.edit_change(
            change_id,
            expected_version=body.expected_version,
            change_type=body.change_type,
            effective_date=body.effective_date,
            reason=body.reason,
            proposed_snapshot=body.proposed_snapshot,
            target_party_eligible=body.target_party_eligible,
        ),
        message="updated",
    )


@router.post("/lease-changes/apply-due")
def apply_due_lease_changes(
    body: LeaseApplyDue,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    as_of = svc._date(body.as_of, "as_of") if body.as_of else None
    return ok(svc.apply_due(as_of=as_of, limit=body.limit), message="processed")


@router.post("/lease-changes/{change_id}/submit")
def submit_lease_change(
    change_id: int,
    body: LeaseVersionCommand,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.submit_change(
            change_id,
            expected_version=body.expected_version,
            remark=body.remark,
        ),
        message="submitted",
    )


@router.post("/lease-changes/{change_id}/approve")
def approve_lease_change(
    change_id: int,
    body: LeaseChangeDecision,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.decide_change(
            change_id,
            approve=True,
            expected_version=body.expected_version,
            remark=body.remark,
            override_reason=body.override_reason,
        ),
        message="approved",
    )


@router.post("/lease-changes/{change_id}/reject")
def reject_lease_change(
    change_id: int,
    body: LeaseChangeDecision,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.decide_change(
            change_id,
            approve=False,
            expected_version=body.expected_version,
            remark=body.remark,
            override_reason=body.override_reason,
        ),
        message="rejected",
    )


@router.post("/lease-changes/{change_id}/withdraw")
def withdraw_lease_change(
    change_id: int,
    body: LeaseVersionCommand,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.withdraw_change(
            change_id,
            expected_version=body.expected_version,
            remark=body.remark,
        ),
        message="withdrawn",
    )


@router.post("/lease-changes/{change_id}/cancel")
def cancel_lease_change(
    change_id: int,
    body: LeaseVersionCommand,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.cancel_change(
            change_id,
            expected_version=body.expected_version,
            remark=body.remark,
        ),
        message="cancelled",
    )


@router.post("/lease-changes/{change_id}/apply")
def apply_lease_change(
    change_id: int,
    body: LeaseChangeApply,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    as_of = svc._date(body.as_of, "as_of") if body.as_of else None
    return ok(
        svc.apply_change(
            change_id,
            expected_version=body.expected_version,
            idempotency_key=body.idempotency_key,
            as_of=as_of,
        ),
        message="applied",
    )


@router.post("/leases/{contract_id}/exit-settlements")
def create_lease_exit(
    contract_id: int,
    body: LeaseExitCreate,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.create_exit(
            contract_id,
            expected_version=body.expected_version,
            handover_date=body.handover_date,
            inspection_summary=body.inspection_summary,
        ),
        message="created",
    )


@router.put("/lease-exit-settlements/{settlement_id}")
def edit_lease_exit(
    settlement_id: int,
    body: LeaseExitEdit,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.edit_exit(
            settlement_id,
            expected_version=body.expected_version,
            meter_readings=body.meter_readings,
            items=[row.model_dump() for row in body.items],
            inspection_summary=body.inspection_summary,
        ),
        message="updated",
    )


@router.post("/lease-exit-settlements/{settlement_id}/submit")
def submit_lease_exit(
    settlement_id: int,
    body: LeaseExitSubmit,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.submit_exit(
            settlement_id,
            expected_version=body.expected_version,
            contract_expected_version=body.contract_expected_version,
            remark=body.remark,
        ),
        message="submitted",
    )


@router.post("/lease-exit-settlements/{settlement_id}/approve")
def approve_lease_exit(
    settlement_id: int,
    body: LeaseExitDecision,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.decide_exit(
            settlement_id,
            approve=True,
            expected_version=body.expected_version,
            remark=body.remark,
            override_reason=body.override_reason,
        ),
        message="approved",
    )


@router.post("/lease-exit-settlements/{settlement_id}/withdraw")
def withdraw_lease_exit(
    settlement_id: int,
    body: LeaseExitWithdraw,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.withdraw_exit(
            settlement_id,
            expected_version=body.expected_version,
            contract_expected_version=body.contract_expected_version,
            remark=body.remark,
        ),
        message="withdrawn",
    )


@router.post("/lease-exit-settlements/{settlement_id}/reject")
def reject_lease_exit(
    settlement_id: int,
    body: LeaseExitDecision,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.decide_exit(
            settlement_id,
            approve=False,
            expected_version=body.expected_version,
            remark=body.remark,
            override_reason=body.override_reason,
        ),
        message="rejected",
    )


@router.post("/lease-exit-settlements/{settlement_id}/clearance")
def confirm_lease_exit_clearance(
    settlement_id: int,
    body: LeaseExitClearance,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.confirm_clearance(
            settlement_id,
            expected_version=body.expected_version,
            evidence_attachment_id=body.evidence_attachment_id,
            reference=body.reference,
            reason=body.reason,
        ),
        message="confirmed",
    )


@router.post("/lease-exit-settlements/{settlement_id}/close")
def close_lease_exit(
    settlement_id: int,
    body: LeaseExitClose,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    return ok(
        svc.close_exit(
            settlement_id,
            expected_version=body.expected_version,
            contract_expected_version=body.contract_expected_version,
            idempotency_key=body.idempotency_key,
            breached=body.breached,
        ),
        message="closed",
    )


@router.get("/leases", dependencies=[Depends(require_permissions("lease:read"))])
def list_leases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
    park_id: Optional[int] = None,
    party_id: Optional[int] = None,
    contract_type: Optional[str] = None,
    approval_status: Optional[str] = None,
    change_status: Optional[str] = None,
    exit_status: Optional[str] = None,
    keyword: Optional[str] = Query(default=None, max_length=100),
    end_from: Optional[str] = None,
    end_to: Optional[str] = None,
    svc: LeaseService = Depends(_svc),
) -> dict:
    """功能说明：
        GET /leases 分页列出可见合同。

    业务职责：
        Interface；需 lease:read；park scope 由 Service/仓储强制。

    输入参数：
        page/page_size/status/park_id/party_id。

    返回结果：
        envelope 分页结构。

    异常说明：
        401/403 鉴权。

    业务规则：
        空 park scope 不表示全园。
    """

    return ok(
        svc.list_contracts(
            page=page,
            page_size=page_size,
            status=status,
            park_id=park_id,
            party_id=party_id,
            contract_type=contract_type,
            approval_status=approval_status,
            change_status=change_status,
            exit_status=exit_status,
            keyword=keyword,
            end_from=svc._parse_date(end_from, "end_from") if end_from else None,
            end_to=svc._parse_date(end_to, "end_to") if end_to else None,
        )
    )


@router.post("/leases")
def create_lease(
    body: LeaseCreate,
    svc: LeaseService = Depends(_svc),
    lifecycle: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    """功能说明：
        POST /leases 创建 DRAFT 合同。

    业务职责：
        Interface；写权限在 Service（lease:write）。

    输入参数：
        body：LeaseCreate。

    返回结果：
        创建后详情。

    异常说明：
        业务 AppError。

    业务规则：
        deposit 仅字段；不含 Bill/Payment。
    """

    data = body.model_dump()
    if data.get("charges") is not None:
        return ok(lifecycle.create_draft(data), message="created")
    return ok(svc.create_contract(data), message="created")


@router.get("/leases/{contract_id}", dependencies=[Depends(require_permissions("lease:read"))])
def get_lease(contract_id: int, svc: LeaseService = Depends(_svc)) -> dict:
    """功能说明：
        GET /leases/{id} 合同详情。

    业务职责：
        Interface；需 lease:read。

    业务规则：
        跨租户/scope 外 404。
    """

    return ok(svc.get_contract(contract_id))


@router.patch("/leases/{contract_id}")
def update_lease(
    contract_id: int,
    body: LeaseUpdate,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    """功能说明：
        PATCH /leases/{id} 更新可编辑合同。

    业务职责：
        Interface。
    """

    data = body.model_dump(exclude_unset=True)
    expected_version = int(data.pop("expected_version"))
    return ok(svc.update_draft(contract_id, expected_version=expected_version, data=data), message="updated")


@router.post("/leases/{contract_id}/submit")
def submit_lease(
    contract_id: int,
    body: LeaseVersionCommand,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    """功能说明：
        POST .../submit DRAFT→PENDING_ACTIVE。

    业务职责：
        Interface；需 lease:activate（Service）。
    """

    return ok(
        svc.submit(contract_id, expected_version=body.expected_version, remark=body.remark),
        message="submitted",
    )


@router.post("/leases/{contract_id}/reject")
def reject_lease(
    contract_id: int,
    body: LeaseApprovalCommand,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    """功能说明：
        POST .../reject PENDING_ACTIVE→DRAFT。
    """

    return ok(
        svc.decide(
            contract_id,
            approval_id=body.approval_id,
            expected_version=body.expected_version,
            approve=False,
            remark=body.remark,
            override_reason=body.override_reason,
        ),
        message="rejected",
    )


@router.post("/leases/{contract_id}/cancel")
def cancel_lease(
    contract_id: int,
    body: LeaseVersionCommand,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    """功能说明：
        POST .../cancel 取消草稿/待激活合同。
    """

    return ok(svc.cancel_draft(contract_id, expected_version=body.expected_version), message="cancelled")


@router.post("/leases/{contract_id}/activate")
def activate_lease(
    contract_id: int,
    body: LeaseVersionCommand,
    svc: ContractLifecycleService = Depends(_lifecycle_svc),
) -> dict:
    """功能说明：
        POST .../activate 激活合同并投影占用。

    业务规则：
        冲突检测；无出账/押金退还。
    """

    return ok(svc.activate(contract_id, expected_version=body.expected_version), message="activated")


@router.post("/leases/{contract_id}/terminate")
def terminate_lease(contract_id: int) -> dict:
    """功能说明：
        POST .../terminate 正常终止并释放占用。
    """

    raise AppError(
        "已生效合同必须通过退租结算关闭",
        code="LEASE_EXIT_SETTLEMENT_REQUIRED",
        status_code=409,
    )


@router.post("/leases/{contract_id}/breach")
def breach_lease(contract_id: int) -> dict:
    """功能说明：
        POST .../breach 违约终止并释放占用。
    """

    raise AppError(
        "违约退出必须通过退租结算关闭",
        code="LEASE_EXIT_SETTLEMENT_REQUIRED",
        status_code=409,
    )

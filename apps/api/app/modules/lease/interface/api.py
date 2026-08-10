"""功能说明：
    Lease REST 路由。

业务职责：
    Interface；鉴权与 envelope；业务在 LeaseService。
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.lease.application.lease_service import LeaseService
from app.modules.lease.interface.schemas import LeaseCreate, LeaseUpdate
from app.shared.deps import TenantContext, get_tenant_context, require_permissions
from app.shared.response import ok

router = APIRouter(tags=["Leases"])


def _svc(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> LeaseService:
    """功能说明：构造 LeaseService。"""

    return LeaseService(db, ctx)


@router.get("/leases", dependencies=[Depends(require_permissions("lease:read"))])
def list_leases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
    park_id: Optional[int] = None,
    party_id: Optional[int] = None,
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
        )
    )


@router.post("/leases")
def create_lease(body: LeaseCreate, svc: LeaseService = Depends(_svc)) -> dict:
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
    contract_id: int, body: LeaseUpdate, svc: LeaseService = Depends(_svc)
) -> dict:
    """功能说明：
        PATCH /leases/{id} 更新可编辑合同。

    业务职责：
        Interface。
    """

    return ok(
        svc.update_contract(contract_id, body.model_dump(exclude_unset=True)),
        message="updated",
    )


@router.post("/leases/{contract_id}/submit")
def submit_lease(contract_id: int, svc: LeaseService = Depends(_svc)) -> dict:
    """功能说明：
        POST .../submit DRAFT→PENDING_ACTIVE。

    业务职责：
        Interface；需 lease:activate（Service）。
    """

    return ok(svc.submit(contract_id), message="submitted")


@router.post("/leases/{contract_id}/reject")
def reject_lease(contract_id: int, svc: LeaseService = Depends(_svc)) -> dict:
    """功能说明：
        POST .../reject PENDING_ACTIVE→DRAFT。
    """

    return ok(svc.reject(contract_id), message="rejected")


@router.post("/leases/{contract_id}/cancel")
def cancel_lease(contract_id: int, svc: LeaseService = Depends(_svc)) -> dict:
    """功能说明：
        POST .../cancel 取消草稿/待激活合同。
    """

    return ok(svc.cancel(contract_id), message="cancelled")


@router.post("/leases/{contract_id}/activate")
def activate_lease(contract_id: int, svc: LeaseService = Depends(_svc)) -> dict:
    """功能说明：
        POST .../activate 激活合同并投影占用。

    业务规则：
        冲突检测；无出账/押金退还。
    """

    return ok(svc.activate(contract_id), message="activated")


@router.post("/leases/{contract_id}/terminate")
def terminate_lease(contract_id: int, svc: LeaseService = Depends(_svc)) -> dict:
    """功能说明：
        POST .../terminate 正常终止并释放占用。
    """

    return ok(svc.terminate(contract_id, breached=False), message="terminated")


@router.post("/leases/{contract_id}/breach")
def breach_lease(contract_id: int, svc: LeaseService = Depends(_svc)) -> dict:
    """功能说明：
        POST .../breach 违约终止并释放占用。
    """

    return ok(svc.terminate(contract_id, breached=True), message="breached")

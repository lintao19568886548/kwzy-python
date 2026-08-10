"""功能说明：
    Party REST 接口路由。

业务职责：
    Interface 层；鉴权依赖、参数绑定与 envelope 包装，业务在 PartyService。
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.party.application.party_service import PartyService
from app.modules.party.interface.schemas import (
    AddressCreate,
    AddressUpdate,
    ContactCreate,
    ContactUpdate,
    PartyCreate,
    PartyUpdate,
    RelationCreate,
    RestoreBody,
    RiskReasonBody,
    RoleCreate,
)
from app.shared.deps import TenantContext, get_tenant_context, require_permissions
from app.shared.response import ok

router = APIRouter(tags=["Parties"])


def _svc(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> PartyService:
    """功能说明：
        构造 PartyService 依赖。

    业务职责：
        私有 DI 工厂；注入 Session 与 TenantContext。
    """

    return PartyService(db, ctx)


@router.get("/parties", dependencies=[Depends(require_permissions("party:read"))])
def list_parties(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    risk_status: Optional[str] = None,
    party_type: Optional[str] = None,
    include_archived: bool = False,
    park_id: Optional[int] = None,
    svc: PartyService = Depends(_svc),
) -> dict:
    """功能说明：
        GET /parties 分页列出当前可见主体。

    业务职责：
        Interface；需 party:read；可见性由 Service/仓储 park scope 决定。

    输入参数：
        page/page_size：分页。
        keyword/status/risk_status/party_type/include_archived/park_id：筛选。

    返回结果：
        统一 envelope，data 含 total/page/page_size/items；items 不含 addresses。

    异常说明：
        401/403：鉴权与权限（依赖注入）。

    业务规则：
        1. 强制 tenant 隔离与 park scope。
        2. 列表不嵌套 PERSON/ORGANIZATION 地址。
    """

    return ok(
        svc.list_parties(
            page=page,
            page_size=page_size,
            keyword=keyword,
            status=status,
            risk_status=risk_status,
            party_type=party_type,
            include_archived=include_archived,
            park_id=park_id,
        )
    )


@router.post("/parties")
def create_party(
    body: PartyCreate,
    ctx: TenantContext = Depends(get_tenant_context),
    svc: PartyService = Depends(_svc),
) -> dict:
    """功能说明：
        POST /parties 创建主体。

    业务职责：
        Interface；写权限在 Service（write vs manage_unscoped）。

    输入参数：
        body：PartyCreate。

    返回结果：
        envelope，data 为创建后详情。

    异常说明：
        AppError 各业务码经全局处理器返回。

    业务规则：
        无 initial_park_relation 时需 party:manage_unscoped。
    """

    # permission enforced in service (unscoped vs write)
    data = svc.create_party(body.model_dump())
    return ok(data, message="created")


@router.get("/parties/{party_id}", dependencies=[Depends(require_permissions("party:read"))])
def get_party(party_id: int, svc: PartyService = Depends(_svc)) -> dict:
    """功能说明：
        GET /parties/{party_id} 获取主体详情。

    业务职责：
        Interface；需 party:read。

    输入参数：
        party_id：主体 ID。

    返回结果：
        envelope；含 roles 与 ACTIVE park_relations；不含 addresses。

    异常说明：
        PARTY_NOT_FOUND：不可见或不存在。

    业务规则：
        跨租户/scope 外统一 404；不返回地址子资源。
    """

    return ok(svc.get_party(party_id))


@router.patch("/parties/{party_id}")
def update_party(
    party_id: int,
    body: PartyUpdate,
    svc: PartyService = Depends(_svc),
) -> dict:
    """功能说明：
        PATCH /parties/{party_id} 更新主体。

    业务职责：
        Interface；写权限由 Service 判定。

    输入参数：
        party_id：主体 ID。
        body：PartyUpdate（部分字段）。

    返回结果：
        envelope，更新后详情。

    异常说明：
        PERMISSION_DENIED / PARTY_NOT_FOUND / 校验类错误。

    业务规则：
        不可经本接口改 risk_status。
    """

    return ok(svc.update_party(party_id, body.model_dump(exclude_unset=True)), message="updated")


@router.post("/parties/{party_id}/archive")
def archive_party(party_id: int, svc: PartyService = Depends(_svc)) -> dict:
    """功能说明：
        POST /parties/{party_id}/archive 归档主体。

    业务职责：
        Interface；状态机由 Service/Domain 校验。

    输入参数：
        party_id：主体 ID。

    返回结果：
        envelope，归档后详情。

    异常说明：
        PARTY_STATUS_INVALID 等。

    业务规则：
        需写权限；不物理删除子资源。
    """

    return ok(svc.archive_party(party_id), message="archived")


@router.post("/parties/{party_id}/restore")
def restore_party(
    party_id: int,
    body: RestoreBody | None = None,
    svc: PartyService = Depends(_svc),
) -> dict:
    """功能说明：
        POST /parties/{party_id}/restore 恢复归档主体。

    业务职责：
        Interface。

    输入参数：
        party_id：主体 ID。
        body：可选 target_status，默认 ACTIVE。

    返回结果：
        envelope，恢复后详情。

    异常说明：
        PARTY_STATUS_INVALID / CREDIT_CODE_DUPLICATE 等。

    业务规则：
        恢复不清除 risk_status/黑名单字段。
    """

    target = (body.target_status if body else "ACTIVE") or "ACTIVE"
    return ok(svc.restore_party(party_id, target_status=target), message="restored")


@router.get("/parties/{party_id}/roles", dependencies=[Depends(require_permissions("party:read"))])
def list_roles(party_id: int, svc: PartyService = Depends(_svc)) -> dict:
    """功能说明：
        GET /parties/{party_id}/roles 列出业务角色。

    业务职责：
        Interface；需 party:read。

    输入参数：
        party_id：主体 ID。

    返回结果：
        envelope，角色列表。

    异常说明：
        PARTY_NOT_FOUND。

    业务规则：
        主体须可见。
    """

    return ok(svc.list_roles(party_id))


@router.post("/parties/{party_id}/roles")
def add_role(party_id: int, body: RoleCreate, svc: PartyService = Depends(_svc)) -> dict:
    """功能说明：
        POST /parties/{party_id}/roles 新增或重新激活业务角色。

    业务职责：
        Interface。

    输入参数：
        party_id：主体 ID。
        body.role_code：角色码。

    返回结果：
        envelope，角色摘要。

    异常说明：
        PERMISSION_DENIED / VALIDATION_ERROR 等。

    业务规则：
        需写权限。
    """

    return ok(svc.add_role(party_id, body.role_code), message="created")


@router.post("/parties/{party_id}/roles/{role_id}/deactivate")
def deactivate_role(party_id: int, role_id: int, svc: PartyService = Depends(_svc)) -> dict:
    """功能说明：
        POST .../roles/{role_id}/deactivate 停用业务角色。

    业务职责：
        Interface。

    输入参数：
        party_id/role_id：路径参数。

    返回结果：
        envelope，角色摘要。

    异常说明：
        PARTY_ROLE_IN_USE：仍有有效园区关系。

    业务规则：
        须先结束占用关系。
    """

    return ok(svc.deactivate_role(party_id, role_id), message="deactivated")


@router.get(
    "/parties/{party_id}/park-relations",
    dependencies=[Depends(require_permissions("party:read"))],
)
def list_relations(party_id: int, svc: PartyService = Depends(_svc)) -> dict:
    """功能说明：
        GET /parties/{party_id}/park-relations 列出园区关系。

    业务职责：
        Interface；需 party:read。

    输入参数：
        party_id：主体 ID。

    返回结果：
        envelope，关系列表。

    异常说明：
        PARTY_NOT_FOUND。

    业务规则：
        主体须可见。
    """

    return ok(svc.list_relations(party_id))


@router.post("/parties/{party_id}/park-relations")
def add_relation(
    party_id: int, body: RelationCreate, svc: PartyService = Depends(_svc)
) -> dict:
    """功能说明：
        POST /parties/{party_id}/park-relations 添加园区关系。

    业务职责：
        Interface；park scope 与首关联权限在 Service。

    输入参数：
        party_id：主体 ID。
        body.park_id / body.party_role_id。

    返回结果：
        envelope，关系摘要。

    异常说明：
        PARK_SCOPE_DENIED / PARTY_PARK_RELATION_DUPLICATE 等。

    业务规则：
        首个园区关系需 manage_unscoped。
    """

    return ok(
        svc.add_relation(party_id, body.park_id, body.party_role_id),
        message="created",
    )


@router.post("/parties/{party_id}/park-relations/{relation_id}/end")
def end_relation(party_id: int, relation_id: int, svc: PartyService = Depends(_svc)) -> dict:
    """功能说明：
        POST .../park-relations/{relation_id}/end 结束园区关系。

    业务职责：
        Interface。

    输入参数：
        party_id/relation_id：路径参数。

    返回结果：
        envelope，关系状态。

    异常说明：
        VALIDATION_ERROR：关系不存在。

    业务规则：
        需写权限；软状态 ENDED。
    """

    return ok(svc.end_relation(party_id, relation_id), message="ended")


@router.get(
    "/parties/{party_id}/contacts",
    dependencies=[Depends(require_permissions("party:read"))],
)
def list_contacts(party_id: int, svc: PartyService = Depends(_svc)) -> dict:
    """功能说明：
        GET /parties/{party_id}/contacts 列出联系人。

    业务职责：
        Interface；需 party:read。

    输入参数：
        party_id：主体 ID。

    返回结果：
        envelope，联系人列表。

    异常说明：
        PARTY_NOT_FOUND。

    业务规则：
        主体须可见。
    """

    return ok(svc.list_contacts(party_id))


@router.post("/parties/{party_id}/contacts")
def create_contact(
    party_id: int, body: ContactCreate, svc: PartyService = Depends(_svc)
) -> dict:
    """功能说明：
        POST /parties/{party_id}/contacts 创建联系人。

    业务职责：
        Interface。

    输入参数：
        party_id：主体 ID。
        body：ContactCreate。

    返回结果：
        envelope，联系人摘要。

    异常说明：
        PERMISSION_DENIED 等。

    业务规则：
        需写权限。
    """

    return ok(svc.create_contact(party_id, body.model_dump()), message="created")


@router.patch("/parties/{party_id}/contacts/{contact_id}")
def update_contact(
    party_id: int,
    contact_id: int,
    body: ContactUpdate,
    svc: PartyService = Depends(_svc),
) -> dict:
    """功能说明：
        PATCH .../contacts/{contact_id} 更新联系人。

    业务职责：
        Interface。

    输入参数：
        party_id/contact_id：路径参数。
        body：ContactUpdate。

    返回结果：
        envelope，更新摘要。

    异常说明：
        CONTACT_NOT_FOUND 等。

    业务规则：
        contact 须属于 path party_id。
    """

    return ok(
        svc.update_contact(party_id, contact_id, body.model_dump(exclude_unset=True)),
        message="updated",
    )


@router.delete("/parties/{party_id}/contacts/{contact_id}")
def delete_contact(
    party_id: int, contact_id: int, svc: PartyService = Depends(_svc)
) -> dict:
    """功能说明：
        DELETE .../contacts/{contact_id} 软删联系人。

    业务职责：
        Interface。

    输入参数：
        party_id/contact_id：路径参数。

    返回结果：
        envelope，data=null。

    异常说明：
        CONTACT_PRIMARY_REQUIRED：仍有其他联系人时不可直接删主联系人。

    业务规则：
        软删除。
    """

    svc.delete_contact(party_id, contact_id)
    return ok(None, message="deleted")


@router.get(
    "/parties/{party_id}/addresses",
    dependencies=[Depends(require_permissions("party:read"))],
)
def list_addresses(party_id: int, svc: PartyService = Depends(_svc)) -> dict:
    """功能说明：
        GET /parties/{party_id}/addresses 列出地址。

    业务职责：
        Interface；PERSON v1 由 Application 返回 403 PERSON_ADDRESS_FORBIDDEN。

    输入参数：
        party_id：主体 ID。

    返回结果：
        ORGANIZATION：地址列表 envelope；PERSON：错误 envelope data=null。

    异常说明：
        PERSON_ADDRESS_FORBIDDEN：PERSON 主体（含库中已有行）。
        PARTY_NOT_FOUND：主体不可见。

    业务规则：
        1. 禁止仅 Router 拦截；Service 在查表前拒绝。
        2. 错误体与日志不得含完整地址值。
    """

    return ok(svc.list_addresses(party_id))


@router.post("/parties/{party_id}/addresses")
def create_address(
    party_id: int, body: AddressCreate, svc: PartyService = Depends(_svc)
) -> dict:
    """功能说明：
        POST /parties/{party_id}/addresses 创建地址。

    业务职责：
        Interface；ORGANIZATION 可写；PERSON 由 Application 拒绝。

    输入参数：
        party_id：主体 ID。
        body：AddressCreate。

    返回结果：
        envelope，摘要字段 id/address_type/is_primary。

    异常说明：
        PERSON_ADDRESS_FORBIDDEN / ADDRESS_PRIMARY_CONFLICT 等。

    业务规则：
        审计 detail 不含完整 street/detail。
    """

    return ok(svc.create_address(party_id, body.model_dump()), message="created")


@router.patch("/parties/{party_id}/addresses/{address_id}")
def update_address(
    party_id: int,
    address_id: int,
    body: AddressUpdate,
    svc: PartyService = Depends(_svc),
) -> dict:
    """功能说明：
        PATCH .../addresses/{address_id} 更新地址。

    业务职责：
        Interface；PERSON 由 Application 拒绝。

    输入参数：
        party_id/address_id：路径参数（归属双重校验）。
        body：AddressUpdate。

    返回结果：
        envelope，更新摘要。

    异常说明：
        PERSON_ADDRESS_FORBIDDEN / ADDRESS_NOT_FOUND 等。

    业务规则：
        address_id 必须属于 path party_id 与当前租户。
    """

    return ok(
        svc.update_address(party_id, address_id, body.model_dump(exclude_unset=True)),
        message="updated",
    )


@router.delete("/parties/{party_id}/addresses/{address_id}")
def delete_address(
    party_id: int, address_id: int, svc: PartyService = Depends(_svc)
) -> dict:
    """功能说明：
        DELETE .../addresses/{address_id} 软删地址。

    业务职责：
        Interface；PERSON 由 Application 拒绝。

    输入参数：
        party_id/address_id：路径参数。

    返回结果：
        envelope，data=null。

    异常说明：
        PERSON_ADDRESS_FORBIDDEN / ADDRESS_NOT_FOUND。

    业务规则：
        软删除；PERSON 即使存在行亦 403。
    """

    svc.delete_address(party_id, address_id)
    return ok(None, message="deleted")


@router.get(
    "/parties/{party_id}/risk-events",
    dependencies=[Depends(require_permissions("party:risk_read"))],
)
def list_risk_events(party_id: int, svc: PartyService = Depends(_svc)) -> dict:
    """功能说明：
        GET /parties/{party_id}/risk-events 列出风险事件。

    业务职责：
        Interface；路由需 party:risk_read，Service 再次校验。

    输入参数：
        party_id：主体 ID。

    返回结果：
        envelope，事件列表。

    异常说明：
        PERMISSION_DENIED / PARTY_NOT_FOUND。

    业务规则：
        事件只读；主体须可见。
    """

    return ok(svc.list_risk_events(party_id))


@router.post(
    "/parties/{party_id}/blacklist",
    dependencies=[Depends(require_permissions("party:risk_manage"))],
)
def blacklist(
    party_id: int, body: RiskReasonBody, svc: PartyService = Depends(_svc)
) -> dict:
    """功能说明：
        POST /parties/{party_id}/blacklist 加入黑名单。

    业务职责：
        Interface；需 party:risk_manage。

    输入参数：
        party_id：主体 ID。
        body.reason：原因必填。

    返回结果：
        envelope，更新后主体详情。

    异常说明：
        PARTY_RISK_* / PERMISSION_DENIED。

    业务规则：
        同事务写 risk 事件与审计。
    """

    return ok(svc.blacklist(party_id, body.reason), message="blacklisted")


@router.post(
    "/parties/{party_id}/remove-blacklist",
    dependencies=[Depends(require_permissions("party:risk_manage"))],
)
def remove_blacklist(
    party_id: int, body: RiskReasonBody, svc: PartyService = Depends(_svc)
) -> dict:
    """功能说明：
        POST /parties/{party_id}/remove-blacklist 解除黑名单。

    业务职责：
        Interface；需 party:risk_manage。

    输入参数：
        party_id：主体 ID。
        body.reason：解除原因必填。

    返回结果：
        envelope，更新后主体详情。

    异常说明：
        PARTY_RISK_* / PERMISSION_DENIED。

    业务规则：
        同事务写 risk 事件与审计。
    """

    return ok(svc.remove_blacklist(party_id, body.reason), message="unblacklisted")

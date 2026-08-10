"""功能说明：
    Party HTTP 请求体 Pydantic Schema。

业务职责：
    Interface 层；校验入参形态，不承载业务权限与租户逻辑。
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class InitialParkRelation(BaseModel):
    """功能说明：
        创建主体时可选的初始园区关系。

    业务职责：
        Interface DTO；映射 initial_park_relation。

    输入参数：
        park_id：园区 ID，必填。
        party_role_id：已有角色 ID，可空。
        role_code：新建角色码，可空（与 party_role_id 二选一语义由 Service 处理）。

    返回结果：
        无（请求体模型）。

    异常说明：
        Pydantic 校验失败 → 422 VALIDATION_ERROR。

    业务规则：
        实际写权限与 park scope 由 Application 强制。
    """

    park_id: int
    party_role_id: Optional[int] = None
    role_code: Optional[str] = None


class PartyCreate(BaseModel):
    """功能说明：
        创建主体请求体。

    业务职责：
        Interface DTO；无主档 park_id/address 字段。

    输入参数：
        name：名称必填。
        party_type：默认 ORGANIZATION。
        credit_code/remark/联系人字段：可选。
        initial_park_relation：可选初始园区关系。

    返回结果：
        无（请求体模型）。

    异常说明：
        Pydantic 校验失败 → 422。

    业务规则：
        无园区关系创建需 party:manage_unscoped（Service 校验）。
    """

    name: str
    party_type: str = "ORGANIZATION"
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    credit_code: Optional[str] = None
    remark: Optional[str] = None
    initial_park_relation: Optional[InitialParkRelation] = None


class PartyUpdate(BaseModel):
    """功能说明：
        部分更新主体请求体。

    业务职责：
        Interface DTO；字段均可选。

    输入参数：
        name/party_type/contact_*/credit_code/remark/status：可选。

    返回结果：
        无（请求体模型）。

    异常说明：
        Pydantic 校验失败 → 422。

    业务规则：
        risk_status 不得经本体更新（Service 拒绝）。
    """

    name: Optional[str] = None
    party_type: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    credit_code: Optional[str] = None
    remark: Optional[str] = None
    status: Optional[str] = None


class RoleCreate(BaseModel):
    """功能说明：
        新增业务角色请求体。

    业务职责：
        Interface DTO。

    输入参数：
        role_code：业务角色码，必填。

    返回结果：
        无。

    异常说明：
        Pydantic 校验失败 → 422。

    业务规则：
        合法枚举由 Domain assert_role_code 校验。
    """

    role_code: str


class RelationCreate(BaseModel):
    """功能说明：
        新增 Party–Park 关系请求体。

    业务职责：
        Interface DTO。

    输入参数：
        park_id：园区 ID。
        party_role_id：本主体下有效角色 ID。

    返回结果：
        无。

    异常说明：
        Pydantic 校验失败 → 422。

    业务规则：
        park scope 与角色归属由 Application 校验。
    """

    park_id: int
    party_role_id: int


class ContactCreate(BaseModel):
    """功能说明：
        创建联系人请求体。

    业务职责：
        Interface DTO。

    输入参数：
        name/phone/email/role_label：可选。
        is_primary：是否主联系人，默认 False。

    返回结果：
        无。

    异常说明：
        Pydantic 校验失败 → 422。

    业务规则：
        主联系人会同步主档 contact_*（Service）。
    """

    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    role_label: Optional[str] = None
    is_primary: bool = False


class ContactUpdate(BaseModel):
    """功能说明：
        更新联系人请求体。

    业务职责：
        Interface DTO；字段均可选。

    输入参数：
        name/phone/email/role_label/is_primary：可选。

    返回结果：
        无。

    异常说明：
        Pydantic 校验失败 → 422。

    业务规则：
        无额外 Interface 层规则。
    """

    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    role_label: Optional[str] = None
    is_primary: Optional[bool] = None


class AddressCreate(BaseModel):
    """功能说明：
        创建地址请求体（ORGANIZATION；PERSON 由 Service 403）。

    业务职责：
        Interface DTO；不在此层判定 party_type。

    输入参数：
        address_type：默认 OTHER。
        行政区划与 street/detail/postal_code：可选。
        is_primary：是否主地址。

    返回结果：
        无。

    异常说明：
        Pydantic 校验失败 → 422。

    业务规则：
        PERSON 主体创建在 Application 返回 PERSON_ADDRESS_FORBIDDEN。
    """

    address_type: str = "OTHER"
    country_code: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    street: Optional[str] = None
    detail: Optional[str] = None
    postal_code: Optional[str] = None
    is_primary: bool = False


class AddressUpdate(BaseModel):
    """功能说明：
        更新地址请求体（ORGANIZATION；PERSON 由 Service 403）。

    业务职责：
        Interface DTO。

    输入参数：
        行政区划与 street/detail/postal_code/is_primary/status：均可选。

    返回结果：
        无。

    异常说明：
        Pydantic 校验失败 → 422。

    业务规则：
        PERSON 主体更新在 Application 返回 PERSON_ADDRESS_FORBIDDEN。
    """

    country_code: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    street: Optional[str] = None
    detail: Optional[str] = None
    postal_code: Optional[str] = None
    is_primary: Optional[bool] = None
    status: Optional[str] = None


class RiskReasonBody(BaseModel):
    """功能说明：
        黑名单/解除黑名单原因请求体。

    业务职责：
        Interface DTO。

    输入参数：
        reason：非空字符串。

    返回结果：
        无。

    异常说明：
        空串 → 422（Field min_length=1）。

    业务规则：
        需 party:risk_manage（路由/Service）。
    """

    reason: str = Field(min_length=1)


class RestoreBody(BaseModel):
    """功能说明：
        恢复归档主体请求体。

    业务职责：
        Interface DTO。

    输入参数：
        target_status：恢复目标状态，默认 ACTIVE。

    返回结果：
        无。

    异常说明：
        Pydantic 校验失败 → 422。

    业务规则：
        合法迁移由 Domain assert_status_transition 校验。
    """

    target_status: str = "ACTIVE"

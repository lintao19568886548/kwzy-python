"""功能说明：
    Party 领域实体定义（纯数据，无 SQLAlchemy / FastAPI）。

业务职责：
    Domain 层；描述入驻方主档与子资源结构，供 Application/Mapper 使用。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class PartyEntity:
    """功能说明：
        入驻方/主体主档领域实体。

    业务职责：
        Domain 模型；租户级主体，无单一 park_id 归属，无模糊主档 address 字段。

    输入参数：
        构造字段见属性：tenant_id/name 等。

    返回结果：
        无（数据类）。

    异常说明：
        无（不变量由 rules 与 Application 校验）。

    业务规则：
        1. 必须带 tenant_id；禁止跨租户共享主档。
        2. party_type 为 ORGANIZATION 或 PERSON。
        3. 地址不在主档承载，见 PartyAddressEntity。
    """

    tenant_id: int
    name: str
    party_type: str = "ORGANIZATION"
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    credit_code: Optional[str] = None
    status: str = "ACTIVE"
    risk_status: str = "NORMAL"
    blacklist_reason: Optional[str] = None
    blacklisted_at: Optional[datetime] = None
    blacklisted_by: Optional[int] = None
    blacklist_removed_at: Optional[datetime] = None
    blacklist_removed_by: Optional[int] = None
    remark: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class PartyRoleEntity:
    """功能说明：
        Party 业务角色领域实体（非 RBAC 权限角色）。

    业务职责：
        Domain 模型；描述 LESSEE 等业务身份。

    输入参数：
        tenant_id/party_id/role_code 等。

    返回结果：
        无（数据类）。

    异常说明：
        无。

    业务规则：
        1. 同一租户下 party_id + role_code 唯一。
        2. 与身份权限码（party:read 等）相互独立。
    """

    tenant_id: int
    party_id: int
    role_code: str
    status: str = "ACTIVE"
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class PartyParkRelationEntity:
    """功能说明：
        Party 与 Park 在某一业务角色下的关联实体。

    业务职责：
        Domain 模型；多对多关系载体，通过 party_role_id 外键关联角色。

    输入参数：
        tenant_id/party_id/park_id/party_role_id 等。

    返回结果：
        无（数据类）。

    异常说明：
        无。

    业务规则：
        1. 可见性与 park scope 依赖有效 ACTIVE 关系。
        2. party_role_id 必须属于同一 party。
    """

    tenant_id: int
    party_id: int
    park_id: int
    party_role_id: int
    status: str = "ACTIVE"
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class PartyContactEntity:
    """功能说明：
        主体联系人领域实体。

    业务职责：
        Domain 模型；支持主联系人标记与软删除。

    输入参数：
        tenant_id/party_id 及联系方式字段。

    返回结果：
        无（数据类）。

    异常说明：
        无。

    业务规则：
        主联系人删除策略由 Application 强制（须先指定替代）。
    """

    tenant_id: int
    party_id: int
    phone: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    role_label: Optional[str] = None
    is_primary: bool = False
    linked_person_party_id: Optional[int] = None
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class PartyAddressEntity:
    """功能说明：
        结构化地址领域实体（独立于主档）。

    业务职责：
        Domain 模型；对应 party_addresses 表事实来源。

    输入参数：
        tenant_id/party_id/address_type 及行政区划与街道字段。

    返回结果：
        无（数据类）。

    异常说明：
        无。

    业务规则：
        1. PERSON 主体在 v1 禁止经 API 读写地址（Application 强制）。
        2. 同 party + address_type 至多一条 ACTIVE primary。
        3. 不在 Party 列表/详情中嵌套返回。
    """

    tenant_id: int
    party_id: int
    address_type: str
    country_code: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    street: Optional[str] = None
    detail: Optional[str] = None
    postal_code: Optional[str] = None
    is_primary: bool = False
    status: str = "ACTIVE"
    deleted_at: Optional[datetime] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class PartyRiskEventEntity:
    """功能说明：
        不可变风险事件领域实体。

    业务职责：
        Domain 模型；只追加、不更新删除。

    输入参数：
        tenant_id/party_id/event_type/前后 risk_status/reason 等。

    返回结果：
        无（数据类）。

    异常说明：
        无。

    业务规则：
        事件与主体 risk_status 变更应在同一事务中写入。
    """

    tenant_id: int
    party_id: int
    event_type: str
    previous_risk_status: str
    new_risk_status: str
    reason: str
    operator_user_id: Optional[int] = None
    request_id: Optional[str] = None
    source: Optional[str] = None
    occurred_at: Optional[datetime] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None

"""功能说明：
    Party ORM 模型与 Domain 实体之间的映射。

业务职责：
    Infrastructure 层；不施加业务权限，仅做字段转换。
"""

from __future__ import annotations

from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.party import (
    Party,
    PartyAddress,
    PartyContact,
    PartyParkRelation,
    PartyRiskEvent,
    PartyRole,
)
from app.modules.party.domain.entities import (
    PartyAddressEntity,
    PartyContactEntity,
    PartyEntity,
    PartyParkRelationEntity,
    PartyRiskEventEntity,
    PartyRoleEntity,
)


class PartyMapper:
    """功能说明：
        Party 主档 ORM ↔ PartyEntity 映射。

    业务职责：
        Infrastructure Mapper；不含租户/权限判断。
    """

    @staticmethod
    def to_entity(m: Party) -> PartyEntity:
        """功能说明：
            ORM Party 转为领域实体。

        业务职责：
            只读映射。

        输入参数：
            m：已加载的 Party ORM。

        返回结果：
            PartyEntity。

        异常说明：
            无。

        业务规则：
            字段一一对应；不查询子资源。
        """

        return PartyEntity(
            id=m.id,
            tenant_id=m.tenant_id,
            party_type=m.party_type,
            name=m.name,
            contact_name=m.contact_name,
            contact_phone=m.contact_phone,
            credit_code=m.credit_code,
            status=m.status,
            risk_status=m.risk_status,
            blacklist_reason=m.blacklist_reason,
            blacklisted_at=m.blacklisted_at,
            blacklisted_by=m.blacklisted_by,
            blacklist_removed_at=m.blacklist_removed_at,
            blacklist_removed_by=m.blacklist_removed_by,
            remark=m.remark,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    @staticmethod
    def new_model(e: PartyEntity) -> Party:
        """功能说明：
            由领域实体构造新的 Party ORM（未 flush）。

        业务职责：
            创建路径映射。

        输入参数：
            e：PartyEntity。

        返回结果：
            未持久化的 Party。

        异常说明：
            无。

        业务规则：
            不设置 id/时间戳（由库与 Mixin 处理）。
        """

        return Party(
            tenant_id=e.tenant_id,
            party_type=e.party_type,
            name=e.name,
            contact_name=e.contact_name,
            contact_phone=e.contact_phone,
            credit_code=e.credit_code,
            status=e.status,
            risk_status=e.risk_status,
            blacklist_reason=e.blacklist_reason,
            blacklisted_at=e.blacklisted_at,
            blacklisted_by=e.blacklisted_by,
            blacklist_removed_at=e.blacklist_removed_at,
            blacklist_removed_by=e.blacklist_removed_by,
            remark=e.remark,
        )

    @staticmethod
    def apply_entity(m: Party, e: PartyEntity) -> Party:
        """功能说明：
            将实体字段写回已有 ORM（更新路径）。

        业务职责：
            变更映射；不提交事务。

        输入参数：
            m：目标 ORM。
            e：源实体。

        返回结果：
            更新后的 m。

        异常说明：
            无。

        业务规则：
            不修改 id/tenant_id/created_at。
        """

        m.party_type = e.party_type
        m.name = e.name
        m.contact_name = e.contact_name
        m.contact_phone = e.contact_phone
        m.credit_code = e.credit_code
        m.status = e.status
        m.risk_status = e.risk_status
        m.blacklist_reason = e.blacklist_reason
        m.blacklisted_at = e.blacklisted_at
        m.blacklisted_by = e.blacklisted_by
        m.blacklist_removed_at = e.blacklist_removed_at
        m.blacklist_removed_by = e.blacklist_removed_by
        m.remark = e.remark
        return m


class PartyRoleMapper:
    """功能说明：
        PartyRole ORM ↔ PartyRoleEntity 映射。

    业务职责：
        Infrastructure Mapper。
    """

    @staticmethod
    def to_entity(m: PartyRole) -> PartyRoleEntity:
        """功能说明：
            ORM 角色转为领域实体。

        业务职责：
            只读映射。

        输入参数：
            m：PartyRole ORM。

        返回结果：
            PartyRoleEntity。

        异常说明：
            无。

        业务规则：
            无额外转换。
        """

        return PartyRoleEntity(
            id=m.id,
            tenant_id=m.tenant_id,
            party_id=m.party_id,
            role_code=m.role_code,
            status=m.status,
            started_at=m.started_at,
            ended_at=m.ended_at,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    @staticmethod
    def new_model(e: PartyRoleEntity) -> PartyRole:
        """功能说明：
            由实体构造新 PartyRole ORM。

        业务职责：
            创建路径映射。

        输入参数：
            e：PartyRoleEntity。

        返回结果：
            未持久化的 PartyRole。

        异常说明：
            无。

        业务规则：
            无。
        """

        return PartyRole(
            tenant_id=e.tenant_id,
            party_id=e.party_id,
            role_code=e.role_code,
            status=e.status,
            started_at=e.started_at,
            ended_at=e.ended_at,
        )


class PartyParkRelationMapper:
    """功能说明：
        PartyParkRelation ORM ↔ 领域实体映射。

    业务职责：
        Infrastructure Mapper。
    """

    @staticmethod
    def to_entity(m: PartyParkRelation) -> PartyParkRelationEntity:
        """功能说明：
            ORM 园区关系转为领域实体。

        业务职责：
            只读映射。

        输入参数：
            m：PartyParkRelation。

        返回结果：
            PartyParkRelationEntity。

        异常说明：
            无。

        业务规则：
            无。
        """

        return PartyParkRelationEntity(
            id=m.id,
            tenant_id=m.tenant_id,
            party_id=m.party_id,
            park_id=m.park_id,
            party_role_id=m.party_role_id,
            status=m.status,
            started_at=m.started_at,
            ended_at=m.ended_at,
            deleted_at=m.deleted_at,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    @staticmethod
    def new_model(e: PartyParkRelationEntity) -> PartyParkRelation:
        """功能说明：
            由实体构造新园区关系 ORM。

        业务职责：
            创建路径映射。

        输入参数：
            e：PartyParkRelationEntity。

        返回结果：
            未持久化的 PartyParkRelation。

        异常说明：
            无。

        业务规则：
            无。
        """

        return PartyParkRelation(
            tenant_id=e.tenant_id,
            party_id=e.party_id,
            park_id=e.park_id,
            party_role_id=e.party_role_id,
            status=e.status,
            started_at=e.started_at,
            ended_at=e.ended_at,
            deleted_at=e.deleted_at,
        )


class PartyContactMapper:
    """功能说明：
        PartyContact ORM ↔ 领域实体映射。

    业务职责：
        Infrastructure Mapper。
    """

    @staticmethod
    def to_entity(m: PartyContact) -> PartyContactEntity:
        """功能说明：
            ORM 联系人转为领域实体。

        业务职责：
            只读映射；布尔字段显式 bool()。

        输入参数：
            m：PartyContact。

        返回结果：
            PartyContactEntity。

        异常说明：
            无。

        业务规则：
            无。
        """

        return PartyContactEntity(
            id=m.id,
            tenant_id=m.tenant_id,
            party_id=m.party_id,
            name=m.name,
            phone=m.phone,
            email=m.email,
            role_label=m.role_label,
            is_primary=bool(m.is_primary),
            linked_person_party_id=m.linked_person_party_id,
            is_deleted=bool(m.is_deleted),
            deleted_at=m.deleted_at,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    @staticmethod
    def new_model(e: PartyContactEntity) -> PartyContact:
        """功能说明：
            由实体构造新联系人 ORM。

        业务职责：
            创建路径映射。

        输入参数：
            e：PartyContactEntity。

        返回结果：
            未持久化的 PartyContact。

        异常说明：
            无。

        业务规则：
            无。
        """

        return PartyContact(
            tenant_id=e.tenant_id,
            party_id=e.party_id,
            name=e.name,
            phone=e.phone,
            email=e.email,
            role_label=e.role_label,
            is_primary=e.is_primary,
            linked_person_party_id=e.linked_person_party_id,
            is_deleted=e.is_deleted,
            deleted_at=e.deleted_at,
        )


class PartyAddressMapper:
    """功能说明：
        PartyAddress ORM ↔ 领域实体映射。

    业务职责：
        Infrastructure Mapper；不执行 PERSON 地址拒绝（由 Application）。
    """

    @staticmethod
    def to_entity(m: PartyAddress) -> PartyAddressEntity:
        """功能说明：
            ORM 地址转为领域实体。

        业务职责：
            只读映射。

        输入参数：
            m：PartyAddress。

        返回结果：
            PartyAddressEntity。

        异常说明：
            无。

        业务规则：
            不脱敏；调用方不得将 PERSON 地址暴露给 API。
        """

        return PartyAddressEntity(
            id=m.id,
            tenant_id=m.tenant_id,
            party_id=m.party_id,
            address_type=m.address_type,
            country_code=m.country_code,
            province=m.province,
            city=m.city,
            district=m.district,
            street=m.street,
            detail=m.detail,
            postal_code=m.postal_code,
            is_primary=bool(m.is_primary),
            status=m.status,
            deleted_at=m.deleted_at,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    @staticmethod
    def new_model(e: PartyAddressEntity) -> PartyAddress:
        """功能说明：
            由实体构造新地址 ORM。

        业务职责：
            创建路径映射。

        输入参数：
            e：PartyAddressEntity。

        返回结果：
            未持久化的 PartyAddress。

        异常说明：
            无。

        业务规则：
            PERSON 写入拒绝在 Application，不在本方法。
        """

        return PartyAddress(
            tenant_id=e.tenant_id,
            party_id=e.party_id,
            address_type=e.address_type,
            country_code=e.country_code,
            province=e.province,
            city=e.city,
            district=e.district,
            street=e.street,
            detail=e.detail,
            postal_code=e.postal_code,
            is_primary=e.is_primary,
            status=e.status,
            deleted_at=e.deleted_at,
        )


class PartyRiskEventMapper:
    """功能说明：
        PartyRiskEvent ORM ↔ 领域实体映射。

    业务职责：
        Infrastructure Mapper；事件只追加。
    """

    @staticmethod
    def to_entity(m: PartyRiskEvent) -> PartyRiskEventEntity:
        """功能说明：
            ORM 风险事件转为领域实体。

        业务职责：
            只读映射。

        输入参数：
            m：PartyRiskEvent。

        返回结果：
            PartyRiskEventEntity。

        异常说明：
            无。

        业务规则：
            无。
        """

        return PartyRiskEventEntity(
            id=m.id,
            tenant_id=m.tenant_id,
            party_id=m.party_id,
            event_type=m.event_type,
            previous_risk_status=m.previous_risk_status,
            new_risk_status=m.new_risk_status,
            reason=m.reason,
            operator_user_id=m.operator_user_id,
            request_id=m.request_id,
            source=m.source,
            occurred_at=m.occurred_at,
            created_at=m.created_at,
        )

    @staticmethod
    def new_model(e: PartyRiskEventEntity) -> PartyRiskEvent:
        """功能说明：
            由实体构造新风险事件 ORM。

        业务职责：
            创建路径映射；补齐 occurred_at/created_at 默认值。

        输入参数：
            e：PartyRiskEventEntity。

        返回结果：
            未持久化的 PartyRiskEvent。

        异常说明：
            无。

        业务规则：
            缺省时间使用 utc_now()。
        """

        return PartyRiskEvent(
            tenant_id=e.tenant_id,
            party_id=e.party_id,
            event_type=e.event_type,
            previous_risk_status=e.previous_risk_status,
            new_risk_status=e.new_risk_status,
            reason=e.reason,
            operator_user_id=e.operator_user_id,
            request_id=e.request_id,
            source=e.source,
            occurred_at=e.occurred_at or utc_now(),
            created_at=e.created_at or utc_now(),
        )

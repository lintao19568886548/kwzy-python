"""功能说明：
    Lease ORM ↔ Domain 映射。

业务职责：
    Infrastructure Mapper。
"""

from __future__ import annotations

from decimal import Decimal

from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.lease import (
    LeaseContract,
    LeaseContractUnit,
    LeaseTerm,
)
from app.modules.lease.domain.entities import (
    LeaseContractEntity,
    LeaseContractUnitEntity,
    LeaseTermEntity,
)


class LeaseContractMapper:
    """功能说明：LeaseContract 映射。"""

    @staticmethod
    def to_entity(m: LeaseContract) -> LeaseContractEntity:
        """功能说明：ORM 转领域实体。"""

        return LeaseContractEntity(
            id=m.id,
            tenant_id=m.tenant_id,
            park_id=m.park_id,
            party_id=m.party_id,
            contract_no=m.contract_no,
            status=m.status,
            start_date=m.start_date,
            end_date=m.end_date,
            increase_date=m.increase_date,
            increase_rate=m.increase_rate,
            deposit_amount=Decimal(str(m.deposit_amount or 0)),
            remark=m.remark,
            created_by=m.created_by,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    @staticmethod
    def new_model(e: LeaseContractEntity) -> LeaseContract:
        """功能说明：实体转新 ORM。"""

        return LeaseContract(
            tenant_id=e.tenant_id,
            park_id=e.park_id,
            party_id=e.party_id,
            contract_no=e.contract_no,
            status=e.status,
            start_date=e.start_date,
            end_date=e.end_date,
            increase_date=e.increase_date,
            increase_rate=e.increase_rate,
            deposit_amount=e.deposit_amount,
            remark=e.remark,
            created_by=e.created_by,
        )

    @staticmethod
    def apply_entity(m: LeaseContract, e: LeaseContractEntity) -> LeaseContract:
        """功能说明：实体字段写回 ORM。"""

        m.park_id = e.park_id
        m.party_id = e.party_id
        m.contract_no = e.contract_no
        m.status = e.status
        m.start_date = e.start_date
        m.end_date = e.end_date
        m.increase_date = e.increase_date
        m.increase_rate = e.increase_rate
        m.deposit_amount = e.deposit_amount
        m.remark = e.remark
        return m


class LeaseContractUnitMapper:
    """功能说明：占用行映射。"""

    @staticmethod
    def to_entity(m: LeaseContractUnit) -> LeaseContractUnitEntity:
        return LeaseContractUnitEntity(
            id=m.id,
            tenant_id=m.tenant_id,
            contract_id=m.contract_id,
            unit_id=m.unit_id,
            occupied_area=Decimal(str(m.occupied_area or 0)),
            unit_rent_price=Decimal(str(m.unit_rent_price or 0)),
        )

    @staticmethod
    def new_model(e: LeaseContractUnitEntity) -> LeaseContractUnit:
        return LeaseContractUnit(
            tenant_id=e.tenant_id,
            contract_id=e.contract_id,
            unit_id=e.unit_id,
            occupied_area=e.occupied_area,
            unit_rent_price=e.unit_rent_price,
        )


class LeaseTermMapper:
    """功能说明：条款行映射。"""

    @staticmethod
    def to_entity(m: LeaseTerm) -> LeaseTermEntity:
        return LeaseTermEntity(
            id=m.id,
            tenant_id=m.tenant_id,
            contract_id=m.contract_id,
            term_type=m.term_type,
            effective_date=m.effective_date,
            end_date=m.end_date,
            rate=m.rate,
            amount=m.amount,
            description=m.description,
            sort_order=int(m.sort_order or 0),
            created_at=m.created_at,
        )

    @staticmethod
    def new_model(e: LeaseTermEntity) -> LeaseTerm:
        return LeaseTerm(
            tenant_id=e.tenant_id,
            contract_id=e.contract_id,
            term_type=e.term_type,
            effective_date=e.effective_date,
            end_date=e.end_date,
            rate=e.rate,
            amount=e.amount,
            description=e.description,
            sort_order=e.sort_order,
            created_at=e.created_at or utc_now(),
        )

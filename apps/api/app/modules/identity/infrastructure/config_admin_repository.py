"""功能说明：组织/字典/参数 ORM 访问。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.system_config import (
    DictItem,
    DictType,
    OrgUnit,
    SystemParam,
)


class ConfigAdminRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_org_units(self, tenant_id: int) -> list[OrgUnit]:
        return list(
            self.session.scalars(
                select(OrgUnit)
                .where(OrgUnit.tenant_id == tenant_id)
                .order_by(OrgUnit.sort_order, OrgUnit.id)
            ).all()
        )

    def get_org(self, org_id: int) -> OrgUnit | None:
        return self.session.get(OrgUnit, org_id)

    def find_org_by_code(self, tenant_id: int, code: str) -> OrgUnit | None:
        return self.session.scalars(
            select(OrgUnit).where(OrgUnit.tenant_id == tenant_id, OrgUnit.code == code)
        ).first()

    def add_org(self, row: OrgUnit) -> OrgUnit:
        self.session.add(row)
        self.session.flush()
        return row

    def create_org(
        self,
        *,
        tenant_id: int,
        parent_id: int | None,
        code: str,
        name: str,
        sort_order: int,
        status: str,
        remark: str | None,
    ) -> OrgUnit:
        return self.add_org(
            OrgUnit(
                tenant_id=tenant_id,
                parent_id=parent_id,
                code=code,
                name=name,
                sort_order=sort_order,
                status=status,
                remark=remark,
            )
        )

    def list_dict_types(self, tenant_id: int) -> list[DictType]:
        return list(
            self.session.scalars(
                select(DictType).where(DictType.tenant_id == tenant_id).order_by(DictType.id)
            ).all()
        )

    def find_dict_type(self, tenant_id: int, code: str) -> DictType | None:
        return self.session.scalars(
            select(DictType).where(DictType.tenant_id == tenant_id, DictType.code == code)
        ).first()

    def add_dict_type(self, row: DictType) -> DictType:
        self.session.add(row)
        self.session.flush()
        return row

    def create_dict_type(
        self, *, tenant_id: int, code: str, name: str, status: str, remark: str | None
    ) -> DictType:
        return self.add_dict_type(
            DictType(tenant_id=tenant_id, code=code, name=name, status=status, remark=remark)
        )

    def list_dict_items(self, tenant_id: int, dict_type_id: int) -> list[DictItem]:
        return list(
            self.session.scalars(
                select(DictItem)
                .where(
                    DictItem.tenant_id == tenant_id,
                    DictItem.dict_type_id == dict_type_id,
                )
                .order_by(DictItem.sort_order, DictItem.id)
            ).all()
        )

    def add_dict_item(self, row: DictItem) -> DictItem:
        self.session.add(row)
        self.session.flush()
        return row

    def create_dict_item(
        self,
        *,
        tenant_id: int,
        dict_type_id: int,
        item_label: str,
        item_value: str,
        sort_order: int,
        status: str,
        remark: str | None,
    ) -> DictItem:
        return self.add_dict_item(
            DictItem(
                tenant_id=tenant_id,
                dict_type_id=dict_type_id,
                item_label=item_label,
                item_value=item_value,
                sort_order=sort_order,
                status=status,
                remark=remark,
            )
        )

    def list_params(self, tenant_id: int) -> list[SystemParam]:
        return list(
            self.session.scalars(
                select(SystemParam)
                .where(SystemParam.tenant_id == tenant_id)
                .order_by(SystemParam.id)
            ).all()
        )

    def find_param(self, tenant_id: int, key: str) -> SystemParam | None:
        return self.session.scalars(
            select(SystemParam).where(
                SystemParam.tenant_id == tenant_id, SystemParam.param_key == key
            )
        ).first()

    def add_param(self, row: SystemParam) -> SystemParam:
        self.session.add(row)
        self.session.flush()
        return row

    def create_param(
        self,
        *,
        tenant_id: int,
        param_key: str,
        param_value: str,
        value_type: str,
        is_secret: bool,
        remark: str | None,
    ) -> SystemParam:
        return self.add_param(
            SystemParam(
                tenant_id=tenant_id,
                param_key=param_key,
                param_value=param_value,
                value_type=value_type,
                is_secret=is_secret,
                remark=remark,
            )
        )

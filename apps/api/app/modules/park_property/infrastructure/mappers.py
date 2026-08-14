"""ORM ↔ Domain Mapper。

功能说明：
    在基础设施层完成持久化模型与领域实体转换。

业务职责：
    infrastructure；禁止被 domain 依赖。
"""

from __future__ import annotations

from app.infrastructure.database.models.park_property import Building, Park, Unit
from app.modules.park_property.domain.entities import BuildingEntity, ParkEntity, UnitEntity


class ParkMapper:
    """功能说明：园区 ORM 与领域实体互转。"""

    @staticmethod
    def to_entity(model: Park) -> ParkEntity:
        return ParkEntity(
            id=model.id,
            tenant_id=model.tenant_id,
            name=model.name,
            address=model.address or "",
            area=model.area,
            contact=model.contact,
            manager=model.manager,
            description=model.description,
            status=model.status,
            is_deleted=bool(model.is_deleted),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def apply_entity(model: Park, entity: ParkEntity) -> Park:
        model.tenant_id = entity.tenant_id
        model.name = entity.name
        model.address = entity.address
        model.area = entity.area
        model.contact = entity.contact
        model.manager = entity.manager
        model.description = entity.description
        model.status = entity.status
        model.is_deleted = entity.is_deleted
        return model

    @staticmethod
    def new_model(entity: ParkEntity) -> Park:
        return Park(
            tenant_id=entity.tenant_id,
            name=entity.name,
            address=entity.address,
            area=entity.area,
            contact=entity.contact,
            manager=entity.manager,
            description=entity.description,
            status=entity.status,
            is_deleted=entity.is_deleted,
        )


class BuildingMapper:
    """功能说明：楼栋 ORM 与领域实体互转。"""

    @staticmethod
    def to_entity(model: Building) -> BuildingEntity:
        return BuildingEntity(
            id=model.id,
            tenant_id=model.tenant_id,
            park_id=model.park_id,
            parent_id=model.parent_id,
            code=model.code,
            name=model.name,
            node_type=model.node_type,
            building_type=model.building_type,
            sort_order=model.sort_order,
            status=model.status,
            address=model.address or "",
            description=model.description,
            attributes=model.attributes_json,
            geometry=model.geometry_json,
            geometry_type=model.geometry_type,
            coordinate_reference=model.coordinate_reference,
            geometry_version=model.geometry_version,
            is_deleted=bool(model.is_deleted),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def new_model(entity: BuildingEntity) -> Building:
        return Building(
            tenant_id=entity.tenant_id,
            park_id=entity.park_id,
            parent_id=entity.parent_id,
            code=entity.code,
            name=entity.name,
            node_type=entity.node_type,
            building_type=entity.building_type,
            sort_order=entity.sort_order,
            status=entity.status,
            address=entity.address,
            description=entity.description,
            attributes_json=entity.attributes,
            geometry_json=entity.geometry,
            geometry_type=entity.geometry_type,
            coordinate_reference=entity.coordinate_reference,
            geometry_version=entity.geometry_version,
            is_deleted=entity.is_deleted,
        )

    @staticmethod
    def apply_entity(model: Building, entity: BuildingEntity) -> Building:
        model.parent_id = entity.parent_id
        model.code = entity.code
        model.name = entity.name
        model.node_type = entity.node_type
        model.building_type = entity.building_type
        model.sort_order = entity.sort_order
        model.status = entity.status
        model.address = entity.address
        model.description = entity.description
        model.attributes_json = entity.attributes
        model.geometry_json = entity.geometry
        model.geometry_type = entity.geometry_type
        model.coordinate_reference = entity.coordinate_reference
        model.geometry_version = entity.geometry_version
        model.is_deleted = entity.is_deleted
        return model


class UnitMapper:
    """功能说明：单元 ORM 与领域实体互转。"""

    @staticmethod
    def to_entity(model: Unit) -> UnitEntity:
        return UnitEntity(
            id=model.id,
            tenant_id=model.tenant_id,
            park_id=model.park_id,
            building_id=model.building_id,
            logical_id=model.logical_id,
            version_no=model.version_no,
            valid_from=model.valid_from,
            valid_to=model.valid_to,
            supersedes_id=model.supersedes_id,
            lock_version=model.lock_version,
            code=model.code,
            name=model.name,
            usage_type=model.usage_type,
            billing_unit=model.billing_unit,
            available_from=model.available_from,
            rentable_area=model.rentable_area,
            used_area=model.used_area,
            base_rent_price=model.base_rent_price,
            status=model.status,
            attributes=model.attributes_json,
            asset_template_version_id=model.asset_template_version_id,
            is_deleted=bool(model.is_deleted),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def apply_entity(model: Unit, entity: UnitEntity) -> Unit:
        model.tenant_id = entity.tenant_id
        model.park_id = entity.park_id
        model.building_id = entity.building_id
        model.logical_id = entity.logical_id
        model.version_no = entity.version_no
        model.valid_from = entity.valid_from
        model.valid_to = entity.valid_to
        model.supersedes_id = entity.supersedes_id
        model.lock_version = entity.lock_version
        model.code = entity.code
        model.name = entity.name
        model.usage_type = entity.usage_type
        model.billing_unit = entity.billing_unit
        model.available_from = entity.available_from
        model.rentable_area = entity.rentable_area
        model.used_area = entity.used_area
        model.base_rent_price = entity.base_rent_price
        model.status = entity.status
        model.attributes_json = entity.attributes
        model.asset_template_version_id = entity.asset_template_version_id
        model.is_deleted = entity.is_deleted
        return model

    @staticmethod
    def new_model(entity: UnitEntity) -> Unit:
        return Unit(
            tenant_id=entity.tenant_id,
            park_id=entity.park_id,
            building_id=entity.building_id,
            logical_id=entity.logical_id,
            version_no=entity.version_no,
            valid_from=entity.valid_from,
            valid_to=entity.valid_to,
            supersedes_id=entity.supersedes_id,
            lock_version=entity.lock_version,
            code=entity.code,
            name=entity.name,
            usage_type=entity.usage_type,
            billing_unit=entity.billing_unit,
            available_from=entity.available_from,
            rentable_area=entity.rentable_area,
            used_area=entity.used_area,
            base_rent_price=entity.base_rent_price,
            status=entity.status,
            attributes_json=entity.attributes,
            asset_template_version_id=entity.asset_template_version_id,
            is_deleted=entity.is_deleted,
        )

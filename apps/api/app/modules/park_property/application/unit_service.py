"""Unit application service.

功能说明：
    单元 CRUD 与状态迁移编排；经 Entity+Mapper 持久化。

业务职责：
    Application 层；禁止直接构造 ORM Model。
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.business_logging import log_business_success
from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.modules.park_property.domain.entities import BuildingEntity, UnitEntity
from app.modules.park_property.domain.states import (
    assert_unit_status,
    transition_unit_status,
)
from app.modules.park_property.infrastructure.building_repository import BuildingRepository
from app.modules.park_property.infrastructure.mappers import BuildingMapper, UnitMapper
from app.modules.park_property.infrastructure.park_repository import ParkRepository
from app.modules.park_property.infrastructure.unit_repository import UnitRepository
from app.shared.tenant_context import TenantContext

logger = logging.getLogger(__name__)


class UnitService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.repo = UnitRepository(session, ctx)
        self.park_repo = ParkRepository(session, ctx)
        self.building_repo = BuildingRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def list_units(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        park_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> dict[str, Any]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        offset = (page - 1) * page_size
        items = self.repo.list(
            park_id=park_id, status=status, offset=offset, limit=page_size
        )
        total = self.repo.count(park_id=park_id, status=status)
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [self._to_dict(UnitMapper.to_entity(u)) for u in items],
        }

    def get_unit(self, unit_id: int) -> dict[str, Any]:
        unit = self.repo.get_by_id(unit_id)
        if unit is None:
            raise AppError("单元不存在", code="UNIT_NOT_FOUND", status_code=404)
        return self._to_dict(UnitMapper.to_entity(unit))

    def create_unit(self, data: dict[str, Any]) -> dict[str, Any]:
        park_id = data.get("park_id")
        if not park_id:
            raise AppError("park_id 必填", code="VALIDATION_ERROR", status_code=400)
        park_id = int(park_id)
        park = self.park_repo.get_by_id(park_id)
        if park is None:
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)

        code = (data.get("code") or "").strip()
        name = (data.get("name") or "").strip()
        if not code or not name:
            raise AppError("code 与 name 必填", code="VALIDATION_ERROR", status_code=400)

        building_id = data.get("building_id")
        if building_id:
            building = self.building_repo.get_by_id(int(building_id))
            if building is None or building.park_id != park_id:
                raise AppError(
                    "楼栋不存在或不属于该园区",
                    code="BUILDING_INVALID",
                    status_code=400,
                )
            building_id = int(building_id)
        else:
            building = self._ensure_default_building(park_id)
            building_id = int(building.id)

        try:
            status = assert_unit_status(data.get("status") or "VACANT")
        except ValueError as exc:
            raise AppError(str(exc), code="UNIT_STATUS_INVALID", status_code=400) from exc
        existing = self.repo.find_by_building_code(building_id, code)
        if existing:
            raise AppError("同一楼栋下单元编码已存在", code="UNIT_CODE_DUP", status_code=400)

        entity = UnitEntity(
            tenant_id=self.ctx.tenant_id,
            park_id=park_id,
            building_id=building_id,
            code=code,
            name=name,
            rentable_area=Decimal(str(data.get("rentable_area") or 0)),
            used_area=Decimal(str(data.get("used_area") or 0)),
            base_rent_price=Decimal(str(data.get("base_rent_price") or 0)),
            status=status,
            attributes=data.get("attributes"),
        )
        model = UnitMapper.new_model(entity)
        self.repo.add(model)
        self.audit.record(
            action="create",
            resource_type="UNIT",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"status": model.status, "building_id": model.building_id},
        )
        self.session.commit()
        self.session.refresh(model)
        log_business_success(
            logger,
            "创建单元成功",
            ctx=self.ctx,
            module="unit",
            action="create",
            resource_id=model.id,
            park_id=model.park_id,
        )
        return self._to_dict(UnitMapper.to_entity(model))

    def update_unit(
        self,
        unit_id: int,
        data: dict[str, Any],
        *,
        audit_action: str = "update",
    ) -> dict[str, Any]:
        model = self.repo.get_by_id(unit_id)
        if model is None:
            raise AppError("单元不存在", code="UNIT_NOT_FOUND", status_code=404)
        entity = UnitMapper.to_entity(model)

        if "name" in data and data["name"] is not None:
            entity.name = str(data["name"]).strip()
        if "rentable_area" in data and data["rentable_area"] is not None:
            entity.rentable_area = Decimal(str(data["rentable_area"]))
        if "base_rent_price" in data and data["base_rent_price"] is not None:
            entity.base_rent_price = Decimal(str(data["base_rent_price"]))
        if "attributes" in data:
            entity.attributes = data["attributes"]
        # used_area is projection — ignore client write in step1
        if "status" in data and data["status"] is not None:
            try:
                entity.status = transition_unit_status(entity.status, str(data["status"]))
            except ValueError as exc:
                raise AppError(str(exc), code="UNIT_STATUS_INVALID", status_code=400) from exc

        UnitMapper.apply_entity(model, entity)
        self.repo.save(model)
        self.audit.record(
            action=audit_action,
            resource_type="UNIT",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"fields": sorted(data.keys()), "status": model.status},
        )
        self.session.commit()
        self.session.refresh(model)
        log_business_success(
            logger,
            "变更单元状态成功" if audit_action == "change_status" else "更新单元成功",
            ctx=self.ctx,
            module="unit",
            action=audit_action,
            resource_id=model.id,
            park_id=model.park_id,
        )
        return self._to_dict(UnitMapper.to_entity(model))

    def change_status(self, unit_id: int, status: str) -> dict[str, Any]:
        return self.update_unit(
            unit_id,
            {"status": status},
            audit_action="change_status",
        )

    def delete_unit(self, unit_id: int) -> None:
        model = self.repo.get_by_id(unit_id)
        if model is None:
            raise AppError("单元不存在", code="UNIT_NOT_FOUND", status_code=404)
        self.repo.soft_delete(model)
        self.audit.record(
            action="delete",
            resource_type="UNIT",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"soft_delete": True},
        )
        self.session.commit()
        log_business_success(
            logger,
            "删除单元成功",
            ctx=self.ctx,
            module="unit",
            action="delete",
            resource_id=model.id,
            park_id=model.park_id,
        )

    def _ensure_default_building(self, park_id: int):
        building = self.building_repo.get_default_for_park(park_id)
        if building:
            return building
        entity = BuildingEntity(
            tenant_id=self.ctx.tenant_id,
            park_id=park_id,
            name="主楼",
            building_type="FACTORY",
            address="",
        )
        model = BuildingMapper.new_model(entity)
        self.building_repo.add(model)
        self.session.flush()
        return model

    @staticmethod
    def _to_dict(entity: UnitEntity) -> dict[str, Any]:
        return {
            "id": entity.id,
            "tenant_id": entity.tenant_id,
            "park_id": entity.park_id,
            "building_id": entity.building_id,
            "code": entity.code,
            "name": entity.name,
            "rentable_area": float(entity.rentable_area or 0),
            "used_area": float(entity.used_area or 0),
            "base_rent_price": float(entity.base_rent_price or 0),
            "status": entity.status,
            "attributes": entity.attributes,
            "created_at": entity.created_at.isoformat() if entity.created_at else None,
            "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        }

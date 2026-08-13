"""Unit application service.

功能说明：
    单元 CRUD 与状态迁移编排；经 Entity+Mapper 持久化。

业务职责：
    Application 层；禁止直接构造 ORM Model。
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
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
from app.modules.park_property.infrastructure.unit_lineage_repository import UnitLineageRepository
from app.shared.tenant_context import TenantContext

logger = logging.getLogger(__name__)


class UnitService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.repo = UnitRepository(session, ctx)
        self.park_repo = ParkRepository(session, ctx)
        self.building_repo = BuildingRepository(session, ctx)
        self.lineages = UnitLineageRepository(session, ctx)
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
        unit = self.repo.get_current_by_id(unit_id)
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

        code = (data.get("code") or "").strip().upper()
        name = (data.get("name") or "").strip()
        if not code or not name:
            raise AppError("code 与 name 必填", code="VALIDATION_ERROR", status_code=400)

        building_id = data.get("building_id")
        if building_id:
            building = self.building_repo.get_by_id(int(building_id))
            if (
                building is None
                or building.park_id != park_id
                or building.status != "ACTIVE"
                or building.node_type not in {"BUILDING", "FLOOR"}
            ):
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
        if status == "OCCUPIED":
            raise AppError(
                "占用状态只能由生效租约投影产生",
                code="UNIT_OCCUPANCY_MANAGED",
                status_code=409,
            )
        existing = self.repo.find_by_building_code(building_id, code)
        if existing:
            raise AppError("同一楼栋下单元编码已存在", code="UNIT_CODE_DUP", status_code=400)

        entity = UnitEntity(
            tenant_id=self.ctx.tenant_id,
            park_id=park_id,
            building_id=building_id,
            logical_id=str(uuid4()),
            code=code,
            name=name,
            usage_type=str(data.get("usage_type") or "FACTORY").upper(),
            billing_unit=str(data.get("billing_unit") or "SQM").upper(),
            available_from=data.get("available_from"),
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
        model = self.repo.get_current_by_id(unit_id)
        if model is None:
            raise AppError("单元不存在", code="UNIT_NOT_FOUND", status_code=404)
        entity = UnitMapper.to_entity(model)

        expected = data.pop("expected_lock_version", None)
        if expected is not None:
            self._expected(model, int(expected))

        if "name" in data and data["name"] is not None:
            entity.name = str(data["name"]).strip()
        if "rentable_area" in data and data["rentable_area"] is not None:
            raise AppError(
                "计租面积属于结构字段，请创建新版本",
                code="UNIT_VERSION_REQUIRED",
                status_code=409,
            )
        if "base_rent_price" in data and data["base_rent_price"] is not None:
            entity.base_rent_price = Decimal(str(data["base_rent_price"]))
        if "attributes" in data:
            entity.attributes = data["attributes"]
        # used_area is projection — ignore client write in step1
        if "status" in data and data["status"] is not None:
            if str(data["status"]).upper() == "OCCUPIED":
                raise AppError(
                    "占用状态只能由生效租约投影产生",
                    code="UNIT_OCCUPANCY_MANAGED",
                    status_code=409,
                )
            try:
                entity.status = transition_unit_status(entity.status, str(data["status"]))
            except ValueError as exc:
                raise AppError(str(exc), code="UNIT_STATUS_INVALID", status_code=400) from exc

        entity.lock_version += 1

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

    def history(self, unit_id: int) -> list[dict[str, Any]]:
        model = self.repo.get_by_id(unit_id)
        if model is None:
            raise AppError("单元不存在", code="UNIT_NOT_FOUND", status_code=404)
        return [self._to_dict(UnitMapper.to_entity(row)) for row in self.repo.history(model.logical_id)]

    def lineage(self, unit_id: int) -> list[dict[str, Any]]:
        model = self.repo.get_by_id(unit_id)
        if model is None:
            raise AppError("单元不存在", code="UNIT_NOT_FOUND", status_code=404)
        return [
            {
                "operation_id": row.operation_id,
                "operation_type": row.operation_type,
                "source_unit_id": row.source_unit_id,
                "target_unit_id": row.target_unit_id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in self.lineages.list_for_unit(unit_id)
        ]

    def create_version(self, unit_id: int, data: dict[str, Any]) -> dict[str, Any]:
        source = self.repo.get_current_for_update(unit_id)
        if source is None:
            self._raise_missing_or_stale(unit_id)
        self._expected(source, int(data.pop("expected_lock_version")))
        if Decimal(str(source.used_area or 0)) > 0:
            raise AppError("已占用单元不能结构变更", code="UNIT_IN_USE", status_code=409)
        building_id = int(data.get("building_id") or source.building_id)
        building = self.building_repo.get_by_id(building_id)
        if (
            building is None
            or int(building.park_id) != int(source.park_id)
            or building.status != "ACTIVE"
            or building.node_type not in {"BUILDING", "FLOOR"}
        ):
            raise AppError("目标空间无效", code="BUILDING_INVALID", status_code=400)
        code = str(data.get("code") or source.code).strip().upper()
        now = datetime.utcnow()
        source.valid_to = now
        source.lock_version += 1
        self.repo.save(source)
        self.session.flush()
        entity = UnitEntity(
            tenant_id=source.tenant_id,
            park_id=source.park_id,
            building_id=building_id,
            logical_id=source.logical_id,
            version_no=source.version_no + 1,
            valid_from=now,
            supersedes_id=source.id,
            lock_version=1,
            code=code,
            name=str(data.get("name") or source.name).strip(),
            usage_type=str(data.get("usage_type") or source.usage_type).upper(),
            billing_unit=str(data.get("billing_unit") or source.billing_unit).upper(),
            available_from=data.get("available_from", source.available_from),
            rentable_area=Decimal(str(data.get("rentable_area") or source.rentable_area)),
            used_area=Decimal("0"),
            base_rent_price=Decimal(str(data.get("base_rent_price") if data.get("base_rent_price") is not None else source.base_rent_price)),
            status="VACANT",
            attributes=data.get("attributes", source.attributes_json),
        )
        target = UnitMapper.new_model(entity)
        try:
            self.repo.add(target)
            self.audit.record(
                action="create_version",
                resource_type="UNIT",
                resource_id=target.id,
                park_id=target.park_id,
                detail={"source_id": source.id, "version_no": target.version_no},
            )
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError("当前空间单元编码冲突", code="UNIT_CODE_CONFLICT", status_code=409) from exc
        self.session.refresh(target)
        return self._to_dict(UnitMapper.to_entity(target))

    def split(self, data: dict[str, Any]) -> dict[str, Any]:
        unit_id = int(data["unit_id"])
        source = self.repo.get_current_for_update(unit_id)
        if source is None:
            self._raise_missing_or_stale(unit_id)
        self._expected(source, int(data["expected_lock_version"]))
        self._assert_transformable(source)
        targets = data.get("targets") or []
        areas = [Decimal(str(item["rentable_area"])) for item in targets]
        if any(area <= 0 for area in areas) or sum(areas, Decimal("0")) != Decimal(str(source.rentable_area)):
            raise AppError("拆分面积必须为正且与来源面积完全一致", code="UNIT_AREA_MISMATCH", status_code=400)
        codes = [str(item["code"]).strip().upper() for item in targets]
        if len(codes) != len(set(codes)):
            raise AppError("拆分目标编码重复", code="UNIT_CODE_CONFLICT", status_code=409)
        operation_id = str(uuid4())
        now = datetime.utcnow()
        source.valid_to = now
        source.status = "RETIRED"
        source.lock_version += 1
        self.repo.save(source)
        self.session.flush()
        created = []
        try:
            for item, area, code in zip(targets, areas, codes):
                target = UnitMapper.new_model(
                    UnitEntity(
                        tenant_id=source.tenant_id,
                        park_id=source.park_id,
                        building_id=source.building_id,
                        logical_id=str(uuid4()),
                        valid_from=now,
                        code=code,
                        name=str(item["name"]).strip(),
                        usage_type=str(item.get("usage_type") or source.usage_type).upper(),
                        billing_unit=source.billing_unit,
                        available_from=source.available_from,
                        rentable_area=area,
                        used_area=Decimal("0"),
                        base_rent_price=Decimal(str(item.get("base_rent_price") if item.get("base_rent_price") is not None else source.base_rent_price)),
                        status="VACANT",
                        attributes=source.attributes_json,
                    )
                )
                self.repo.add(target)
                self.lineages.add_edge(
                    park_id=source.park_id,
                    operation_id=operation_id,
                    operation_type="SPLIT",
                    source_unit_id=source.id,
                    target_unit_id=target.id,
                )
                created.append(target)
            self.audit.record(
                action="split",
                resource_type="UNIT",
                resource_id=source.id,
                park_id=source.park_id,
                detail={"operation_id": operation_id, "target_count": len(created)},
            )
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError("拆分目标编码冲突", code="UNIT_CODE_CONFLICT", status_code=409) from exc
        return {"operation_id": operation_id, "source_unit_id": source.id, "targets": [self._to_dict(UnitMapper.to_entity(row)) for row in created]}

    def merge(self, data: dict[str, Any]) -> dict[str, Any]:
        source_specs = data.get("sources") or []
        ids = [int(item["unit_id"]) for item in source_specs]
        if len(ids) < 2 or len(ids) != len(set(ids)):
            raise AppError("合并至少需要两个不同单元", code="VALIDATION_ERROR", status_code=400)
        sources = self.repo.get_currents_for_update(ids)
        if len(sources) != len(ids):
            if any(
                (known := self.repo.get_by_id(unit_id)) is not None
                and known.valid_to is not None
                for unit_id in ids
            ):
                raise AppError(
                    "单元版本已变化，请刷新后重试",
                    code="UNIT_VERSION_CONFLICT",
                    status_code=409,
                )
            raise AppError("合并来源不存在或不可见", code="UNIT_NOT_FOUND", status_code=404)
        expected = {int(item["unit_id"]): int(item["expected_lock_version"]) for item in source_specs}
        for source in sources:
            self._expected(source, expected[source.id])
            self._assert_transformable(source)
        first = sources[0]
        if any(source.park_id != first.park_id or source.building_id != first.building_id for source in sources):
            raise AppError("合并来源必须属于同一园区和空间", code="UNIT_MERGE_INCOMPATIBLE", status_code=400)
        operation_id = str(uuid4())
        now = datetime.utcnow()
        total = sum((Decimal(str(source.rentable_area)) for source in sources), Decimal("0"))
        for source in sources:
            source.valid_to = now
            source.status = "RETIRED"
            source.lock_version += 1
            self.repo.save(source)
        self.session.flush()
        target = UnitMapper.new_model(
            UnitEntity(
                tenant_id=first.tenant_id,
                park_id=first.park_id,
                building_id=first.building_id,
                logical_id=str(uuid4()),
                valid_from=now,
                code=str(data["code"]).strip().upper(),
                name=str(data["name"]).strip(),
                usage_type=str(data.get("usage_type") or first.usage_type).upper(),
                billing_unit=first.billing_unit,
                available_from=first.available_from,
                rentable_area=total,
                used_area=Decimal("0"),
                base_rent_price=Decimal(str(data.get("base_rent_price") if data.get("base_rent_price") is not None else first.base_rent_price)),
                status="VACANT",
                attributes=first.attributes_json,
            )
        )
        try:
            self.repo.add(target)
            for source in sources:
                self.lineages.add_edge(
                    park_id=first.park_id,
                    operation_id=operation_id,
                    operation_type="MERGE",
                    source_unit_id=source.id,
                    target_unit_id=target.id,
                )
            self.audit.record(
                action="merge",
                resource_type="UNIT",
                resource_id=target.id,
                park_id=target.park_id,
                detail={"operation_id": operation_id, "source_count": len(sources)},
            )
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError("合并目标编码冲突", code="UNIT_CODE_CONFLICT", status_code=409) from exc
        self.session.refresh(target)
        return {"operation_id": operation_id, "source_unit_ids": ids, "target": self._to_dict(UnitMapper.to_entity(target))}

    @staticmethod
    def _expected(unit, expected: int) -> None:
        if int(unit.lock_version) != expected:
            raise AppError("单元版本已变化，请刷新后重试", code="UNIT_VERSION_CONFLICT", status_code=409)

    def _raise_missing_or_stale(self, unit_id: int) -> None:
        known = self.repo.get_by_id(unit_id)
        if known is not None and known.valid_to is not None:
            raise AppError(
                "单元版本已变化，请刷新后重试",
                code="UNIT_VERSION_CONFLICT",
                status_code=409,
            )
        raise AppError("当前单元不存在", code="UNIT_NOT_FOUND", status_code=404)

    @staticmethod
    def _assert_transformable(unit) -> None:
        if unit.status != "VACANT" or Decimal(str(unit.used_area or 0)) != 0:
            raise AppError("仅零占用的空置单元可拆分或合并", code="UNIT_IN_USE", status_code=409)

    def change_status(self, unit_id: int, status: str) -> dict[str, Any]:
        return self.update_unit(
            unit_id,
            {"status": status},
            audit_action="change_status",
        )

    def delete_unit(self, unit_id: int) -> None:
        model = self.repo.get_current_by_id(unit_id)
        if model is None:
            raise AppError("单元不存在", code="UNIT_NOT_FOUND", status_code=404)
        if model.status == "OCCUPIED" or Decimal(str(model.used_area or 0)) > 0:
            raise AppError("已占用单元不能删除", code="UNIT_IN_USE", status_code=409)
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
            code="MAIN",
            name="主楼",
            node_type="BUILDING",
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
            "logical_id": entity.logical_id,
            "version_no": entity.version_no,
            "valid_from": entity.valid_from.isoformat() if entity.valid_from else None,
            "valid_to": entity.valid_to.isoformat() if entity.valid_to else None,
            "supersedes_id": entity.supersedes_id,
            "lock_version": entity.lock_version,
            "code": entity.code,
            "name": entity.name,
            "usage_type": entity.usage_type,
            "billing_unit": entity.billing_unit,
            "available_from": entity.available_from.isoformat() if entity.available_from else None,
            "rentable_area": float(entity.rentable_area or 0),
            "used_area": float(entity.used_area or 0),
            "base_rent_price": float(entity.base_rent_price or 0),
            "status": entity.status,
            "attributes": entity.attributes,
            "created_at": entity.created_at.isoformat() if entity.created_at else None,
            "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        }

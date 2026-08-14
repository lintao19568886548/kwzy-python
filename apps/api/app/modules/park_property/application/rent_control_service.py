"""Scoped rent-control query application service."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.park_property.application.asset_template_service import AssetTemplateService
from app.modules.park_property.application.unit_service import UnitService
from app.modules.park_property.infrastructure.asset_template_repository import (
    AssetTemplateRepository,
)
from app.modules.park_property.infrastructure.building_repository import BuildingRepository
from app.modules.park_property.infrastructure.mappers import UnitMapper
from app.modules.park_property.infrastructure.rent_control_repository import RentControlRepository
from app.modules.park_property.infrastructure.unit_lineage_repository import UnitLineageRepository
from app.modules.park_property.infrastructure.unit_repository import UnitRepository
from app.shared.tenant_context import TenantContext

MARKETABLE_UNIT_STATUSES = {"VACANT", "OCCUPIED"}


class RentControlService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.ctx = ctx
        self.units = UnitRepository(session, ctx)
        self.spaces = BuildingRepository(session, ctx)
        self.relations = RentControlRepository(session, ctx)
        self.lineages = UnitLineageRepository(session, ctx)
        self.template_service = AssetTemplateService(session, ctx)
        self.templates = AssetTemplateRepository(session, ctx)

    def summary(self, **filters) -> dict[str, Any]:
        models = self.units.all_current_filtered(**self._filters(filters))
        rentable = sum((Decimal(str(row.rentable_area or 0)) for row in models), Decimal("0"))
        used = sum((Decimal(str(row.used_area or 0)) for row in models), Decimal("0"))
        available = rentable - used
        statuses = Counter(row.status for row in models)
        return {
            "inventory_count": len(models),
            "rentable_area": float(rentable),
            "used_area": float(used),
            "available_area": float(available),
            "occupancy_rate": round(float(used / rentable), 6) if rentable > 0 else 0,
            "status_counts": {key: statuses.get(key, 0) for key in ["DRAFT", "VACANT", "RESERVED", "OCCUPIED", "MAINTENANCE", "RETIRED"]},
        }

    def list_units(self, *, page: int = 1, page_size: int = 50, **filters) -> dict[str, Any]:
        normalized = self._filters(filters)
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        rows = self.units.list_current_filtered(
            **normalized,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        space_map = self._space_map({int(row.park_id) for row in rows})
        items = [self._unit_row(row, space_map.get(int(row.building_id))) for row in rows]
        return {
            "total": self.units.count_current_filtered(**normalized),
            "page": page,
            "page_size": page_size,
            "items": items,
        }

    def matrix(self, **filters) -> list[dict[str, Any]]:
        normalized = self._filters(filters)
        rows = self.units.all_current_filtered(**normalized)
        space_map = self._space_map({int(row.park_id) for row in rows})
        groups: dict[int, dict[str, Any]] = {}
        for row in rows:
            node = space_map.get(int(row.building_id))
            group = groups.setdefault(
                int(row.building_id),
                {
                    "space_id": int(row.building_id),
                    "space_code": node.code if node else "",
                    "space_name": node.name if node else "未命名空间",
                    "node_type": node.node_type if node else "UNKNOWN",
                    "units": [],
                },
            )
            group["units"].append(self._unit_row(row, node))
        return list(groups.values())

    def map_projection(self, **filters) -> dict[str, Any]:
        rows = self.units.all_current_filtered(**self._filters(filters))
        space_map = self._space_map({int(row.park_id) for row in rows})
        grouped: dict[int, list[Any]] = defaultdict(list)
        for row in rows:
            grouped[int(row.building_id)].append(row)
        features: list[dict[str, Any]] = []
        unmapped_count = 0
        unmapped_area = Decimal("0")
        references: set[str] = set()
        for space_id, group in grouped.items():
            node = space_map.get(space_id)
            if node is None or not node.geometry_json:
                unmapped_count += len(group)
                unmapped_area += sum((Decimal(str(item.rentable_area or 0)) for item in group), Decimal("0"))
                continue
            rentable = sum((Decimal(str(item.rentable_area or 0)) for item in group), Decimal("0"))
            used = sum((Decimal(str(item.used_area or 0)) for item in group), Decimal("0"))
            statuses = Counter(item.status for item in group)
            references.add(node.coordinate_reference or "UNKNOWN")
            features.append(
                {
                    "type": "Feature",
                    "id": node.id,
                    "geometry": node.geometry_json,
                    "properties": {
                        "space_id": node.id,
                        "space_code": node.code,
                        "space_name": node.name,
                        "node_type": node.node_type,
                        "coordinate_reference": node.coordinate_reference,
                        "geometry_version": node.geometry_version,
                        "inventory_count": len(group),
                        "rentable_area": float(rentable),
                        "used_area": float(used),
                        "available_area": float(rentable - used),
                        "occupancy_rate": round(float(used / rentable), 6) if rentable else 0,
                        "status_counts": dict(statuses),
                    },
                }
            )
        return {
            "type": "FeatureCollection",
            "features": features,
            "coordinate_references": sorted(references),
            "provider_status": "NOT_CONNECTED_LOCAL_SCHEMATIC",
            "unmapped_inventory_count": unmapped_count,
            "unmapped_rentable_area": float(unmapped_area),
        }

    def vacancies(self, *, page: int = 1, page_size: int = 50, as_of: date | None = None, **filters) -> dict[str, Any]:
        current_date = as_of or date.today()
        rows = self.units.all_current_filtered(**self._filters(filters))
        space_map = self._space_map({int(row.park_id) for row in rows})
        items = []
        for row in rows:
            if row.status not in MARKETABLE_UNIT_STATUSES:
                continue
            available = Decimal(str(row.rentable_area or 0)) - Decimal(str(row.used_area or 0))
            if available <= 0:
                continue
            available_from = row.available_from or current_date
            items.append(
                {
                    **self._unit_row(row, space_map.get(int(row.building_id))),
                    "available_area": float(available),
                    "vacancy_days": max((current_date - available_from).days, 0),
                    "as_of": current_date.isoformat(),
                }
            )
        items.sort(key=lambda item: (-item["vacancy_days"], item["park_id"], item["space_code"] or "", item["code"]))
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        start = (page - 1) * page_size
        return {"total": len(items), "page": page, "page_size": page_size, "items": items[start : start + page_size]}

    def expiries(self, *, page: int = 1, page_size: int = 50, date_from: date | None = None, days: int = 90, **filters) -> dict[str, Any]:
        start_date = date_from or date.today()
        days = min(max(int(days), 1), 366)
        normalized = self._filters(filters)
        rows = self.relations.expiring_leases(
            date_from=start_date,
            date_to=start_date + timedelta(days=days),
            park_id=normalized["park_id"],
            building_ids=normalized["building_ids"],
        )
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        start = (page - 1) * page_size
        return {
            "total": len(rows),
            "page": page,
            "page_size": page_size,
            "date_from": start_date.isoformat(),
            "date_to": (start_date + timedelta(days=days)).isoformat(),
            "items": rows[start : start + page_size],
        }

    def analysis(self, **filters) -> dict[str, Any]:
        rows = self.units.all_current_filtered(**self._filters(filters))
        version_map = self.templates.public_versions(
            {int(row.asset_template_version_id) for row in rows if row.asset_template_version_id}
        )
        categories: dict[str, dict[str, Any]] = {}
        spaces: dict[int, dict[str, Any]] = {}
        space_map = self._space_map({int(row.park_id) for row in rows})
        total_potential = Decimal("0")
        for row in rows:
            pair = version_map.get(int(row.asset_template_version_id)) if row.asset_template_version_id else None
            category = pair[0].category if pair else row.usage_type
            available = Decimal(str(row.rentable_area or 0)) - Decimal(str(row.used_area or 0))
            potential = (
                available * Decimal(str(row.base_rent_price or 0))
                if row.status in MARKETABLE_UNIT_STATUSES
                else Decimal("0")
            )
            total_potential += potential
            bucket = categories.setdefault(category, self._analysis_bucket(category))
            self._add_analysis(bucket, row, potential)
            node = space_map.get(int(row.building_id))
            space_bucket = spaces.setdefault(
                int(row.building_id),
                self._analysis_bucket(node.name if node else str(row.building_id)),
            )
            space_bucket["space_id"] = int(row.building_id)
            space_bucket["space_code"] = node.code if node else None
            self._add_analysis(space_bucket, row, potential)
        summary = self.summary(**filters)
        return {
            "summary": summary,
            "categories": sorted(categories.values(), key=lambda item: item["key"]),
            "spaces": sorted(spaces.values(), key=lambda item: (item.get("space_code") or "", item["key"])),
            "asking_rent_potential": float(total_potential),
            "asking_rent_potential_label": "当前挂牌价×可租面积（非会计收入）",
        }

    def detail(self, unit_id: int) -> dict[str, Any]:
        model = self.units.get_current_by_id(unit_id)
        if model is None:
            raise AppError("当前单元不存在", code="UNIT_NOT_FOUND", status_code=404)
        node = self.spaces.get_by_id(int(model.building_id))
        history = [UnitService._to_dict(UnitMapper.to_entity(row)) for row in self.units.history(model.logical_id)]
        lineage = [
            {
                "operation_id": row.operation_id,
                "operation_type": row.operation_type,
                "source_unit_id": row.source_unit_id,
                "target_unit_id": row.target_unit_id,
            }
            for row in self.lineages.list_for_unit(unit_id)
        ]
        return {
            **self._unit_row(model, node),
            "asset_template": self.template_service.public_version(model.asset_template_version_id),
            "history": history,
            "lineage": lineage,
            "effective_leases": self.relations.effective_leases(unit_id, int(model.park_id)),
            "work_orders": self.relations.work_orders(unit_id, int(model.park_id)),
            "can_split_merge": model.status == "VACANT" and Decimal(str(model.used_area or 0)) == 0,
            "blocking_reason": None if model.status == "VACANT" and Decimal(str(model.used_area or 0)) == 0 else "仅零占用的空置单元可拆分或合并",
        }

    def _filters(self, filters: dict[str, Any]) -> dict[str, Any]:
        park_id = int(filters["park_id"]) if filters.get("park_id") is not None else None
        space_id = int(filters["space_id"]) if filters.get("space_id") is not None else None
        building_ids = None
        if space_id is not None:
            node = self.spaces.get_by_id(space_id)
            if node is None:
                raise AppError("空间节点不存在", code="SPACE_NOT_FOUND", status_code=404)
            if park_id is not None and int(node.park_id) != park_id:
                raise AppError("空间不属于指定园区", code="SPACE_PARK_MISMATCH", status_code=400)
            park_id = int(node.park_id)
            building_ids = self._subtree_ids(park_id, space_id)
        return {
            "park_id": park_id,
            "building_ids": building_ids,
            "status": filters.get("status"),
            "usage_type": filters.get("usage_type"),
            "keyword": filters.get("keyword"),
        }

    def _subtree_ids(self, park_id: int, root_id: int) -> list[int]:
        rows = self.spaces.list_tree_nodes(park_id)
        children: dict[int, list[int]] = {}
        for row in rows:
            if row.parent_id is not None:
                children.setdefault(int(row.parent_id), []).append(int(row.id))
        result: list[int] = []
        stack = [root_id]
        while stack:
            current = stack.pop()
            result.append(current)
            stack.extend(children.get(current, []))
        return result

    def _space_map(self, park_ids: set[int]):
        result = {}
        for park_id in park_ids:
            for row in self.spaces.list_tree_nodes(park_id):
                result[int(row.id)] = row
        return result

    @staticmethod
    def _unit_row(model, node) -> dict[str, Any]:
        entity = UnitMapper.to_entity(model)
        data = UnitService._to_dict(entity)
        data.update(
            {
                "available_area": float(Decimal(str(model.rentable_area or 0)) - Decimal(str(model.used_area or 0))),
                "space_code": node.code if node else None,
                "space_name": node.name if node else None,
                "space_type": node.node_type if node else None,
            }
        )
        return data

    @staticmethod
    def _analysis_bucket(key: str) -> dict[str, Any]:
        return {"key": key, "inventory_count": 0, "rentable_area": 0.0, "used_area": 0.0, "available_area": 0.0, "asking_rent_potential": 0.0, "status_counts": {}}

    @staticmethod
    def _add_analysis(bucket: dict[str, Any], row: Any, potential: Decimal) -> None:
        rentable = Decimal(str(row.rentable_area or 0))
        used = Decimal(str(row.used_area or 0))
        bucket["inventory_count"] += 1
        bucket["rentable_area"] += float(rentable)
        bucket["used_area"] += float(used)
        bucket["available_area"] += float(rentable - used)
        bucket["asking_rent_potential"] += float(potential)
        bucket["status_counts"][row.status] = bucket["status_counts"].get(row.status, 0) + 1

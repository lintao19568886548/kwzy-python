"""Scoped rent-control query application service."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.park_property.application.unit_service import UnitService
from app.modules.park_property.infrastructure.building_repository import BuildingRepository
from app.modules.park_property.infrastructure.mappers import UnitMapper
from app.modules.park_property.infrastructure.rent_control_repository import RentControlRepository
from app.modules.park_property.infrastructure.unit_lineage_repository import UnitLineageRepository
from app.modules.park_property.infrastructure.unit_repository import UnitRepository
from app.shared.tenant_context import TenantContext


class RentControlService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.ctx = ctx
        self.units = UnitRepository(session, ctx)
        self.spaces = BuildingRepository(session, ctx)
        self.relations = RentControlRepository(session, ctx)
        self.lineages = UnitLineageRepository(session, ctx)

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

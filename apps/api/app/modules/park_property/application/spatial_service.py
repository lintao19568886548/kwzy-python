"""Typed spatial hierarchy application service."""

from __future__ import annotations

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.modules.park_property.domain.entities import BuildingEntity
from app.modules.park_property.infrastructure.building_repository import BuildingRepository
from app.modules.park_property.infrastructure.mappers import BuildingMapper
from app.modules.park_property.infrastructure.park_repository import ParkRepository
from app.shared.tenant_context import TenantContext

NODE_TYPES = {"AREA", "BUILDING", "FLOOR"}
NODE_STATUSES = {"ACTIVE", "INACTIVE"}


class SpatialService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.repo = BuildingRepository(session, ctx)
        self.parks = ParkRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def tree(self, park_id: int) -> list[dict[str, Any]]:
        if self.parks.get_by_id(park_id) is None:
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        rows = [self._to_dict(BuildingMapper.to_entity(row)) for row in self.repo.list_tree_nodes(park_id)]
        by_parent: dict[int | None, list[dict[str, Any]]] = {}
        for row in rows:
            by_parent.setdefault(row["parent_id"], []).append(row)

        def children(parent_id: int | None) -> list[dict[str, Any]]:
            result = []
            for row in by_parent.get(parent_id, []):
                item = dict(row)
                item["children"] = children(int(row["id"]))
                result.append(item)
            return result

        return children(None)

    def get(self, node_id: int) -> dict[str, Any]:
        node = self.repo.get_by_id(node_id)
        if node is None:
            raise AppError("空间节点不存在", code="SPACE_NOT_FOUND", status_code=404)
        return self._to_dict(BuildingMapper.to_entity(node))

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        park_id = int(data["park_id"])
        if self.parks.get_by_id(park_id) is None:
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        code = self._code(data.get("code"))
        name = str(data.get("name") or "").strip()
        if not name:
            raise AppError("空间名称必填", code="VALIDATION_ERROR", status_code=400)
        node_type = self._node_type(data.get("node_type"))
        status = self._status(data.get("status") or "ACTIVE")
        parent_id = data.get("parent_id")
        parent = self._parent(park_id, int(parent_id) if parent_id is not None else None)
        self._validate_parent(node_type, parent)
        self._assert_unique(park_id, parent.id if parent else None, code)
        entity = BuildingEntity(
            tenant_id=self.ctx.tenant_id,
            park_id=park_id,
            parent_id=int(parent.id) if parent else None,
            code=code,
            name=name,
            node_type=node_type,
            building_type=str(data.get("building_type") or "FACTORY").upper(),
            sort_order=int(data.get("sort_order") or 0),
            status=status,
            address=str(data.get("address") or ""),
            description=data.get("description"),
            attributes=data.get("attributes"),
        )
        model = BuildingMapper.new_model(entity)
        try:
            self.repo.add(model)
            self.audit.record(
                action="create",
                resource_type="SPATIAL_NODE",
                resource_id=model.id,
                park_id=park_id,
                detail={"node_type": node_type, "parent_id": entity.parent_id},
            )
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError("同级空间编码已存在", code="SPACE_CODE_CONFLICT", status_code=409) from exc
        self.session.refresh(model)
        return self._to_dict(BuildingMapper.to_entity(model))

    def update(self, node_id: int, data: dict[str, Any]) -> dict[str, Any]:
        model = self.repo.get_for_update(node_id)
        if model is None:
            raise AppError("空间节点不存在", code="SPACE_NOT_FOUND", status_code=404)
        entity = BuildingMapper.to_entity(model)
        parent_id = data.get("parent_id", entity.parent_id)
        parent = self._parent(entity.park_id, int(parent_id) if parent_id is not None else None)
        node_type = self._node_type(data.get("node_type") or entity.node_type)
        self._validate_parent(node_type, parent)
        if node_type != entity.node_type:
            subtree_ids = self._subtree_ids(entity.park_id, node_id)
            if len(subtree_ids) > 1 or self.repo.has_any_units([node_id]):
                raise AppError(
                    "存在子空间或单元时不能变更空间类型",
                    code="SPACE_TYPE_IN_USE",
                    status_code=409,
                )
        if parent and (parent.id == node_id or self._is_descendant(parent.id, node_id, entity.park_id)):
            raise AppError("空间层级不可形成循环", code="SPACE_CYCLE", status_code=400)
        code = self._code(data.get("code") or entity.code)
        self._assert_unique(entity.park_id, parent.id if parent else None, code, exclude_id=node_id)
        entity.parent_id = int(parent.id) if parent else None
        entity.code = code
        entity.node_type = node_type
        if "name" in data:
            entity.name = str(data["name"] or "").strip()
        if not entity.name:
            raise AppError("空间名称必填", code="VALIDATION_ERROR", status_code=400)
        if "sort_order" in data and data["sort_order"] is not None:
            entity.sort_order = int(data["sort_order"])
        if "status" in data and data["status"] is not None:
            entity.status = self._status(data["status"])
        if "address" in data:
            entity.address = str(data["address"] or "")
        if "description" in data:
            entity.description = data["description"]
        if "attributes" in data:
            entity.attributes = data["attributes"]
        BuildingMapper.apply_entity(model, entity)
        try:
            self.repo.save(model)
            self.audit.record(
                action="update",
                resource_type="SPATIAL_NODE",
                resource_id=model.id,
                park_id=model.park_id,
                detail={"fields": sorted(data.keys()), "parent_id": model.parent_id},
            )
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError("同级空间编码已存在", code="SPACE_CODE_CONFLICT", status_code=409) from exc
        self.session.refresh(model)
        return self._to_dict(BuildingMapper.to_entity(model))

    def deactivate(self, node_id: int) -> dict[str, Any]:
        model = self.repo.get_for_update(node_id)
        if model is None:
            raise AppError("空间节点不存在", code="SPACE_NOT_FOUND", status_code=404)
        node_ids = self._subtree_ids(model.park_id, node_id)
        if self.repo.has_operational_units(node_ids):
            raise AppError(
                "空间下仍有在用出租单元，不能停用",
                code="SPACE_IN_USE",
                status_code=409,
            )
        if self.repo.has_active_descendants(node_ids, node_id):
            raise AppError(
                "空间下仍有启用的子节点，不能停用",
                code="SPACE_ACTIVE_DESCENDANTS",
                status_code=409,
            )
        model.status = "INACTIVE"
        self.repo.save(model)
        self.audit.record(
            action="deactivate",
            resource_type="SPATIAL_NODE",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"subtree_size": len(node_ids)},
        )
        self.session.commit()
        self.session.refresh(model)
        return self._to_dict(BuildingMapper.to_entity(model))

    def _parent(self, park_id: int, parent_id: int | None):
        if parent_id is None:
            return None
        parent = self.repo.get_by_id(parent_id)
        if parent is None or int(parent.park_id) != park_id:
            raise AppError("父空间不存在或不属于该园区", code="SPACE_PARENT_INVALID", status_code=400)
        return parent

    @staticmethod
    def _validate_parent(node_type: str, parent) -> None:
        parent_type = str(parent.node_type).upper() if parent else None
        valid = (
            (node_type == "AREA" and parent is None)
            or (node_type == "BUILDING" and parent_type in {None, "AREA"})
            or (node_type == "FLOOR" and parent_type == "BUILDING")
        )
        if not valid:
            raise AppError("空间父子类型不合法", code="SPACE_PARENT_TYPE_INVALID", status_code=400)
        if parent and parent.status != "ACTIVE":
            raise AppError("父空间已停用", code="SPACE_PARENT_INACTIVE", status_code=409)

    def _assert_unique(
        self,
        park_id: int,
        parent_id: int | None,
        code: str,
        *,
        exclude_id: int | None = None,
    ) -> None:
        if self.repo.find_sibling_code(
            park_id=park_id,
            parent_id=parent_id,
            code=code,
            exclude_id=exclude_id,
        ):
            raise AppError("同级空间编码已存在", code="SPACE_CODE_CONFLICT", status_code=409)

    def _subtree_ids(self, park_id: int, root_id: int) -> list[int]:
        rows = self.repo.list_tree_nodes(park_id)
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

    def _is_descendant(self, candidate_id: int, root_id: int, park_id: int) -> bool:
        return candidate_id in self._subtree_ids(park_id, root_id)[1:]

    @staticmethod
    def _node_type(value: object) -> str:
        result = str(value or "").upper()
        if result not in NODE_TYPES:
            raise AppError("空间类型不合法", code="SPACE_TYPE_INVALID", status_code=400)
        return result

    @staticmethod
    def _status(value: object) -> str:
        result = str(value or "").upper()
        if result not in NODE_STATUSES:
            raise AppError("空间状态不合法", code="SPACE_STATUS_INVALID", status_code=400)
        return result

    @staticmethod
    def _code(value: object) -> str:
        result = str(value or "").strip().upper()
        if not result:
            raise AppError("空间编码必填", code="VALIDATION_ERROR", status_code=400)
        return result

    @staticmethod
    def _to_dict(entity: BuildingEntity) -> dict[str, Any]:
        return {
            "id": entity.id,
            "tenant_id": entity.tenant_id,
            "park_id": entity.park_id,
            "parent_id": entity.parent_id,
            "code": entity.code,
            "name": entity.name,
            "node_type": entity.node_type,
            "building_type": entity.building_type,
            "sort_order": entity.sort_order,
            "status": entity.status,
            "address": entity.address,
            "description": entity.description,
            "attributes": entity.attributes,
            "created_at": entity.created_at.isoformat() if entity.created_at else None,
            "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        }

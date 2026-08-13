from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, or_, select

from app.infrastructure.database.models.park_property import Building
from app.infrastructure.database.repository_base import TenantParkRepositoryBase


class BuildingRepository(TenantParkRepositoryBase[Building]):
    model = Building
    park_field = "park_id"
    uses_soft_delete = True

    def get_default_for_park(self, park_id: int) -> Optional[Building]:
        self.assert_park_in_scope(park_id)
        stmt = (
            self._base_select()
            .where(
                Building.park_id == park_id,
                Building.name == "主楼",
                Building.node_type == "BUILDING",
            )
            .limit(1)
        )
        return self.session.scalars(stmt).first()

    def list_tree_nodes(self, park_id: int) -> Sequence[Building]:
        self.assert_park_in_scope(park_id)
        stmt = (
            self._base_select()
            .where(Building.park_id == park_id)
            .order_by(Building.sort_order, Building.id)
        )
        return list(self.session.scalars(stmt).all())

    def find_sibling_code(
        self,
        *,
        park_id: int,
        parent_id: int | None,
        code: str,
        exclude_id: int | None = None,
    ) -> Optional[Building]:
        self.assert_park_in_scope(park_id)
        stmt = self._base_select().where(
            Building.park_id == park_id,
            Building.code == code,
            Building.parent_id.is_(None) if parent_id is None else Building.parent_id == parent_id,
        )
        if exclude_id is not None:
            stmt = stmt.where(Building.id != exclude_id)
        return self.session.scalars(stmt.limit(1)).first()

    def get_for_update(self, node_id: int) -> Optional[Building]:
        stmt = self.apply_park_scope(
            self._base_select().where(Building.id == node_id)
        ).with_for_update()
        return self.session.scalars(stmt).first()

    def has_operational_units(self, node_ids: list[int]) -> bool:
        if not node_ids:
            return False
        from app.infrastructure.database.models.park_property import Unit

        stmt = select(func.count()).select_from(Unit).where(
            Unit.tenant_id == self.tenant_id,
            Unit.building_id.in_(node_ids),
            Unit.is_deleted.is_(False),
            Unit.valid_to.is_(None),
            or_(Unit.status != "RETIRED", Unit.used_area > 0),
        )
        return int(self.session.scalar(stmt) or 0) > 0

    def has_active_descendants(self, node_ids: list[int], root_id: int) -> bool:
        descendant_ids = [node_id for node_id in node_ids if node_id != root_id]
        if not descendant_ids:
            return False
        stmt = select(func.count()).select_from(Building).where(
            Building.tenant_id == self.tenant_id,
            Building.id.in_(descendant_ids),
            Building.is_deleted.is_(False),
            Building.status == "ACTIVE",
        )
        return int(self.session.scalar(stmt) or 0) > 0

    def has_any_units(self, node_ids: list[int]) -> bool:
        if not node_ids:
            return False
        from app.infrastructure.database.models.park_property import Unit

        stmt = select(func.count()).select_from(Unit).where(
            Unit.tenant_id == self.tenant_id,
            Unit.building_id.in_(node_ids),
            Unit.is_deleted.is_(False),
        )
        return int(self.session.scalar(stmt) or 0) > 0

from __future__ import annotations

from typing import Optional

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
            .where(Building.park_id == park_id, Building.name == "主楼")
            .limit(1)
        )
        return self.session.scalars(stmt).first()

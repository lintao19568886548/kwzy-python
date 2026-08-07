from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select

from app.infrastructure.database.models.park_property import Unit
from app.infrastructure.database.repository_base import TenantParkRepositoryBase


class UnitRepository(TenantParkRepositoryBase[Unit]):
    model = Unit
    park_field = "park_id"
    uses_soft_delete = True

    def list(
        self,
        *,
        park_id: Optional[int] = None,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[Unit]:
        stmt = self._base_select()
        if park_id is not None:
            self.assert_park_in_scope(park_id)
            stmt = stmt.where(Unit.park_id == park_id)
        else:
            stmt = self.apply_park_scope(stmt)
        if status:
            stmt = stmt.where(Unit.status == status)
        stmt = stmt.order_by(Unit.id.desc()).offset(offset).limit(limit)
        return list(self.session.scalars(stmt).all())

    def count(
        self,
        *,
        park_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(Unit).where(
            Unit.tenant_id == self.tenant_id,
            Unit.is_deleted.is_(False),
        )
        if park_id is not None:
            self.assert_park_in_scope(park_id)
            stmt = stmt.where(Unit.park_id == park_id)
        elif not self.ctx.has_all_park_access:
            if not self.ctx.park_ids:
                return 0
            stmt = stmt.where(Unit.park_id.in_(self.ctx.park_ids))
        if status:
            stmt = stmt.where(Unit.status == status)
        return int(self.session.scalar(stmt) or 0)

    def find_by_building_code(self, building_id: int, code: str) -> Optional[Unit]:
        stmt = self._base_select().where(
            Unit.building_id == building_id,
            Unit.code == code,
        )
        return self.session.scalars(stmt).first()

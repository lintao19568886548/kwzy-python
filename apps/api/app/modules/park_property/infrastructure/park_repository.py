from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select

from app.infrastructure.database.models.park_property import Park
from app.infrastructure.database.repository_base import TenantParkRepositoryBase


class ParkRepository(TenantParkRepositoryBase[Park]):
    model = Park
    park_field = "id"  # park list scopes by park.id
    uses_soft_delete = True

    def apply_park_scope(self, stmt):  # type: ignore[no-untyped-def]
        if self.ctx.has_all_park_access:
            return stmt
        if not self.ctx.park_ids:
            return stmt.where(False)
        return stmt.where(Park.id.in_(self.ctx.park_ids))

    def list(
        self,
        *,
        park_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 20,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Sequence[Park]:
        stmt = self._base_select()
        stmt = self.apply_park_scope(stmt)
        if park_id is not None:
            self.assert_park_in_scope(park_id)
            stmt = stmt.where(Park.id == park_id)
        if keyword:
            stmt = stmt.where(Park.name.contains(keyword))
        if status:
            stmt = stmt.where(Park.status == status)
        stmt = stmt.order_by(Park.id.desc()).offset(offset).limit(limit)
        return list(self.session.scalars(stmt).all())

    def count(
        self,
        *,
        park_id: Optional[int] = None,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(Park).where(
            Park.tenant_id == self.tenant_id,
            Park.is_deleted.is_(False),
        )
        if not self.ctx.has_all_park_access:
            if not self.ctx.park_ids:
                return 0
            stmt = stmt.where(Park.id.in_(self.ctx.park_ids))
        if park_id is not None:
            self.assert_park_in_scope(park_id)
            stmt = stmt.where(Park.id == park_id)
        if keyword:
            stmt = stmt.where(Park.name.contains(keyword))
        if status:
            stmt = stmt.where(Park.status == status)
        return int(self.session.scalar(stmt) or 0)

    def get_by_id(self, entity_id: int) -> Optional[Park]:
        stmt = self._base_select().where(Park.id == entity_id)
        stmt = self.apply_park_scope(stmt)
        return self.session.scalars(stmt).first()

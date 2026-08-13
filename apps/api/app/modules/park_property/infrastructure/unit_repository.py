from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import or_, select

from app.infrastructure.database.models.park_property import Unit
from app.infrastructure.database.repository_base import TenantParkRepositoryBase


class UnitRepository(TenantParkRepositoryBase[Unit]):
    model = Unit
    park_field = "park_id"
    uses_soft_delete = True

    def _current_select(self):
        return self._base_select().where(Unit.valid_to.is_(None))

    def get_current_by_id(self, unit_id: int) -> Optional[Unit]:
        stmt = self.apply_park_scope(
            self._current_select().where(Unit.id == unit_id)
        )
        return self.session.scalars(stmt).first()

    def get_current_for_update(self, unit_id: int) -> Optional[Unit]:
        stmt = self.apply_park_scope(
            self._current_select().where(Unit.id == unit_id)
        ).with_for_update()
        return self.session.scalars(stmt).first()

    def get_currents_for_update(self, unit_ids: list[int]) -> list[Unit]:
        if not unit_ids:
            return []
        stmt = self.apply_park_scope(
            self._current_select().where(Unit.id.in_(sorted(set(unit_ids))))
        ).order_by(Unit.id).with_for_update()
        return list(self.session.scalars(stmt).all())

    def history(self, logical_id: str) -> list[Unit]:
        stmt = self.apply_park_scope(
            self._base_select().where(Unit.logical_id == logical_id)
        ).order_by(Unit.version_no.desc())
        return list(self.session.scalars(stmt).all())

    def list(
        self,
        *,
        park_id: Optional[int] = None,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[Unit]:
        stmt = self._current_select()
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
            Unit.valid_to.is_(None),
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
        stmt = self._current_select().where(
            Unit.building_id == building_id,
            Unit.code == code,
        )
        return self.session.scalars(stmt).first()

    def list_current_filtered(
        self,
        *,
        park_id: int | None = None,
        building_ids: list[int] | None = None,
        status: str | None = None,
        usage_type: str | None = None,
        keyword: str | None = None,
        offset: int = 0,
        limit: int = 200,
    ) -> list[Unit]:
        stmt = self.filtered_current_stmt(
            park_id=park_id,
            building_ids=building_ids,
            status=status,
            usage_type=usage_type,
            keyword=keyword,
        )
        stmt = stmt.order_by(Unit.park_id, Unit.building_id, Unit.code, Unit.id).offset(offset).limit(limit)
        return list(self.session.scalars(stmt).all())

    def filtered_current_stmt(
        self,
        *,
        park_id: int | None = None,
        building_ids: list[int] | None = None,
        status: str | None = None,
        usage_type: str | None = None,
        keyword: str | None = None,
    ):
        stmt = self._current_select()
        if park_id is not None:
            self.assert_park_in_scope(park_id)
            stmt = stmt.where(Unit.park_id == park_id)
        else:
            stmt = self.apply_park_scope(stmt)
        if building_ids is not None:
            if not building_ids:
                return stmt.where(False)
            stmt = stmt.where(Unit.building_id.in_(building_ids))
        if status:
            stmt = stmt.where(Unit.status == status.upper())
        if usage_type:
            stmt = stmt.where(Unit.usage_type == usage_type.upper())
        if keyword:
            term = f"%{keyword.strip()}%"
            stmt = stmt.where(or_(Unit.code.ilike(term), Unit.name.ilike(term)))
        return stmt

    def count_current_filtered(self, **filters) -> int:
        from sqlalchemy import func

        stmt = self.filtered_current_stmt(**filters).with_only_columns(Unit.id).order_by(None)
        return int(self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)

    def all_current_filtered(self, **filters) -> list[Unit]:
        stmt = self.filtered_current_stmt(**filters).order_by(Unit.park_id, Unit.building_id, Unit.code, Unit.id)
        return list(self.session.scalars(stmt).all())

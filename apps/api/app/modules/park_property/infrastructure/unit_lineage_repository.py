from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.models.park_property import UnitLineage
from app.shared.tenant_context import TenantContext


class UnitLineageRepository:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def add_edge(
        self,
        *,
        park_id: int,
        operation_id: str,
        operation_type: str,
        source_unit_id: int,
        target_unit_id: int,
    ) -> UnitLineage:
        if not self.ctx.allows_park(park_id):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        row = UnitLineage(
            tenant_id=self.ctx.tenant_id,
            park_id=park_id,
            operation_id=operation_id,
            operation_type=operation_type,
            source_unit_id=source_unit_id,
            target_unit_id=target_unit_id,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def list_for_unit(self, unit_id: int) -> list[UnitLineage]:
        stmt = select(UnitLineage).where(
            UnitLineage.tenant_id == self.ctx.tenant_id,
            or_(
                UnitLineage.source_unit_id == unit_id,
                UnitLineage.target_unit_id == unit_id,
            ),
        )
        if not self.ctx.has_all_park_access:
            if not self.ctx.park_ids:
                return []
            stmt = stmt.where(UnitLineage.park_id.in_(self.ctx.park_ids))
        return list(self.session.scalars(stmt.order_by(UnitLineage.id)).all())

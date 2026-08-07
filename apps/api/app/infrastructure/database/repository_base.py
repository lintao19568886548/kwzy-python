"""Tenant + park scoped repository base (ADR-004 / ADR-005)."""

from __future__ import annotations

from typing import Generic, Optional, Sequence, Type, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.base import Base
from app.shared.tenant_context import TenantContext

ModelT = TypeVar("ModelT", bound=Base)


class TenantParkRepositoryBase(Generic[ModelT]):
    """
    All queries must include tenant_id.
    Park-scoped resources also enforce DataScope.
    """

    model: Type[ModelT]
    park_field: str = "park_id"
    uses_soft_delete: bool = True

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    @property
    def tenant_id(self) -> int:
        return self.ctx.tenant_id

    def _base_select(self) -> Select[tuple[ModelT]]:
        stmt = select(self.model).where(self.model.tenant_id == self.tenant_id)  # type: ignore[attr-defined]
        if self.uses_soft_delete and hasattr(self.model, "is_deleted"):
            stmt = stmt.where(self.model.is_deleted.is_(False))  # type: ignore[attr-defined]
        return stmt

    def apply_park_scope(self, stmt: Select[tuple[ModelT]]) -> Select[tuple[ModelT]]:
        if self.ctx.has_all_park_access:
            return stmt
        if not self.ctx.park_ids:
            # no parks allowed → empty
            return stmt.where(False)
        col = getattr(self.model, self.park_field)
        return stmt.where(col.in_(self.ctx.park_ids))

    def assert_park_in_scope(self, park_id: int) -> None:
        if not self.ctx.allows_park(park_id):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)

    def get_by_id(self, entity_id: int) -> Optional[ModelT]:
        stmt = self._base_select().where(self.model.id == entity_id)  # type: ignore[attr-defined]
        if hasattr(self.model, self.park_field) and not self.ctx.has_all_park_access:
            stmt = self.apply_park_scope(stmt)
        return self.session.scalars(stmt).first()

    def list(
        self,
        *,
        park_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[ModelT]:
        stmt = self._base_select()
        if hasattr(self.model, self.park_field):
            if park_id is not None:
                self.assert_park_in_scope(park_id)
                stmt = stmt.where(getattr(self.model, self.park_field) == park_id)
            else:
                stmt = self.apply_park_scope(stmt)
        stmt = stmt.offset(offset).limit(limit).order_by(self.model.id.desc())  # type: ignore[attr-defined]
        return list(self.session.scalars(stmt).all())

    def count(self, *, park_id: Optional[int] = None) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(self.model).where(
            self.model.tenant_id == self.tenant_id  # type: ignore[attr-defined]
        )
        if self.uses_soft_delete and hasattr(self.model, "is_deleted"):
            stmt = stmt.where(self.model.is_deleted.is_(False))  # type: ignore[attr-defined]
        if hasattr(self.model, self.park_field):
            if park_id is not None:
                self.assert_park_in_scope(park_id)
                stmt = stmt.where(getattr(self.model, self.park_field) == park_id)
            elif not self.ctx.has_all_park_access:
                if not self.ctx.park_ids:
                    return 0
                stmt = stmt.where(getattr(self.model, self.park_field).in_(self.ctx.park_ids))
        return int(self.session.scalar(stmt) or 0)

    def add(self, entity: ModelT) -> ModelT:
        # Always stamp tenant from context (prevent client spoofing).
        if hasattr(entity, "tenant_id"):
            entity.tenant_id = self.tenant_id  # type: ignore[attr-defined]
        # Park-scoped resources: validate park_id field (not when park_field is PK "id"
        # on create, where id is still None).
        if self.park_field != "id" and hasattr(entity, self.park_field):
            park_id = getattr(entity, self.park_field)
            if park_id is not None:
                self.assert_park_in_scope(int(park_id))
        self.session.add(entity)
        self.session.flush()
        return entity

    def save(self, entity: ModelT) -> ModelT:
        if hasattr(entity, "tenant_id") and int(entity.tenant_id) != self.tenant_id:  # type: ignore[attr-defined]
            raise AppError("租户不匹配", code="TENANT_MISMATCH", status_code=403)
        if self.park_field != "id" and hasattr(entity, self.park_field):
            park_id = getattr(entity, self.park_field)
            if park_id is not None:
                self.assert_park_in_scope(int(park_id))
        self.session.add(entity)
        self.session.flush()
        return entity

    def soft_delete(self, entity: ModelT) -> None:
        if hasattr(entity, "is_deleted"):
            entity.is_deleted = True  # type: ignore[attr-defined]
            self.session.flush()
        else:
            self.session.delete(entity)
            self.session.flush()

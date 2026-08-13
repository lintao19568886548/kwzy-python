"""Repositories for append-only CRM facts and unit locks."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.models.investment import (
    LeadActivity,
    LeadAssignmentEvent,
    LeadMergeLink,
    LeadUnitLock,
)
from app.infrastructure.database.models.identity import User
from app.shared.tenant_context import ParkScopeMode, TenantContext


class _ScopedRepository:
    model = None

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def _scope(self, stmt):
        stmt = stmt.where(self.model.tenant_id == self.ctx.tenant_id)
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(self.model.park_id.in_(list(self.ctx.park_ids)))
        return stmt.where(False)

    def add(self, model):
        if int(model.tenant_id) != self.ctx.tenant_id:
            raise AppError("租户不匹配", code="TENANT_MISMATCH", status_code=403)
        self.session.add(model)
        self.session.flush()
        return model


class LeadAssigneeRepository:
    """Tenant-scoped active-user lookup used by CRM assignment commands."""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def active_id(self, user_id: int) -> Optional[int]:
        value = self.session.scalar(
            select(User.id).where(
                User.id == int(user_id),
                User.tenant_id == self.ctx.tenant_id,
                User.status == "ACTIVE",
            )
        )
        return int(value) if value is not None else None

    def list_active(self) -> list[dict[str, object]]:
        rows = list(
            self.session.scalars(
                select(User)
                .where(
                    User.tenant_id == self.ctx.tenant_id,
                    User.status == "ACTIVE",
                )
                .order_by(User.real_name, User.username, User.id)
            ).all()
        )
        return [
            {"id": int(row.id), "username": row.username, "real_name": row.real_name}
            for row in rows
        ]


class LeadActivityRepository(_ScopedRepository):
    model = LeadActivity

    def list_for_lead(self, lead_id: int) -> Sequence[LeadActivity]:
        stmt = self._scope(select(LeadActivity).where(LeadActivity.lead_id == lead_id))
        return list(
            self.session.scalars(
                stmt.order_by(LeadActivity.occurred_at.desc(), LeadActivity.id.desc())
            ).all()
        )


class LeadAssignmentRepository(_ScopedRepository):
    model = LeadAssignmentEvent

    def list_for_lead(self, lead_id: int) -> Sequence[LeadAssignmentEvent]:
        stmt = self._scope(
            select(LeadAssignmentEvent).where(LeadAssignmentEvent.lead_id == lead_id)
        )
        return list(
            self.session.scalars(
                stmt.order_by(
                    LeadAssignmentEvent.occurred_at.desc(),
                    LeadAssignmentEvent.id.desc(),
                )
            ).all()
        )


class LeadMergeRepository(_ScopedRepository):
    model = LeadMergeLink

    def list_for_target(self, lead_id: int) -> Sequence[LeadMergeLink]:
        stmt = self._scope(
            select(LeadMergeLink).where(LeadMergeLink.target_lead_id == lead_id)
        )
        return list(self.session.scalars(stmt.order_by(LeadMergeLink.id)).all())

    def get_for_source(self, lead_id: int) -> Optional[LeadMergeLink]:
        stmt = self._scope(
            select(LeadMergeLink).where(LeadMergeLink.source_lead_id == lead_id)
        )
        return self.session.scalars(stmt).first()


class LeadUnitLockRepository(_ScopedRepository):
    model = LeadUnitLock

    def get_by_id(self, lock_id: int, *, for_update: bool = False) -> Optional[LeadUnitLock]:
        stmt = self._scope(select(LeadUnitLock).where(LeadUnitLock.id == lock_id))
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def active_for_unit(self, unit_id: int, *, for_update: bool = False) -> Optional[LeadUnitLock]:
        stmt = self._scope(
            select(LeadUnitLock).where(
                LeadUnitLock.unit_id == unit_id,
                LeadUnitLock.status == "ACTIVE",
            )
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def active_for_lead(self, lead_id: int) -> Sequence[LeadUnitLock]:
        stmt = self._scope(
            select(LeadUnitLock).where(
                LeadUnitLock.lead_id == lead_id,
                LeadUnitLock.status == "ACTIVE",
            )
        )
        return list(self.session.scalars(stmt.order_by(LeadUnitLock.id)).all())

    def list_for_lead(self, lead_id: int) -> Sequence[LeadUnitLock]:
        stmt = self._scope(select(LeadUnitLock).where(LeadUnitLock.lead_id == lead_id))
        return list(self.session.scalars(stmt.order_by(LeadUnitLock.id.desc())).all())

    def expired_active(self, now: datetime, *, park_id: Optional[int] = None) -> Sequence[LeadUnitLock]:
        stmt = self._scope(
            select(LeadUnitLock).where(
                LeadUnitLock.status == "ACTIVE",
                LeadUnitLock.expires_at <= now,
            )
        )
        if park_id is not None:
            stmt = stmt.where(LeadUnitLock.park_id == int(park_id))
        # Candidates only. Callers lock Unit first, then re-read the lock FOR UPDATE
        # to preserve the global Unit -> LeadUnitLock write-lock order.
        return list(self.session.scalars(stmt.order_by(LeadUnitLock.id)).all())

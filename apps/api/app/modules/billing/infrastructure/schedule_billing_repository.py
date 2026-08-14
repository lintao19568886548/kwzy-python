"""Lease schedule read/write port used only by deterministic Billing generation."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.infrastructure.database.models.lease import LeaseContract, LeasePerformanceSchedule
from app.shared.tenant_context import ParkScopeMode, TenantContext


class ScheduleBillingRepository:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def _scope(self, stmt):
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(LeaseContract.park_id.in_(list(self.ctx.park_ids)))
        return stmt.where(False)

    def eligible(
        self, *, as_of: date, park_id: int | None, for_update: bool
    ) -> list[tuple[LeasePerformanceSchedule, LeaseContract]]:
        stmt = (
            select(LeasePerformanceSchedule, LeaseContract)
            .join(LeaseContract, LeaseContract.id == LeasePerformanceSchedule.contract_id)
            .where(
                LeasePerformanceSchedule.tenant_id == self.ctx.tenant_id,
                LeaseContract.tenant_id == self.ctx.tenant_id,
                LeasePerformanceSchedule.contract_version_no == LeaseContract.current_version_no,
                LeasePerformanceSchedule.bill_id.is_(None),
                LeasePerformanceSchedule.period_start <= as_of,
                LeaseContract.status.in_(["ACTIVE", "EXPIRING", "EXIT_PENDING"]),
            )
        )
        stmt = self._scope(stmt)
        if park_id is not None:
            stmt = stmt.where(LeaseContract.park_id == int(park_id))
        stmt = stmt.order_by(
            LeaseContract.park_id,
            LeasePerformanceSchedule.contract_id,
            LeasePerformanceSchedule.period_start,
            LeasePerformanceSchedule.id,
        )
        if (
            for_update
            and self.session.bind is not None
            and self.session.bind.dialect.name == "postgresql"
        ):
            stmt = stmt.with_for_update(of=LeasePerformanceSchedule)
        return list(self.session.execute(stmt).all())

    def billed_overlaps(
        self, rows: list[LeasePerformanceSchedule]
    ) -> dict[tuple[int, str, date, date], LeasePerformanceSchedule]:
        """Load historical billed-period conflicts in one query for preview/apply."""

        keys = {
            (
                int(row.contract_id),
                str(row.charge_code),
                row.period_start,
                row.period_end,
            )
            for row in rows
        }
        if not keys:
            return {}
        stmt = (
            select(LeasePerformanceSchedule)
            .where(
                LeasePerformanceSchedule.tenant_id == self.ctx.tenant_id,
                LeasePerformanceSchedule.bill_id.is_not(None),
                tuple_(
                    LeasePerformanceSchedule.contract_id,
                    LeasePerformanceSchedule.charge_code,
                    LeasePerformanceSchedule.period_start,
                    LeasePerformanceSchedule.period_end,
                ).in_(keys),
            )
            .order_by(LeasePerformanceSchedule.id)
        )
        overlaps: dict[tuple[int, str, date, date], LeasePerformanceSchedule] = {}
        for row in self.session.scalars(stmt):
            key = (
                int(row.contract_id),
                str(row.charge_code),
                row.period_start,
                row.period_end,
            )
            overlaps.setdefault(key, row)
        return overlaps

    def mark_billed(self, row: LeasePerformanceSchedule, *, bill_id: int, billed_at) -> None:
        row.bill_id = int(bill_id)
        row.billed_at = billed_at
        row.status = "BILLED"
        self.session.add(row)
        self.session.flush()

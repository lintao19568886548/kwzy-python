from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.facility_ops import WorkOrder
from app.infrastructure.database.models.lease import LeaseContract, LeaseContractUnit
from app.infrastructure.database.models.party import Party
from app.shared.tenant_context import TenantContext


class RentControlRepository:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def effective_leases(self, unit_id: int, park_id: int) -> list[dict]:
        if not self.ctx.allows_park(park_id):
            return []
        stmt = (
            select(LeaseContractUnit, LeaseContract, Party)
            .join(LeaseContract, LeaseContract.id == LeaseContractUnit.contract_id)
            .join(Party, Party.id == LeaseContract.party_id)
            .where(
                LeaseContractUnit.tenant_id == self.ctx.tenant_id,
                LeaseContract.tenant_id == self.ctx.tenant_id,
                Party.tenant_id == self.ctx.tenant_id,
                LeaseContract.park_id == park_id,
                LeaseContractUnit.unit_id == unit_id,
                LeaseContract.status.in_(["ACTIVE", "EXPIRING"]),
            )
            .order_by(LeaseContract.end_date, LeaseContract.id)
        )
        return [
            {
                "contract_id": contract.id,
                "contract_no": contract.contract_no,
                "contract_status": contract.status,
                "party_id": party.id,
                "party_name": party.name,
                "occupied_area": float(line.occupied_area or 0),
                "start_date": contract.start_date.isoformat(),
                "end_date": contract.end_date.isoformat(),
            }
            for line, contract, party in self.session.execute(stmt).all()
        ]

    def work_orders(self, unit_id: int, park_id: int) -> list[dict]:
        if not self.ctx.allows_park(park_id):
            return []
        stmt = (
            select(WorkOrder)
            .where(
                WorkOrder.tenant_id == self.ctx.tenant_id,
                WorkOrder.park_id == park_id,
                WorkOrder.unit_id == unit_id,
            )
            .order_by(WorkOrder.id.desc())
            .limit(20)
        )
        return [
            {
                "id": row.id,
                "title": row.title,
                "status": row.status,
                "priority": row.priority,
                "due_at": row.due_at.isoformat() if row.due_at else None,
            }
            for row in self.session.scalars(stmt).all()
        ]

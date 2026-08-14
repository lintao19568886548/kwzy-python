"""Infrastructure adapters for Lease collaboration with foreign contexts."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.modules.attachments.infrastructure.attachment_repository import AttachmentRepository
from app.modules.investment.infrastructure.crm_repository import LeadUnitLockRepository
from app.modules.park_property.infrastructure.park_repository import ParkRepository
from app.modules.park_property.infrastructure.unit_repository import UnitRepository
from app.modules.party.infrastructure.party_repository import PartyRepository
from app.modules.workbench.application.work_item_service import WorkItemService
from app.shared.tenant_context import TenantContext


class ScopedAttachmentEvidenceAdapter:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.repository = AttachmentRepository(session, ctx)

    def get(self, attachment_id: int):
        return self.repository.get(attachment_id)


class ScopedPartyEligibilityAdapter:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.repository = PartyRepository(session, ctx)

    def get_by_id(self, party_id: int):
        return self.repository.get_by_id(party_id)

    def options(
        self, *, park_id: Optional[int] = None, keyword: Optional[str] = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        rows = self.repository.list(
            offset=0,
            limit=limit,
            keyword=keyword,
            # Lease creation permits any scoped, eligible Party; a pre-existing
            # PartyParkRelation is not a prerequisite for becoming a tenant.
            park_id=None,
            include_archived=False,
        )
        return [
            {
                "id": int(row.id),
                "label": row.name,
                "status": row.status,
                "risk_status": row.risk_status,
                "eligible": row.status != "ARCHIVED" and row.risk_status != "BLACKLISTED",
            }
            for row in rows
        ]


class ScopedParkReferenceAdapter:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.repository = ParkRepository(session, ctx)

    def exists_in_tenant(self, park_id: int) -> bool:
        return self.repository.exists_in_tenant(park_id)

    def options(self, *, keyword: Optional[str] = None, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.repository.list(offset=0, limit=limit, keyword=keyword)
        return [
            {"id": int(row.id), "label": row.name, "status": row.status}
            for row in rows
        ]


class CurrentUnitReferenceAdapter:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.repository = UnitRepository(session, ctx)

    def get_current_by_id(self, unit_id: int):
        return self.repository.get_current_by_id(unit_id)

    def get_current_for_update(self, unit_id: int):
        return self.repository.get_current_for_update(unit_id)

    def get_by_id(self, unit_id: int):
        return self.repository.get_by_id(unit_id)

    def options(
        self, *, park_id: Optional[int] = None, keyword: Optional[str] = None, limit: int = 200
    ) -> list[dict[str, Any]]:
        rows = self.repository.list_current_filtered(
            park_id=park_id,
            keyword=keyword,
            offset=0,
            limit=limit,
        )
        return [
            {
                "id": int(row.id),
                "park_id": int(row.park_id),
                "label": f"{row.code} · {row.name}",
                "code": row.code,
                "name": row.name,
                "status": row.status,
                "rentable_area": str(row.rentable_area or 0),
                "used_area": str(row.used_area or 0),
                "available_area": str((row.rentable_area or 0) - (row.used_area or 0)),
            }
            for row in rows
        ]


class CrmUnitLockReadAdapter:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.repository = LeadUnitLockRepository(session, ctx)

    def active_for_unit(self, unit_id: int, *, for_update: bool = False):
        return self.repository.active_for_unit(unit_id, for_update=for_update)


class LeaseWorkItemAdapter:
    """Preserve caller-owned transaction semantics for governance todos."""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.service = WorkItemService(session, ctx)

    def ensure_from_source(self, **kwargs: Any) -> dict[str, Any]:
        kwargs["commit"] = False
        return self.service.ensure_from_source(**kwargs)

    def complete_by_source(self, **kwargs: Any) -> Optional[dict[str, Any]]:
        kwargs["commit"] = False
        return self.service.complete_by_source(**kwargs)

    def cancel_by_source(self, **kwargs: Any) -> Optional[dict[str, Any]]:
        kwargs["commit"] = False
        return self.service.cancel_by_source(**kwargs)

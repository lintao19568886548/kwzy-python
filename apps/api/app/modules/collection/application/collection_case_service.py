"""功能说明：催缴案件最小实现（过程记录）。"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.modules.billing.infrastructure.bill_repository import BillRepository
from app.modules.collection.infrastructure.collection_case_repository import (
    CollectionCaseRepository,
)
from app.modules.park_property.infrastructure.park_repository import ParkRepository
from app.modules.party.infrastructure.party_repository import PartyRepository
from app.shared.tenant_context import TenantContext


class CollectionCaseService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.cases = CollectionCaseRepository(session, ctx)
        self.parks = ParkRepository(session, ctx)
        self.parties = PartyRepository(session, ctx)
        self.bills = BillRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def _to_dict(self, m) -> dict[str, Any]:
        return {
            "id": m.id,
            "park_id": m.park_id,
            "party_id": m.party_id,
            "bill_id": m.bill_id,
            "status": m.status,
            "level": m.level,
            "assignee_user_id": m.assignee_user_id,
            "remark": m.remark,
        }

    def list_cases(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        bill_id: Optional[int] = None,
    ) -> dict[str, Any]:
        if not self.ctx.has_permission("collection:read"):
            raise AppError("无催缴查看权限", code="PERMISSION_DENIED", status_code=403)
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        items = self.cases.list(
            offset=(page - 1) * page_size,
            limit=page_size,
            status=status,
            park_id=park_id,
            bill_id=bill_id,
        )
        total = self.cases.count(status=status, park_id=park_id, bill_id=bill_id)
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [self._to_dict(i) for i in items],
        }

    def create_case(self, data: dict[str, Any]) -> dict[str, Any]:
        if not self.ctx.has_permission("collection:write"):
            raise AppError("无催缴维护权限", code="PERMISSION_DENIED", status_code=403)
        park_id = int(data["park_id"])
        party_id = int(data["party_id"])
        bill_id = int(data["bill_id"])
        if not self.parks.exists_in_tenant(park_id):
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        if not self.ctx.allows_park(park_id):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        if self.parties.get_by_id(party_id) is None:
            raise AppError("主体不存在", code="PARTY_NOT_FOUND", status_code=404)
        bill = self.bills.get_by_id(bill_id)
        if bill is None:
            raise AppError("账单不存在", code="BILL_NOT_FOUND", status_code=404)
        if int(bill.park_id) != park_id or int(bill.party_id) != party_id:
            raise AppError("账单与园区/主体不一致", code="COLLECTION_BILL_MISMATCH", status_code=400)
        model = self.cases.create(
            park_id=park_id,
            party_id=party_id,
            bill_id=bill_id,
            level=str(data.get("level") or "L1"),
            assignee_user_id=int(data["assignee_id"])
            if data.get("assignee_id") is not None
            else None,
            remark=data.get("remark"),
        )
        self.audit.record(
            action="create",
            resource_type="COLLECTION_CASE",
            resource_id=model.id,
            park_id=park_id,
            detail={"bill_id": bill_id},
        )
        self.session.commit()
        return self._to_dict(model)

    def get_case(self, case_id: int) -> dict[str, Any]:
        if not self.ctx.has_permission("collection:read"):
            raise AppError("无催缴查看权限", code="PERMISSION_DENIED", status_code=403)
        model = self.cases.get_by_id(case_id)
        if model is None:
            raise AppError("催缴案件不存在", code="COLLECTION_CASE_NOT_FOUND", status_code=404)
        return self._to_dict(model)

    def update_case(self, case_id: int, data: dict[str, Any]) -> dict[str, Any]:
        if not self.ctx.has_permission("collection:write"):
            raise AppError("无催缴维护权限", code="PERMISSION_DENIED", status_code=403)
        model = self.cases.get_by_id(case_id)
        if model is None:
            raise AppError("催缴案件不存在", code="COLLECTION_CASE_NOT_FOUND", status_code=404)
        if "status" in data and data["status"]:
            model.status = str(data["status"])
        if "level" in data and data["level"]:
            model.level = str(data["level"])
        if "assignee_id" in data:
            model.assignee_user_id = (
                int(data["assignee_id"]) if data["assignee_id"] is not None else None
            )
        if "remark" in data:
            model.remark = data.get("remark")
        self.cases.save(model)
        self.session.commit()
        return self._to_dict(model)

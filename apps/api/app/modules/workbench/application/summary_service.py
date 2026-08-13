"""功能说明：园区运营工作台聚合（只读指标 + 最近待办）。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.billing.infrastructure.bill_repository import BillRepository
from app.modules.lease.infrastructure.lease_repository import LeaseContractRepository
from app.modules.workbench.application.work_item_service import WorkItemService
from app.modules.workbench.infrastructure.work_item_repository import WorkItemRepository
from app.shared.tenant_context import TenantContext


class WorkbenchSummaryService:
    """功能说明：聚合待办、到期合同、未结账单等运营指标（不修改领域状态机）。"""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.items = WorkItemRepository(session, ctx)
        self.work_items = WorkItemService(session, ctx)
        self.leases = LeaseContractRepository(session, ctx)
        self.bills = BillRepository(session, ctx)

    def summary(
        self,
        *,
        park_id: Optional[int] = None,
        expiring_within_days: int = 90,
        todo_limit: int = 10,
    ) -> dict[str, Any]:
        if not self.ctx.has_permission("work_item:read"):
            raise AppError("无工作台查看权限", code="PERMISSION_DENIED", status_code=403)

        open_total = self.items.count(status="OPEN", park_id=park_id)
        open_items = self.items.list(
            status="OPEN", park_id=park_id, offset=0, limit=max(todo_limit, 1)
        )

        now = datetime.utcnow()
        overdue = 0
        due_soon = 0
        horizon = now + timedelta(days=7)
        for it in self.items.list(status="OPEN", park_id=park_id, offset=0, limit=500):
            if it.due_at is None:
                continue
            if it.due_at < now:
                overdue += 1
            elif it.due_at <= horizon:
                due_soon += 1

        unpaid_bills = self.bills.count_open_receivable()
        expiring_contracts = self.leases.count_expiring(within_days=expiring_within_days)

        return {
            "as_of": date.today().isoformat(),
            "park_id": park_id,
            "metrics": {
                "open_todos": open_total,
                "overdue_todos": overdue,
                "due_soon_todos": due_soon,
                "unpaid_bills": unpaid_bills,
                "expiring_contracts": expiring_contracts,
                "expiring_within_days": expiring_within_days,
            },
            "recent_todos": [self.work_items._to_dict(i) for i in open_items[:todo_limit]],
        }

    def sync_lease_expiring_todos(self, *, within_days: int = 90) -> dict[str, Any]:
        """扫描即将到期 ACTIVE 合同，幂等补齐 CONTRACT_EXPIRING 待办。"""

        if not self.ctx.has_permission("work_item:write"):
            raise AppError("无待办维护权限", code="PERMISSION_DENIED", status_code=403)

        from app.modules.lease.application.lease_service import LEASE_EXPIRING_ITEM_TYPE

        contracts = self.leases.list_expiring(within_days=within_days, limit=500)
        created_or_refreshed = 0
        for model in contracts:
            cno = model.contract_no or str(model.id)
            due = None
            if model.end_date is not None:
                due = datetime.combine(model.end_date, datetime.min.time()).isoformat()
            self.work_items.ensure_from_source(
                source_type="LEASE",
                source_id=str(model.id),
                item_type=LEASE_EXPIRING_ITEM_TYPE,
                title=f"合同即将到期 {cno}",
                description=f"end_date={model.end_date} party_id={model.party_id}",
                park_id=int(model.park_id) if model.park_id is not None else None,
                priority="HIGH",
                due_at=due,
                commit=False,
            )
            created_or_refreshed += 1
        self.session.commit()
        return {
            "scanned": len(contracts),
            "ensured": created_or_refreshed,
            "within_days": within_days,
        }

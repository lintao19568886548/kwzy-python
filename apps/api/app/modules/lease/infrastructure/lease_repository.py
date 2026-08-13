"""功能说明：
    Lease 持久化仓储（tenant + park scope）。

业务职责：
    Infrastructure；强制租户与园区可见性。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.models.lease import (
    LeaseContract,
    LeaseContractUnit,
    LeaseTerm,
)
from app.modules.lease.domain.rules import OCCUPYING_STATUSES
from app.shared.tenant_context import ParkScopeMode, TenantContext


class LeaseContractRepository:
    """功能说明：
        合同主档仓储。

    业务职责：
        列表/详情叠加 tenant 与 park scope。
    """

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    @property
    def tenant_id(self) -> int:
        return self.ctx.tenant_id

    def _scope_filter(self, stmt):
        stmt = stmt.where(LeaseContract.tenant_id == self.tenant_id)
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(LeaseContract.park_id.in_(list(self.ctx.park_ids)))
        return stmt.where(False)

    def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        party_id: Optional[int] = None,
    ) -> Sequence[LeaseContract]:
        """功能说明：分页列出可见合同。"""

        stmt = select(LeaseContract)
        stmt = self._scope_filter(stmt)
        if status:
            stmt = stmt.where(LeaseContract.status == status)
        if park_id is not None:
            stmt = stmt.where(LeaseContract.park_id == int(park_id))
        if party_id is not None:
            stmt = stmt.where(LeaseContract.party_id == int(party_id))
        stmt = stmt.order_by(LeaseContract.id.desc()).offset(offset).limit(limit)
        return list(self.session.scalars(stmt).all())

    def count(
        self,
        *,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        party_id: Optional[int] = None,
    ) -> int:
        """功能说明：统计可见合同数。"""

        vis = select(LeaseContract.id)
        vis = self._scope_filter(vis)
        if status:
            vis = vis.where(LeaseContract.status == status)
        if park_id is not None:
            vis = vis.where(LeaseContract.park_id == int(park_id))
        if party_id is not None:
            vis = vis.where(LeaseContract.party_id == int(party_id))
        stmt = select(func.count()).select_from(vis.subquery())
        return int(self.session.scalar(stmt) or 0)

    def list_expiring(
        self,
        *,
        within_days: int = 90,
        as_of: Optional[date] = None,
        limit: int = 200,
    ) -> Sequence[LeaseContract]:
        """功能说明：ACTIVE 且 end_date 在 as_of~as_of+within_days 内的合同。"""

        today = as_of or date.today()
        if within_days < 0:
            within_days = 0
        from datetime import timedelta

        end_limit = today + timedelta(days=int(within_days))
        stmt = self._scope_filter(select(LeaseContract)).where(
            LeaseContract.status.in_(["ACTIVE", "EXPIRING"]),
            LeaseContract.end_date >= today,
            LeaseContract.end_date <= end_limit,
        )
        return list(
            self.session.scalars(
                stmt.order_by(LeaseContract.end_date.asc()).limit(limit)
            ).all()
        )

    def count_expiring(self, *, within_days: int = 90, as_of: Optional[date] = None) -> int:
        today = as_of or date.today()
        from datetime import timedelta

        end_limit = today + timedelta(days=int(within_days))
        vis = self._scope_filter(select(LeaseContract.id)).where(
            LeaseContract.status.in_(["ACTIVE", "EXPIRING"]),
            LeaseContract.end_date >= today,
            LeaseContract.end_date <= end_limit,
        )
        return int(self.session.scalar(select(func.count()).select_from(vis.subquery())) or 0)

    def get_by_id(self, contract_id: int) -> Optional[LeaseContract]:
        """功能说明：按 ID 加载可见合同。"""

        stmt = select(LeaseContract).where(LeaseContract.id == contract_id)
        stmt = self._scope_filter(stmt)
        return self.session.scalars(stmt).first()

    def find_by_contract_no(self, contract_no: str) -> Optional[LeaseContract]:
        """功能说明：租户内按合同号查找。"""

        return self.session.scalars(
            select(LeaseContract).where(
                LeaseContract.tenant_id == self.tenant_id,
                LeaseContract.contract_no == contract_no,
            )
        ).first()

    def add(self, model: LeaseContract) -> LeaseContract:
        model.tenant_id = self.tenant_id
        self.session.add(model)
        self.session.flush()
        return model

    def save(self, model: LeaseContract) -> LeaseContract:
        if int(model.tenant_id) != self.tenant_id:
            raise AppError("租户不匹配", code="TENANT_MISMATCH", status_code=403)
        self.session.add(model)
        self.session.flush()
        return model


class LeaseContractUnitRepository:
    """功能说明：合同占用行仓储。"""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def list_for_contract(self, contract_id: int) -> list[LeaseContractUnit]:
        return list(
            self.session.scalars(
                select(LeaseContractUnit)
                .where(
                    LeaseContractUnit.tenant_id == self.ctx.tenant_id,
                    LeaseContractUnit.contract_id == contract_id,
                )
                .order_by(LeaseContractUnit.id)
            ).all()
        )

    def get(self, line_id: int, contract_id: int) -> Optional[LeaseContractUnit]:
        return self.session.scalars(
            select(LeaseContractUnit).where(
                LeaseContractUnit.tenant_id == self.ctx.tenant_id,
                LeaseContractUnit.contract_id == contract_id,
                LeaseContractUnit.id == line_id,
            )
        ).first()

    def sum_active_occupied_for_unit(
        self, unit_id: int, *, exclude_contract_id: Optional[int] = None
    ) -> Decimal:
        """功能说明：
            汇总 unit 在有效占用合同上的 occupied_area。
        """

        stmt = (
            select(func.coalesce(func.sum(LeaseContractUnit.occupied_area), 0))
            .select_from(LeaseContractUnit)
            .join(LeaseContract, LeaseContract.id == LeaseContractUnit.contract_id)
            .where(
                LeaseContractUnit.tenant_id == self.ctx.tenant_id,
                LeaseContractUnit.unit_id == unit_id,
                LeaseContract.tenant_id == self.ctx.tenant_id,
                LeaseContract.status.in_(list(OCCUPYING_STATUSES)),
            )
        )
        if exclude_contract_id is not None:
            stmt = stmt.where(LeaseContract.id != int(exclude_contract_id))
        raw = self.session.scalar(stmt)
        return Decimal(str(raw or 0))

    def delete_for_contract(self, contract_id: int) -> None:
        rows = self.list_for_contract(contract_id)
        for r in rows:
            self.session.delete(r)
        self.session.flush()

    def add(self, model: LeaseContractUnit) -> LeaseContractUnit:
        model.tenant_id = self.ctx.tenant_id
        self.session.add(model)
        self.session.flush()
        return model

    def save(self, model: LeaseContractUnit) -> LeaseContractUnit:
        self.session.add(model)
        self.session.flush()
        return model


class LeaseTermRepository:
    """功能说明：合同条款仓储。"""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def list_for_contract(self, contract_id: int) -> list[LeaseTerm]:
        return list(
            self.session.scalars(
                select(LeaseTerm)
                .where(
                    LeaseTerm.tenant_id == self.ctx.tenant_id,
                    LeaseTerm.contract_id == contract_id,
                )
                .order_by(LeaseTerm.sort_order, LeaseTerm.id)
            ).all()
        )

    def get(self, term_id: int, contract_id: int) -> Optional[LeaseTerm]:
        return self.session.scalars(
            select(LeaseTerm).where(
                LeaseTerm.tenant_id == self.ctx.tenant_id,
                LeaseTerm.contract_id == contract_id,
                LeaseTerm.id == term_id,
            )
        ).first()

    def delete_for_contract(self, contract_id: int) -> None:
        for r in self.list_for_contract(contract_id):
            self.session.delete(r)
        self.session.flush()

    def add(self, model: LeaseTerm) -> LeaseTerm:
        model.tenant_id = self.ctx.tenant_id
        self.session.add(model)
        self.session.flush()
        return model

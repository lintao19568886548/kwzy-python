"""功能说明：
    Lease 持久化仓储（tenant + park scope）。

业务职责：
    Infrastructure；强制租户与园区可见性。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Iterable, Optional, Sequence

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.models.lease import (
    LeaseContract,
    LeaseContractDocument,
    LeaseContractUnit,
    LeaseContractVersion,
    LeaseChangeOrder,
    LeaseChargeItem,
    LeaseExitItem,
    LeaseExitSettlement,
    LeasePerformanceSchedule,
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

    def _apply_filters(
        self,
        stmt,
        *,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        party_id: Optional[int] = None,
        contract_type: Optional[str] = None,
        approval_status: Optional[str] = None,
        change_status: Optional[str] = None,
        exit_status: Optional[str] = None,
        keyword: Optional[str] = None,
        end_from: Optional[date] = None,
        end_to: Optional[date] = None,
    ):
        stmt = self._scope_filter(stmt)
        if status:
            stmt = stmt.where(LeaseContract.status == status)
        if park_id is not None:
            stmt = stmt.where(LeaseContract.park_id == int(park_id))
        if party_id is not None:
            stmt = stmt.where(LeaseContract.party_id == int(party_id))
        if contract_type:
            stmt = stmt.where(LeaseContract.contract_type == contract_type)
        if approval_status:
            stmt = stmt.where(LeaseContract.approval_status == approval_status)
        if change_status:
            stmt = stmt.where(
                LeaseContract.id.in_(
                    select(LeaseChangeOrder.contract_id).where(
                        LeaseChangeOrder.tenant_id == self.tenant_id,
                        LeaseChangeOrder.status == change_status,
                    )
                )
            )
        if exit_status:
            stmt = stmt.where(
                LeaseContract.id.in_(
                    select(LeaseExitSettlement.contract_id).where(
                        LeaseExitSettlement.tenant_id == self.tenant_id,
                        LeaseExitSettlement.status == exit_status,
                    )
                )
            )
        if keyword:
            escaped = keyword.strip().replace("%", "\\%").replace("_", "\\_")
            stmt = stmt.where(
                or_(
                    LeaseContract.contract_no.ilike(f"%{escaped}%", escape="\\"),
                    LeaseContract.remark.ilike(f"%{escaped}%", escape="\\"),
                    LeaseContract.source_ref.ilike(f"%{escaped}%", escape="\\"),
                )
            )
        if end_from:
            stmt = stmt.where(LeaseContract.end_date >= end_from)
        if end_to:
            stmt = stmt.where(LeaseContract.end_date <= end_to)
        return stmt

    def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        party_id: Optional[int] = None,
        contract_type: Optional[str] = None,
        approval_status: Optional[str] = None,
        change_status: Optional[str] = None,
        exit_status: Optional[str] = None,
        keyword: Optional[str] = None,
        end_from: Optional[date] = None,
        end_to: Optional[date] = None,
    ) -> Sequence[LeaseContract]:
        """功能说明：分页列出可见合同。"""

        stmt = self._apply_filters(
            select(LeaseContract),
            status=status,
            park_id=park_id,
            party_id=party_id,
            contract_type=contract_type,
            approval_status=approval_status,
            change_status=change_status,
            exit_status=exit_status,
            keyword=keyword,
            end_from=end_from,
            end_to=end_to,
        )
        stmt = stmt.order_by(LeaseContract.id.desc()).offset(offset).limit(limit)
        return list(self.session.scalars(stmt).all())

    def count(
        self,
        *,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        party_id: Optional[int] = None,
        contract_type: Optional[str] = None,
        approval_status: Optional[str] = None,
        change_status: Optional[str] = None,
        exit_status: Optional[str] = None,
        keyword: Optional[str] = None,
        end_from: Optional[date] = None,
        end_to: Optional[date] = None,
    ) -> int:
        """功能说明：统计可见合同数。"""

        vis = self._apply_filters(
            select(LeaseContract.id),
            status=status,
            park_id=park_id,
            party_id=party_id,
            contract_type=contract_type,
            approval_status=approval_status,
            change_status=change_status,
            exit_status=exit_status,
            keyword=keyword,
            end_from=end_from,
            end_to=end_to,
        )
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

    def count_expiring(
        self,
        *,
        within_days: int = 90,
        as_of: Optional[date] = None,
        park_id: Optional[int] = None,
    ) -> int:
        today = as_of or date.today()
        from datetime import timedelta

        end_limit = today + timedelta(days=int(within_days))
        vis = self._scope_filter(select(LeaseContract.id)).where(
            LeaseContract.status.in_(["ACTIVE", "EXPIRING"]),
            LeaseContract.end_date >= today,
            LeaseContract.end_date <= end_limit,
        )
        if park_id is not None:
            vis = vis.where(LeaseContract.park_id == int(park_id))
        return int(self.session.scalar(select(func.count()).select_from(vis.subquery())) or 0)

    def count_statuses(
        self, statuses: Iterable[str], *, park_id: Optional[int] = None
    ) -> int:
        normalized = sorted({str(status).upper() for status in statuses})
        if not normalized:
            return 0
        stmt = self._scope_filter(select(LeaseContract.id)).where(
            LeaseContract.status.in_(normalized)
        )
        if park_id is not None:
            stmt = stmt.where(LeaseContract.park_id == int(park_id))
        return int(self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)

    def sum_deposit(
        self, statuses: Iterable[str], *, park_id: Optional[int] = None
    ) -> Decimal:
        normalized = sorted({str(status).upper() for status in statuses})
        if not normalized:
            return Decimal("0")
        stmt = self._scope_filter(select(LeaseContract.deposit_amount)).where(
            LeaseContract.status.in_(normalized)
        )
        if park_id is not None:
            stmt = stmt.where(LeaseContract.park_id == int(park_id))
        total = self.session.scalar(select(func.coalesce(func.sum(stmt.subquery().c.deposit_amount), 0)))
        return Decimal(str(total or 0))

    def get_by_id(self, contract_id: int) -> Optional[LeaseContract]:
        """功能说明：按 ID 加载可见合同。"""

        stmt = select(LeaseContract).where(LeaseContract.id == contract_id)
        stmt = self._scope_filter(stmt)
        return self.session.scalars(stmt).first()

    def get_for_update(self, contract_id: int) -> Optional[LeaseContract]:
        """Lock a visible contract root for a V2 command transaction."""

        stmt = select(LeaseContract).where(LeaseContract.id == int(contract_id)).with_for_update()
        return self.session.scalars(self._scope_filter(stmt)).first()

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


class _ScopedContractChildRepository:
    """Tenant-scoped base for children whose park scope follows their Lease root."""

    model: Any

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def _visible_contract_ids(self):
        stmt = select(LeaseContract.id).where(LeaseContract.tenant_id == self.ctx.tenant_id)
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(LeaseContract.park_id.in_(list(self.ctx.park_ids)))
        return stmt.where(False)

    def _scope(self, stmt):
        return stmt.where(
            self.model.tenant_id == self.ctx.tenant_id,
            self.model.contract_id.in_(self._visible_contract_ids()),
        )

    def add(self, model):
        model.tenant_id = self.ctx.tenant_id
        if int(model.contract_id) not in set(self.session.scalars(self._visible_contract_ids())):
            raise AppError("合同不可见", code="LEASE_NOT_FOUND", status_code=404)
        self.session.add(model)
        self.session.flush()
        return model

    def save(self, model):
        if int(model.tenant_id) != self.ctx.tenant_id:
            raise AppError("租户不匹配", code="TENANT_MISMATCH", status_code=403)
        self.session.add(model)
        self.session.flush()
        return model


class LeaseContractVersionRepository(_ScopedContractChildRepository):
    model = LeaseContractVersion

    def list_for_contract(self, contract_id: int) -> list[LeaseContractVersion]:
        stmt = self._scope(select(self.model)).where(self.model.contract_id == int(contract_id))
        return list(self.session.scalars(stmt.order_by(self.model.version_no)).all())

    def get(self, contract_id: int, version_no: int) -> Optional[LeaseContractVersion]:
        stmt = self._scope(select(self.model)).where(
            self.model.contract_id == int(contract_id), self.model.version_no == int(version_no)
        )
        return self.session.scalars(stmt).first()


class LeaseChargeItemRepository(_ScopedContractChildRepository):
    model = LeaseChargeItem

    def list_for_contract(self, contract_id: int) -> list[LeaseChargeItem]:
        stmt = self._scope(select(self.model)).where(self.model.contract_id == int(contract_id))
        return list(self.session.scalars(stmt.order_by(self.model.sort_order, self.model.id)).all())

    def replace_for_contract(self, contract_id: int, models: Iterable[LeaseChargeItem]) -> None:
        self.session.execute(
            delete(self.model).where(
                self.model.tenant_id == self.ctx.tenant_id,
                self.model.contract_id == int(contract_id),
            )
        )
        for model in models:
            self.add(model)
        self.session.flush()


class LeasePerformanceScheduleRepository(_ScopedContractChildRepository):
    model = LeasePerformanceSchedule

    def list_for_contract(
        self, contract_id: int, *, version_no: Optional[int] = None
    ) -> list[LeasePerformanceSchedule]:
        stmt = self._scope(select(self.model)).where(self.model.contract_id == int(contract_id))
        if version_no is not None:
            stmt = stmt.where(self.model.contract_version_no == int(version_no))
        return list(
            self.session.scalars(
                stmt.order_by(self.model.period_start, self.model.charge_code, self.model.id)
            ).all()
        )

    def replace_version(
        self,
        contract_id: int,
        version_no: int,
        models: Iterable[LeasePerformanceSchedule],
    ) -> None:
        self.session.execute(
            delete(self.model).where(
                self.model.tenant_id == self.ctx.tenant_id,
                self.model.contract_id == int(contract_id),
                self.model.contract_version_no == int(version_no),
            )
        )
        for model in models:
            self.add(model)
        self.session.flush()


class LeaseChangeOrderRepository(_ScopedContractChildRepository):
    model = LeaseChangeOrder

    def list_for_contract(self, contract_id: int) -> list[LeaseChangeOrder]:
        stmt = self._scope(select(self.model)).where(self.model.contract_id == int(contract_id))
        return list(self.session.scalars(stmt.order_by(self.model.id.desc())).all())

    def get(self, change_id: int, *, for_update: bool = False) -> Optional[LeaseChangeOrder]:
        stmt = self._scope(select(self.model)).where(self.model.id == int(change_id))
        if for_update:
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def find_replay(self, idempotency_key: str) -> Optional[LeaseChangeOrder]:
        return self.session.scalars(
            self._scope(select(self.model)).where(self.model.idempotency_key == idempotency_key)
        ).first()

    def list_due_approved(self, as_of: date) -> list[LeaseChangeOrder]:
        return list(
            self.session.scalars(
                self._scope(select(self.model))
                .where(self.model.status == "APPROVED", self.model.effective_date <= as_of)
                .order_by(self.model.effective_date, self.model.id)
            ).all()
        )

    def count_due_approved(self, as_of: date, *, park_id: Optional[int] = None) -> int:
        stmt = self._scope(select(self.model.id)).where(
            self.model.status == "APPROVED", self.model.effective_date <= as_of
        )
        if park_id is not None:
            stmt = stmt.where(self.model.park_id == int(park_id))
        return int(self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)


class LeaseContractDocumentRepository(_ScopedContractChildRepository):
    model = LeaseContractDocument

    def list_for_contract(self, contract_id: int) -> list[LeaseContractDocument]:
        stmt = self._scope(select(self.model)).where(self.model.contract_id == int(contract_id))
        return list(
            self.session.scalars(
                stmt.order_by(self.model.document_type, self.model.document_version, self.model.id)
            ).all()
        )


class LeaseExitSettlementRepository(_ScopedContractChildRepository):
    model = LeaseExitSettlement

    def unresolved_clearance_summary(self, *, park_id: Optional[int] = None) -> dict[str, Any]:
        stmt = self._scope(select(self.model)).where(
            self.model.status == "APPROVED",
            self.model.financial_clearance_status != "CONFIRMED",
            or_(self.model.net_due_from_party > 0, self.model.net_due_to_party > 0),
        )
        if park_id is not None:
            stmt = stmt.where(self.model.park_id == int(park_id))
        rows = list(self.session.scalars(stmt).all())
        amount = sum(
            (Decimal(str(row.net_due_from_party or 0)) + Decimal(str(row.net_due_to_party or 0)) for row in rows),
            Decimal("0"),
        )
        return {"count": len(rows), "amount": amount}

    def list_for_contract(self, contract_id: int) -> list[LeaseExitSettlement]:
        stmt = self._scope(select(self.model)).where(self.model.contract_id == int(contract_id))
        return list(self.session.scalars(stmt.order_by(self.model.id.desc())).all())

    def get(self, settlement_id: int, *, for_update: bool = False) -> Optional[LeaseExitSettlement]:
        stmt = self._scope(select(self.model)).where(self.model.id == int(settlement_id))
        if for_update:
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def get_open_for_contract(self, contract_id: int) -> Optional[LeaseExitSettlement]:
        stmt = self._scope(select(self.model)).where(
            self.model.contract_id == int(contract_id),
            self.model.status.in_(["DRAFT", "SUBMITTED", "APPROVED"]),
        )
        return self.session.scalars(stmt).first()

    def find_replay(self, idempotency_key: str) -> Optional[LeaseExitSettlement]:
        return self.session.scalars(
            self._scope(select(self.model)).where(self.model.idempotency_key == idempotency_key)
        ).first()


class LeaseExitItemRepository:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def list_for_settlement(self, settlement_id: int) -> list[LeaseExitItem]:
        visible = LeaseExitSettlementRepository(self.session, self.ctx).get(settlement_id)
        if visible is None:
            return []
        return list(
            self.session.scalars(
                select(LeaseExitItem)
                .where(
                    LeaseExitItem.tenant_id == self.ctx.tenant_id,
                    LeaseExitItem.settlement_id == int(settlement_id),
                )
                .order_by(LeaseExitItem.sort_order, LeaseExitItem.id)
            ).all()
        )

    def replace_for_settlement(
        self, settlement_id: int, models: Iterable[LeaseExitItem]
    ) -> None:
        if LeaseExitSettlementRepository(self.session, self.ctx).get(settlement_id) is None:
            raise AppError("退租结算不存在", code="LEASE_EXIT_NOT_FOUND", status_code=404)
        self.session.execute(
            delete(LeaseExitItem).where(
                LeaseExitItem.tenant_id == self.ctx.tenant_id,
                LeaseExitItem.settlement_id == int(settlement_id),
            )
        )
        for model in models:
            model.tenant_id = self.ctx.tenant_id
            model.settlement_id = int(settlement_id)
            self.session.add(model)
        self.session.flush()


def lock_current_units(session: Session, unit_ids: Iterable[int]) -> list[Any]:
    """Lock current Unit versions in ascending id order to avoid deadlocks."""

    from app.infrastructure.database.models.park_property import Unit

    ordered = sorted({int(unit_id) for unit_id in unit_ids})
    if not ordered:
        return []
    return list(
        session.scalars(
            select(Unit)
            .where(Unit.id.in_(ordered), Unit.valid_to.is_(None), Unit.is_deleted.is_(False))
            .order_by(Unit.id)
            .with_for_update()
        ).all()
    )

"""功能说明：
    Lease 应用服务：合同生命周期与占用编排。

业务职责：
    Application 层；tenant/park 权限、审计、事务；不直写 SQL。
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.business_logging import log_business_success
from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.modules.lease.application.occupancy_service import OccupancyService
from app.modules.lease.domain.entities import (
    LeaseContractEntity,
    LeaseContractUnitEntity,
    LeaseTermEntity,
)
from app.modules.lease.domain.rules import (
    assert_positive_area,
    assert_status_transition,
    assert_term_type,
    is_editable_status,
)
from app.modules.lease.infrastructure.lease_repository import (
    LeaseContractRepository,
    LeaseContractUnitRepository,
    LeaseTermRepository,
)
from app.modules.lease.infrastructure.mappers import (
    LeaseContractMapper,
    LeaseContractUnitMapper,
    LeaseTermMapper,
)
from app.modules.investment.infrastructure.crm_repository import LeadUnitLockRepository
from app.modules.park_property.infrastructure.park_repository import ParkRepository
from app.modules.park_property.infrastructure.unit_repository import UnitRepository
from app.modules.party.infrastructure.party_repository import PartyRepository
from app.modules.workbench.application.work_item_service import WorkItemService
from app.shared.tenant_context import TenantContext

logger = logging.getLogger(__name__)

LEASE_EXPIRING_ITEM_TYPE = "CONTRACT_EXPIRING"


class LeaseService:
    """功能说明：
        编排租赁合同创建/提交/激活/终止等用例。

    业务职责：
        应用层；协调仓储、占用投影、Party/Park/Unit 校验。
    """

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.contracts = LeaseContractRepository(session, ctx)
        self.units_lines = LeaseContractUnitRepository(session, ctx)
        self.terms = LeaseTermRepository(session, ctx)
        self.parks = ParkRepository(session, ctx)
        self.units = UnitRepository(session, ctx)
        self.parties = PartyRepository(session, ctx)
        self.occupancy = OccupancyService(session, ctx)
        self.lead_unit_locks = LeadUnitLockRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)
        self.work_items = WorkItemService(session, ctx)

    def _open_expiring_todo(self, model) -> None:
        """激活后幂等打开合同到期待办（不侵入合同状态机）。"""

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

    def _close_expiring_todo(self, contract_id: int) -> None:
        self.work_items.cancel_by_source(
            source_type="LEASE",
            source_id=str(contract_id),
            item_type=LEASE_EXPIRING_ITEM_TYPE,
            commit=False,
        )

    def _require_contract(self, contract_id: int):
        model = self.contracts.get_by_id(contract_id)
        if model is None:
            raise AppError("合同不存在", code="LEASE_NOT_FOUND", status_code=404)
        return model

    def _assert_park_scope(self, park_id: int) -> None:
        if not self.parks.exists_in_tenant(park_id):
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        if not self.ctx.allows_park(park_id):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)

    def _assert_write(self) -> None:
        if not self.ctx.has_permission("lease:write"):
            raise AppError("无合同写权限", code="PERMISSION_DENIED", status_code=403)

    def _assert_activate(self) -> None:
        if not self.ctx.has_permission("lease:activate"):
            raise AppError("无合同激活权限", code="PERMISSION_DENIED", status_code=403)

    def _assert_terminate(self) -> None:
        if not self.ctx.has_permission("lease:terminate"):
            raise AppError("无合同终止权限", code="PERMISSION_DENIED", status_code=403)

    def _parse_date(self, value: Any, field: str) -> date:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            return date.fromisoformat(value[:10])
        raise AppError(f"{field} 无效", code="VALIDATION_ERROR", status_code=400)

    def _to_dict(self, model, *, with_children: bool = False) -> dict[str, Any]:
        e = LeaseContractMapper.to_entity(model)
        data: dict[str, Any] = {
            "id": e.id,
            "tenant_id": e.tenant_id,
            "park_id": e.park_id,
            "party_id": e.party_id,
            "contract_no": e.contract_no,
            "status": e.status,
            "start_date": e.start_date.isoformat() if e.start_date else None,
            "end_date": e.end_date.isoformat() if e.end_date else None,
            "deposit_amount": str(e.deposit_amount),
            "increase_date": e.increase_date.isoformat() if e.increase_date else None,
            "increase_rate": str(e.increase_rate) if e.increase_rate is not None else None,
            "remark": e.remark,
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "updated_at": e.updated_at.isoformat() if e.updated_at else None,
        }
        if with_children:
            data["units"] = [
                {
                    "id": u.id,
                    "unit_id": u.unit_id,
                    "occupied_area": str(u.occupied_area),
                    "unit_rent_price": str(u.unit_rent_price),
                }
                for u in self.units_lines.list_for_contract(int(model.id))
            ]
            data["terms"] = [
                {
                    "id": t.id,
                    "term_type": t.term_type,
                    "effective_date": t.effective_date.isoformat() if t.effective_date else None,
                    "end_date": t.end_date.isoformat() if t.end_date else None,
                    "rate": str(t.rate) if t.rate is not None else None,
                    "amount": str(t.amount) if t.amount is not None else None,
                    "description": t.description,
                    "sort_order": t.sort_order,
                }
                for t in self.terms.list_for_contract(int(model.id))
            ]
        return data

    def _replace_units(self, contract_id: int, park_id: int, units: list[dict[str, Any]]) -> None:
        self.units_lines.delete_for_contract(contract_id)
        seen: set[int] = set()
        for raw in units or []:
            unit_id = int(raw["unit_id"])
            if unit_id in seen:
                raise AppError("合同内单元重复", code="VALIDATION_ERROR", status_code=400)
            seen.add(unit_id)
            unit = self.units.get_current_by_id(unit_id)
            if unit is None:
                raise AppError("单元不存在", code="UNIT_NOT_FOUND", status_code=404)
            if int(unit.park_id) != int(park_id):
                raise AppError(
                    "单元不属于合同园区",
                    code="UNIT_PARK_MISMATCH",
                    status_code=400,
                )
            try:
                area = assert_positive_area(raw.get("occupied_area") or 0)
                price = Decimal(str(raw.get("unit_rent_price") or 0))
            except ValueError as exc:
                raise AppError(str(exc), code="VALIDATION_ERROR", status_code=400) from exc
            self.units_lines.add(
                LeaseContractUnitMapper.new_model(
                    LeaseContractUnitEntity(
                        tenant_id=self.ctx.tenant_id,
                        contract_id=contract_id,
                        unit_id=unit_id,
                        occupied_area=area,
                        unit_rent_price=price,
                    )
                )
            )

    def _replace_terms(self, contract_id: int, terms: list[dict[str, Any]]) -> None:
        self.terms.delete_for_contract(contract_id)
        for i, raw in enumerate(terms or []):
            try:
                tt = assert_term_type(str(raw.get("term_type") or "OTHER"))
            except ValueError as exc:
                raise AppError(str(exc), code="VALIDATION_ERROR", status_code=400) from exc
            eff = raw.get("effective_date")
            end = raw.get("end_date")
            self.terms.add(
                LeaseTermMapper.new_model(
                    LeaseTermEntity(
                        tenant_id=self.ctx.tenant_id,
                        contract_id=contract_id,
                        term_type=tt,
                        effective_date=self._parse_date(eff, "effective_date") if eff else None,
                        end_date=self._parse_date(end, "end_date") if end else None,
                        rate=Decimal(str(raw["rate"])) if raw.get("rate") is not None else None,
                        amount=Decimal(str(raw["amount"])) if raw.get("amount") is not None else None,
                        description=raw.get("description"),
                        sort_order=int(raw.get("sort_order") or i),
                    )
                )
            )

    def list_contracts(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        party_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """功能说明：
            分页列出可见合同。

        业务职责：
            应用层查询；需 lease:read（路由保证）。

        业务规则：
            tenant + park scope 由仓储施加。
        """

        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        offset = (page - 1) * page_size
        items = self.contracts.list(
            offset=offset,
            limit=page_size,
            status=status,
            park_id=park_id,
            party_id=party_id,
        )
        total = self.contracts.count(status=status, park_id=park_id, party_id=party_id)
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [self._to_dict(c) for c in items],
        }

    def get_contract(self, contract_id: int) -> dict[str, Any]:
        """功能说明：获取合同详情（含 units/terms）。"""

        model = self._require_contract(contract_id)
        return self._to_dict(model, with_children=True)

    def create_contract(self, data: dict[str, Any], *, commit: bool = True) -> dict[str, Any]:
        """功能说明：
            创建 DRAFT 合同及可选占用/条款。

        业务职责：
            应用层创建；校验 party/park/scope。

        业务规则：
            1. 需 lease:write。
            2. contract_no 可省略则自动生成。
            3. deposit_amount 仅存储。
        """

        self._assert_write()
        park_id = int(data["park_id"])
        party_id = int(data["party_id"])
        self._assert_park_scope(park_id)
        party = self.parties.get_by_id(party_id)
        if party is None:
            raise AppError("主体不存在", code="PARTY_NOT_FOUND", status_code=404)
        if party.status == "ARCHIVED":
            raise AppError("已归档主体不可签约", code="PARTY_STATUS_INVALID", status_code=400)
        if party.risk_status == "BLACKLISTED":
            raise AppError("黑名单主体不可签约", code="PARTY_RISK_INVALID", status_code=400)

        start = self._parse_date(data.get("start_date"), "start_date")
        end = self._parse_date(data.get("end_date"), "end_date")
        if end < start:
            raise AppError("end_date 不得早于 start_date", code="VALIDATION_ERROR", status_code=400)

        from app.infrastructure.platform.number_sequence import next_number

        contract_no = (data.get("contract_no") or "").strip()
        if not contract_no:
            seq = next_number(
                self.session,
                tenant_id=self.ctx.tenant_id,
                biz_type="CONTRACT",
                period_key=start.strftime("%Y%m%d"),
            )
            contract_no = f"LC{start.strftime('%Y%m%d')}{seq:04d}"
        if self.contracts.find_by_contract_no(contract_no):
            raise AppError("合同号重复", code="LEASE_NO_DUPLICATE", status_code=409)

        deposit = Decimal(str(data.get("deposit_amount") or 0))
        if deposit < 0:
            raise AppError("deposit_amount 不得为负", code="VALIDATION_ERROR", status_code=400)

        entity = LeaseContractEntity(
            tenant_id=self.ctx.tenant_id,
            park_id=park_id,
            party_id=party_id,
            contract_no=contract_no,
            start_date=start,
            end_date=end,
            status="DRAFT",
            deposit_amount=deposit,
            remark=data.get("remark"),
            created_by=self.ctx.user_id,
        )
        model = LeaseContractMapper.new_model(entity)
        try:
            self.contracts.add(model)
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError("合同号重复", code="LEASE_NO_DUPLICATE", status_code=409) from exc

        self._replace_units(int(model.id), park_id, data.get("units") or [])
        self._replace_terms(int(model.id), data.get("terms") or [])

        self.audit.record(
            action="create",
            resource_type="LEASE_CONTRACT",
            resource_id=model.id,
            park_id=park_id,
            detail={"contract_no": contract_no, "party_id": party_id},
        )
        if commit:
            self.session.commit()
            self.session.refresh(model)
            log_business_success(
                logger,
                "创建合同成功",
                ctx=self.ctx,
                module="lease",
                action="create",
                resource_id=model.id,
                park_id=park_id,
            )
        else:
            self.session.flush()
        return self.get_contract(int(model.id))

    def update_contract(self, contract_id: int, data: dict[str, Any]) -> dict[str, Any]:
        """功能说明：更新可编辑状态合同。"""

        self._assert_write()
        model = self._require_contract(contract_id)
        if not is_editable_status(model.status):
            raise AppError("当前状态不可编辑", code="LEASE_STATUS_INVALID", status_code=400)
        entity = LeaseContractMapper.to_entity(model)
        if "start_date" in data and data["start_date"] is not None:
            entity.start_date = self._parse_date(data["start_date"], "start_date")
        if "end_date" in data and data["end_date"] is not None:
            entity.end_date = self._parse_date(data["end_date"], "end_date")
        if entity.end_date < entity.start_date:
            raise AppError("end_date 不得早于 start_date", code="VALIDATION_ERROR", status_code=400)
        if "remark" in data:
            entity.remark = data["remark"]
        if "deposit_amount" in data and data["deposit_amount"] is not None:
            dep = Decimal(str(data["deposit_amount"]))
            if dep < 0:
                raise AppError("deposit_amount 不得为负", code="VALIDATION_ERROR", status_code=400)
            entity.deposit_amount = dep
        LeaseContractMapper.apply_entity(model, entity)
        self.contracts.save(model)
        if "units" in data:
            self._replace_units(int(model.id), int(model.park_id), data.get("units") or [])
        if "terms" in data:
            self._replace_terms(int(model.id), data.get("terms") or [])
        self.audit.record(
            action="update",
            resource_type="LEASE_CONTRACT",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"fields": sorted(data.keys())},
        )
        self.session.commit()
        return self.get_contract(int(model.id))

    def submit(self, contract_id: int) -> dict[str, Any]:
        """功能说明：DRAFT → PENDING_ACTIVE。"""

        self._assert_activate()
        model = self._require_contract(contract_id)
        try:
            model.status = assert_status_transition(model.status, "PENDING_ACTIVE")
        except ValueError as exc:
            raise AppError(str(exc), code="LEASE_STATUS_INVALID", status_code=400) from exc
        if not self.units_lines.list_for_contract(contract_id):
            raise AppError("激活前须配置占用单元", code="LEASE_UNITS_REQUIRED", status_code=400)
        self.contracts.save(model)
        self.audit.record(
            action="submit",
            resource_type="LEASE_CONTRACT",
            resource_id=model.id,
            park_id=model.park_id,
            detail={},
        )
        self.session.commit()
        return self.get_contract(contract_id)

    def reject(self, contract_id: int) -> dict[str, Any]:
        """功能说明：PENDING_ACTIVE → DRAFT。"""

        self._assert_activate()
        model = self._require_contract(contract_id)
        try:
            model.status = assert_status_transition(model.status, "DRAFT")
        except ValueError as exc:
            raise AppError(str(exc), code="LEASE_STATUS_INVALID", status_code=400) from exc
        self.contracts.save(model)
        self.audit.record(
            action="reject",
            resource_type="LEASE_CONTRACT",
            resource_id=model.id,
            park_id=model.park_id,
            detail={},
        )
        self.session.commit()
        return self.get_contract(contract_id)

    def cancel(self, contract_id: int) -> dict[str, Any]:
        """功能说明：DRAFT/PENDING_ACTIVE → CANCELLED。"""

        self._assert_write()
        model = self._require_contract(contract_id)
        try:
            model.status = assert_status_transition(model.status, "CANCELLED")
        except ValueError as exc:
            raise AppError(str(exc), code="LEASE_STATUS_INVALID", status_code=400) from exc
        self.contracts.save(model)
        self.audit.record(
            action="cancel",
            resource_type="LEASE_CONTRACT",
            resource_id=model.id,
            park_id=model.park_id,
            detail={},
        )
        self.session.commit()
        return self.get_contract(contract_id)

    def activate(self, contract_id: int) -> dict[str, Any]:
        """功能说明：
            PENDING_ACTIVE → ACTIVE；校验占用并投影 used_area。

        业务规则：
            1. 需 lease:activate。
            2. Party 不可 ARCHIVED/BLACKLISTED。
            3. 无押金退还/出账副作用。
        """

        self._assert_activate()
        model = self._require_contract(contract_id)
        try:
            assert_status_transition(model.status, "ACTIVE")
        except ValueError as exc:
            raise AppError(str(exc), code="LEASE_STATUS_INVALID", status_code=400) from exc

        party = self.parties.get_by_id(int(model.party_id))
        if party is None:
            raise AppError("主体不存在", code="PARTY_NOT_FOUND", status_code=404)
        if party.status == "ARCHIVED" or party.risk_status == "BLACKLISTED":
            raise AppError("主体不可激活合同", code="PARTY_STATUS_INVALID", status_code=400)

        lines = self.units_lines.list_for_contract(contract_id)
        if not lines:
            raise AppError("激活前须配置占用单元", code="LEASE_UNITS_REQUIRED", status_code=400)

        unit_area: list[tuple[Any, Decimal]] = []
        consumed_locks: list[Any] = []
        now = utc_now()
        for line in lines:
            # Serialize activation with structural version/split/merge writes.
            # A pending lease may only activate against the current unit version.
            unit = self.units.get_current_for_update(int(line.unit_id))
            if unit is None:
                raise AppError("单元不存在", code="UNIT_NOT_FOUND", status_code=404)
            if int(unit.park_id) != int(model.park_id):
                raise AppError("单元不属于合同园区", code="UNIT_PARK_MISMATCH", status_code=400)
            active_lock = self.lead_unit_locks.active_for_unit(int(unit.id), for_update=True)
            if active_lock is not None and active_lock.expires_at <= now:
                active_lock.status = "EXPIRED"
                active_lock.released_at = now
                active_lock.lock_version += 1
                self.session.add(active_lock)
                active_lock = None
            if active_lock is not None:
                if int(active_lock.lease_id or 0) != int(model.id):
                    raise AppError(
                        "单元存在不属于当前合同的有效招商锁",
                        code="UNIT_ALREADY_LOCKED",
                        status_code=409,
                    )
                consumed_locks.append(active_lock)
            unit_area.append((unit, Decimal(str(line.occupied_area or 0))))

        self.occupancy.assert_can_activate_lines(contract_id=contract_id, lines=unit_area)

        model.status = "ACTIVE"
        self.contracts.save(model)
        for unit, _ in unit_area:
            self.occupancy.recompute_unit_used_area(unit)
        for lock in consumed_locks:
            lock.status = "CONSUMED"
            lock.consumed_at = now
            lock.lock_version += 1
            self.session.add(lock)
        self._open_expiring_todo(model)

        self.audit.record(
            action="activate",
            resource_type="LEASE_CONTRACT",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"units": len(lines)},
        )
        self.session.commit()
        log_business_success(
            logger,
            "激活合同成功",
            ctx=self.ctx,
            module="lease",
            action="activate",
            resource_id=model.id,
            park_id=model.park_id,
        )
        return self.get_contract(contract_id)

    def terminate(self, contract_id: int, *, breached: bool = False) -> dict[str, Any]:
        """功能说明：
            ACTIVE/EXPIRING → TERMINATED 或 BREACHED；释放占用投影。

        业务规则：
            不实现押金退还流水。
        """

        self._assert_terminate()
        model = self._require_contract(contract_id)
        target = "BREACHED" if breached else "TERMINATED"
        try:
            model.status = assert_status_transition(model.status, target)
        except ValueError as exc:
            raise AppError(str(exc), code="LEASE_STATUS_INVALID", status_code=400) from exc

        unit_ids = {int(u.unit_id) for u in self.units_lines.list_for_contract(contract_id)}
        self.contracts.save(model)
        for uid in unit_ids:
            unit = self.units.get_by_id(uid)
            if unit is not None:
                self.occupancy.recompute_unit_used_area(unit)
        self._close_expiring_todo(contract_id)

        self.audit.record(
            action="breach" if breached else "terminate",
            resource_type="LEASE_CONTRACT",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"status": target},
        )
        self.session.commit()
        return self.get_contract(contract_id)

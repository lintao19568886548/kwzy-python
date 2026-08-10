"""功能说明：
    单元占用与 used_area 投影服务。

业务职责：
    Application；activate/terminate 后重算投影，禁止客户端直写 used_area。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.lease.domain.rules import UNIT_RENTABLE_STATUSES, assert_capacity
from app.modules.lease.infrastructure.lease_repository import LeaseContractUnitRepository
from app.modules.park_property.domain.states import transition_unit_status
from app.shared.tenant_context import TenantContext


class OccupancyService:
    """功能说明：
        占用冲突检测与 used_area 投影。

    业务职责：
        应用层领域服务编排。
    """

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.units_lines = LeaseContractUnitRepository(session, ctx)

    def recompute_unit_used_area(self, unit: Any) -> Any:
        """功能说明：
            按有效合同占用重算 unit.used_area 并调整状态。

        业务职责：
            投影写回；不接受客户端 used_area。

        输入参数：
            unit：Unit ORM。

        返回结果：
            更新后的 unit。

        异常说明：
            无。

        业务规则：
            1. used_area = ACTIVE/EXPIRING 合同占用之和。
            2. used_area>0 → OCCUPIED（若当前可迁）；=0 且 OCCUPIED → VACANT。
        """

        used = self.units_lines.sum_active_occupied_for_unit(int(unit.id))
        unit.used_area = used
        if used > 0:
            if unit.status in {"VACANT", "RESERVED", "OCCUPIED"}:
                try:
                    unit.status = transition_unit_status(unit.status, "OCCUPIED")
                except ValueError:
                    unit.status = "OCCUPIED"
        else:
            if unit.status == "OCCUPIED":
                try:
                    unit.status = transition_unit_status(unit.status, "VACANT")
                except ValueError:
                    unit.status = "VACANT"
        self.session.add(unit)
        self.session.flush()
        return unit

    def assert_can_activate_lines(
        self,
        *,
        contract_id: int,
        lines: list[tuple[Any, Decimal]],
    ) -> None:
        """功能说明：
            激活前校验单元可租与容量。

        业务职责：
            冲突预检。

        输入参数：
            contract_id：当前合同（排除自身占用）。
            lines：(Unit, occupied_area) 列表。

        返回结果：
            None。

        异常说明：
            AppError(UNIT_NOT_RENTABLE / OCCUPANCY_CONFLICT)。

        业务规则：
            单元状态须可租；面积不超 rentable。
        """

        for unit, area in lines:
            if unit.is_deleted:
                raise AppError("单元已删除", code="UNIT_NOT_FOUND", status_code=404)
            if unit.status not in UNIT_RENTABLE_STATUSES and unit.status != "OCCUPIED":
                raise AppError(
                    f"单元状态不可占用: {unit.status}",
                    code="UNIT_NOT_RENTABLE",
                    status_code=409,
                )
            if unit.status in {"RETIRED", "DRAFT", "MAINTENANCE"}:
                raise AppError(
                    f"单元状态不可占用: {unit.status}",
                    code="UNIT_NOT_RENTABLE",
                    status_code=409,
                )
            current = self.units_lines.sum_active_occupied_for_unit(
                int(unit.id), exclude_contract_id=contract_id
            )
            try:
                assert_capacity(unit.rentable_area, current, area)
            except ValueError as exc:
                raise AppError(
                    str(exc),
                    code="OCCUPANCY_CONFLICT",
                    status_code=409,
                ) from exc

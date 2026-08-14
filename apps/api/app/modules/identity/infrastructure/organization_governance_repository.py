"""平台组织治理仓储；集中执行 tenant 与 park scope 过滤。"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.identity import Role, User, UserRole
from app.infrastructure.database.models.organization_governance import (
    FieldAccessPolicy,
    OrganizationGroup,
    OrganizationRegion,
    Position,
    RegionParkAssignment,
    UserPositionAssignment,
)
from app.infrastructure.database.models.park_property import Park
from app.infrastructure.database.models.system_config import OrgUnit
from app.shared.tenant_context import ParkScopeMode, TenantContext


class OrganizationGovernanceRepository:
    """集团、区域、岗位、任职和字段策略持久化。"""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def _locked(self, stmt, *, for_update: bool):
        if (
            for_update
            and self.session.bind is not None
            and self.session.bind.dialect.name == "postgresql"
        ):
            return stmt.with_for_update()
        return stmt

    def _park_scope(self, stmt, column):
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(column.in_(list(self.ctx.park_ids)))
        return stmt.where(False)

    def add(self, model):
        """写入并 flush，让数据库约束在业务事务内尽早生效。"""

        self.session.add(model)
        self.session.flush()
        return model

    def new_group(self, **values) -> OrganizationGroup:
        """在基础设施边界内构造集团持久化模型。"""

        return OrganizationGroup(**values)

    def new_region(self, **values) -> OrganizationRegion:
        """在基础设施边界内构造区域持久化模型。"""

        return OrganizationRegion(**values)

    def new_park_assignment(self, **values) -> RegionParkAssignment:
        """在基础设施边界内构造园区归属持久化模型。"""

        return RegionParkAssignment(**values)

    def new_position(self, **values) -> Position:
        """在基础设施边界内构造岗位持久化模型。"""

        return Position(**values)

    def new_user_assignment(self, **values) -> UserPositionAssignment:
        """在基础设施边界内构造任职持久化模型。"""

        return UserPositionAssignment(**values)

    def new_field_policy(self, **values) -> FieldAccessPolicy:
        """在基础设施边界内构造字段策略持久化模型。"""

        return FieldAccessPolicy(**values)

    # Groups and regions
    def list_groups(self) -> Sequence[OrganizationGroup]:
        return list(
            self.session.scalars(
                select(OrganizationGroup)
                .where(OrganizationGroup.tenant_id == self.ctx.tenant_id)
                .order_by(OrganizationGroup.sort_order, OrganizationGroup.id)
            ).all()
        )

    def get_group(
        self, group_id: int, *, for_update: bool = False
    ) -> OrganizationGroup | None:
        stmt = select(OrganizationGroup).where(
            OrganizationGroup.tenant_id == self.ctx.tenant_id,
            OrganizationGroup.id == group_id,
        )
        return self.session.scalars(self._locked(stmt, for_update=for_update)).first()

    def find_group_by_code(self, code: str) -> OrganizationGroup | None:
        return self.session.scalars(
            select(OrganizationGroup).where(
                OrganizationGroup.tenant_id == self.ctx.tenant_id,
                OrganizationGroup.code == code,
            )
        ).first()

    def active_region_count(self, group_id: int) -> int:
        return int(
            self.session.scalar(
                select(func.count(OrganizationRegion.id)).where(
                    OrganizationRegion.tenant_id == self.ctx.tenant_id,
                    OrganizationRegion.group_id == group_id,
                    OrganizationRegion.status == "ACTIVE",
                )
            )
            or 0
        )

    def list_regions(self, *, group_id: int | None = None) -> Sequence[OrganizationRegion]:
        stmt = select(OrganizationRegion).where(
            OrganizationRegion.tenant_id == self.ctx.tenant_id
        )
        if group_id is not None:
            stmt = stmt.where(OrganizationRegion.group_id == group_id)
        return list(
            self.session.scalars(
                stmt.order_by(
                    OrganizationRegion.group_id,
                    OrganizationRegion.sort_order,
                    OrganizationRegion.id,
                )
            ).all()
        )

    def get_region(
        self, region_id: int, *, for_update: bool = False
    ) -> OrganizationRegion | None:
        stmt = select(OrganizationRegion).where(
            OrganizationRegion.tenant_id == self.ctx.tenant_id,
            OrganizationRegion.id == region_id,
        )
        return self.session.scalars(self._locked(stmt, for_update=for_update)).first()

    def find_region_by_code(self, code: str) -> OrganizationRegion | None:
        return self.session.scalars(
            select(OrganizationRegion).where(
                OrganizationRegion.tenant_id == self.ctx.tenant_id,
                OrganizationRegion.code == code,
            )
        ).first()

    def current_park_count(self, region_id: int) -> int:
        return int(
            self.session.scalar(
                select(func.count(RegionParkAssignment.id)).where(
                    RegionParkAssignment.tenant_id == self.ctx.tenant_id,
                    RegionParkAssignment.region_id == region_id,
                    RegionParkAssignment.effective_to.is_(None),
                )
            )
            or 0
        )

    def get_park(self, park_id: int, *, for_update: bool = False) -> Park | None:
        stmt = select(Park).where(
            Park.tenant_id == self.ctx.tenant_id,
            Park.id == park_id,
            Park.is_deleted.is_(False),
        )
        return self.session.scalars(self._locked(stmt, for_update=for_update)).first()

    def get_current_park_assignment(
        self, park_id: int, *, for_update: bool = False
    ) -> RegionParkAssignment | None:
        stmt = select(RegionParkAssignment).where(
            RegionParkAssignment.tenant_id == self.ctx.tenant_id,
            RegionParkAssignment.park_id == park_id,
            RegionParkAssignment.effective_to.is_(None),
        )
        return self.session.scalars(self._locked(stmt, for_update=for_update)).first()

    def list_current_park_assignments(self) -> Sequence[RegionParkAssignment]:
        stmt = select(RegionParkAssignment).where(
            RegionParkAssignment.tenant_id == self.ctx.tenant_id,
            RegionParkAssignment.effective_to.is_(None),
        )
        stmt = self._park_scope(stmt, RegionParkAssignment.park_id)
        return list(
            self.session.scalars(
                stmt.order_by(RegionParkAssignment.region_id, RegionParkAssignment.park_id)
            ).all()
        )

    def list_park_assignment_history(self, park_id: int) -> Sequence[RegionParkAssignment]:
        stmt = select(RegionParkAssignment).where(
            RegionParkAssignment.tenant_id == self.ctx.tenant_id,
            RegionParkAssignment.park_id == park_id,
        )
        stmt = self._park_scope(stmt, RegionParkAssignment.park_id)
        return list(
            self.session.scalars(
                stmt.order_by(RegionParkAssignment.effective_from, RegionParkAssignment.id)
            ).all()
        )

    # Position and assignment
    def get_org_unit(self, org_unit_id: int) -> OrgUnit | None:
        return self.session.scalars(
            select(OrgUnit).where(
                OrgUnit.tenant_id == self.ctx.tenant_id,
                OrgUnit.id == org_unit_id,
            )
        ).first()

    def list_positions(self) -> Sequence[Position]:
        return list(
            self.session.scalars(
                select(Position)
                .where(Position.tenant_id == self.ctx.tenant_id)
                .order_by(Position.sort_order, Position.id)
            ).all()
        )

    def get_position(
        self, position_id: int, *, for_update: bool = False
    ) -> Position | None:
        stmt = select(Position).where(
            Position.tenant_id == self.ctx.tenant_id,
            Position.id == position_id,
        )
        return self.session.scalars(self._locked(stmt, for_update=for_update)).first()

    def find_position_by_code(self, code: str) -> Position | None:
        return self.session.scalars(
            select(Position).where(
                Position.tenant_id == self.ctx.tenant_id,
                Position.code == code,
            )
        ).first()

    def get_user(self, user_id: int) -> User | None:
        return self.session.scalars(
            select(User).where(
                User.tenant_id == self.ctx.tenant_id,
                User.id == user_id,
            )
        ).first()

    def active_assignment_count(self, position_id: int) -> int:
        return int(
            self.session.scalar(
                select(func.count(UserPositionAssignment.id)).where(
                    UserPositionAssignment.tenant_id == self.ctx.tenant_id,
                    UserPositionAssignment.position_id == position_id,
                    UserPositionAssignment.ends_at.is_(None),
                )
            )
            or 0
        )

    def list_user_assignments(
        self,
        *,
        user_id: int | None = None,
        current_only: bool = False,
    ) -> Sequence[UserPositionAssignment]:
        stmt = select(UserPositionAssignment).where(
            UserPositionAssignment.tenant_id == self.ctx.tenant_id
        )
        if user_id is not None:
            stmt = stmt.where(UserPositionAssignment.user_id == user_id)
        if current_only:
            stmt = stmt.where(UserPositionAssignment.ends_at.is_(None))
        if self.ctx.park_scope_mode != ParkScopeMode.ALL:
            if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
                stmt = stmt.where(
                    or_(
                        UserPositionAssignment.park_id.is_(None),
                        UserPositionAssignment.park_id.in_(list(self.ctx.park_ids)),
                    )
                )
            else:
                stmt = stmt.where(UserPositionAssignment.park_id.is_(None))
        return list(
            self.session.scalars(
                stmt.order_by(UserPositionAssignment.starts_at.desc(), UserPositionAssignment.id)
            ).all()
        )

    def get_user_assignment(
        self, assignment_id: int, *, for_update: bool = False
    ) -> UserPositionAssignment | None:
        stmt = select(UserPositionAssignment).where(
            UserPositionAssignment.tenant_id == self.ctx.tenant_id,
            UserPositionAssignment.id == assignment_id,
        )
        if self.ctx.park_scope_mode != ParkScopeMode.ALL:
            if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
                stmt = stmt.where(
                    or_(
                        UserPositionAssignment.park_id.is_(None),
                        UserPositionAssignment.park_id.in_(list(self.ctx.park_ids)),
                    )
                )
            else:
                stmt = stmt.where(UserPositionAssignment.park_id.is_(None))
        return self.session.scalars(self._locked(stmt, for_update=for_update)).first()

    def get_current_primary_assignment(
        self, user_id: int, *, for_update: bool = False
    ) -> UserPositionAssignment | None:
        stmt = select(UserPositionAssignment).where(
            UserPositionAssignment.tenant_id == self.ctx.tenant_id,
            UserPositionAssignment.user_id == user_id,
            UserPositionAssignment.ends_at.is_(None),
            UserPositionAssignment.is_primary.is_(True),
        )
        return self.session.scalars(self._locked(stmt, for_update=for_update)).first()

    def get_current_duplicate_assignment(
        self,
        *,
        user_id: int,
        position_id: int,
        scope_key: str,
    ) -> UserPositionAssignment | None:
        return self.session.scalars(
            select(UserPositionAssignment).where(
                UserPositionAssignment.tenant_id == self.ctx.tenant_id,
                UserPositionAssignment.user_id == user_id,
                UserPositionAssignment.position_id == position_id,
                UserPositionAssignment.scope_key == scope_key,
                UserPositionAssignment.ends_at.is_(None),
            )
        ).first()

    # Field policies
    def get_role(self, role_id: int) -> Role | None:
        return self.session.scalars(
            select(Role).where(Role.tenant_id == self.ctx.tenant_id, Role.id == role_id)
        ).first()

    def list_field_policies(self) -> Sequence[FieldAccessPolicy]:
        return list(
            self.session.scalars(
                select(FieldAccessPolicy)
                .where(FieldAccessPolicy.tenant_id == self.ctx.tenant_id)
                .order_by(
                    FieldAccessPolicy.resource_type,
                    FieldAccessPolicy.field_name,
                    FieldAccessPolicy.role_id,
                )
            ).all()
        )

    def find_field_policy(
        self, *, role_id: int, resource_type: str, field_name: str
    ) -> FieldAccessPolicy | None:
        return self.session.scalars(
            select(FieldAccessPolicy).where(
                FieldAccessPolicy.tenant_id == self.ctx.tenant_id,
                FieldAccessPolicy.role_id == role_id,
                FieldAccessPolicy.resource_type == resource_type,
                FieldAccessPolicy.field_name == field_name,
            )
        ).first()

    def active_field_modes_for_user(
        self, *, user_id: int, resource_type: str
    ) -> Sequence[tuple[str, str]]:
        stmt = (
            select(FieldAccessPolicy.field_name, FieldAccessPolicy.access_mode)
            .join(UserRole, UserRole.role_id == FieldAccessPolicy.role_id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                FieldAccessPolicy.tenant_id == self.ctx.tenant_id,
                FieldAccessPolicy.resource_type == resource_type,
                FieldAccessPolicy.status == "ACTIVE",
                UserRole.tenant_id == self.ctx.tenant_id,
                UserRole.user_id == user_id,
                Role.tenant_id == self.ctx.tenant_id,
                Role.status == "ACTIVE",
            )
        )
        return list(self.session.execute(stmt).all())

    def field_policy_count_for_role(self, role_id: int) -> int:
        return int(
            self.session.scalar(
                select(func.count(FieldAccessPolicy.id)).where(
                    FieldAccessPolicy.tenant_id == self.ctx.tenant_id,
                    FieldAccessPolicy.role_id == role_id,
                )
            )
            or 0
        )

    def current_authorization_snapshot(self, user_id: int) -> dict[str, list[int]]:
        """用于证明任职写入前后没有触碰角色/园区授权关系。"""

        role_ids = list(
            self.session.scalars(
                select(UserRole.role_id).where(
                    UserRole.tenant_id == self.ctx.tenant_id,
                    UserRole.user_id == user_id,
                )
            ).all()
        )
        from app.infrastructure.database.models.identity import UserParkScope

        park_ids = list(
            self.session.scalars(
                select(UserParkScope.park_id).where(
                    UserParkScope.tenant_id == self.ctx.tenant_id,
                    UserParkScope.user_id == user_id,
                )
            ).all()
        )
        return {"role_ids": sorted(map(int, role_ids)), "park_ids": sorted(map(int, park_ids))}

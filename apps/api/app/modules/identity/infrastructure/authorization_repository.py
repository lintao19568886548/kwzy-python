"""身份登录与授权关系查询。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.identity import (
    Permission,
    Role,
    RoleParkScope,
    RolePermission,
    Tenant,
    User,
    UserParkScope,
    UserRole,
)
from app.shared.tenant_context import ParkScopeMode


class AuthorizationRepository:
    """按租户读取用户、权限码和园区数据范围。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def find_login_candidates(
        self,
        *,
        username: str,
        tenant_code: str | None,
    ) -> list[User]:
        """查找有效租户中的同名有效用户。"""

        stmt = (
            select(User)
            .join(Tenant, Tenant.id == User.tenant_id)
            .where(
                User.username == username,
                User.status == "ACTIVE",
                Tenant.status == "ACTIVE",
            )
        )
        if tenant_code:
            stmt = stmt.where(Tenant.code == tenant_code)
        return list(self.session.scalars(stmt).all())

    def resolve_authorization(
        self, user: User
    ) -> tuple[list[str], list[int], ParkScopeMode]:
        """计算动作权限并集与园区范围（与 * 正交）。

        返回：
            permissions: 动作权限码列表（`*` 仅表示全部动作）
            park_ids: LIST 模式下的园区 id 并集；ALL/NONE 时为空列表
            park_scope_mode: NONE | LIST | ALL
        """

        permission_stmt = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user.id,
                UserRole.tenant_id == user.tenant_id,
                RolePermission.tenant_id == user.tenant_id,
                Role.tenant_id == user.tenant_id,
                Role.status == "ACTIVE",
            )
        )
        permissions = {str(code) for code in self.session.scalars(permission_stmt).all()}

        # 全园区：用户级 OR 任一有效角色 all_parks（强制同租户）
        grant_all = bool(getattr(user, "all_parks", False))
        if not grant_all:
            role_all_stmt = (
                select(Role.id)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(
                    UserRole.user_id == user.id,
                    UserRole.tenant_id == user.tenant_id,
                    Role.tenant_id == user.tenant_id,
                    Role.status == "ACTIVE",
                    Role.all_parks.is_(True),
                )
                .limit(1)
            )
            grant_all = self.session.scalars(role_all_stmt).first() is not None

        if grant_all:
            return sorted(permissions), [], ParkScopeMode.ALL

        direct_park_stmt = select(UserParkScope.park_id).where(
            UserParkScope.user_id == user.id,
            UserParkScope.tenant_id == user.tenant_id,
        )
        park_ids = {int(park_id) for park_id in self.session.scalars(direct_park_stmt).all()}

        role_park_stmt = (
            select(RoleParkScope.park_id)
            .join(Role, Role.id == RoleParkScope.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user.id,
                UserRole.tenant_id == user.tenant_id,
                RoleParkScope.tenant_id == user.tenant_id,
                Role.tenant_id == user.tenant_id,
                Role.status == "ACTIVE",
            )
        )
        park_ids.update(int(park_id) for park_id in self.session.scalars(role_park_stmt).all())

        if park_ids:
            return sorted(permissions), sorted(park_ids), ParkScopeMode.LIST
        return sorted(permissions), [], ParkScopeMode.NONE

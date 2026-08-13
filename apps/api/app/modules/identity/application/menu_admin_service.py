"""菜单管理与当前用户菜单。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.identity.infrastructure.authorization_repository import (
    AuthorizationRepository,
)
from app.modules.identity.infrastructure.identity_admin_repository import (
    IdentityAdminRepository,
)


class MenuAdminService:
    def __init__(self, session: Session) -> None:
        self.repo = IdentityAdminRepository(session)
        self.auth_repo = AuthorizationRepository(session)

    def list_menus(self, *, tenant_id: int) -> list[dict]:
        return [self._to_dict(m) for m in self.repo.list_menus(tenant_id)]

    def create_menu(
        self,
        *,
        tenant_id: int,
        name: str,
        path: str = "",
        parent_id: int | None = None,
        component: str | None = None,
        icon: str | None = None,
        sort_order: int = 0,
        menu_type: str = "MENU",
        permission_code: str | None = None,
    ) -> dict:
        if not name:
            raise AppError("菜单名称不能为空", code="MENU_INVALID", status_code=400)
        if parent_id is not None:
            parent = self.repo.get_menu(parent_id)
            if parent is None or parent.tenant_id != tenant_id:
                raise AppError("上级菜单无效", code="MENU_PARENT_INVALID", status_code=400)
        menu = self.repo.create_menu_entity(
            tenant_id=tenant_id,
            name=name,
            path=path or "",
            parent_id=parent_id,
            component=component,
            icon=icon,
            sort_order=sort_order,
            menu_type=menu_type,
            permission_code=permission_code,
        )
        self.repo.commit()
        self.repo.refresh(menu)
        return self._to_dict(menu)

    def menus_for_user(self, *, tenant_id: int, user_id: int) -> list[dict]:
        user = self.repo.get_user(user_id)
        if user is None or user.tenant_id != tenant_id:
            raise AppError("用户不存在", code="USER_NOT_FOUND", status_code=404)
        permissions, _, _ = self.auth_repo.resolve_authorization(user)
        if "*" in permissions:
            return self.list_menus(tenant_id=tenant_id)
        role_ids = self.repo.active_role_ids_for_user(tenant_id, user_id)
        rows = self.repo.menus_for_role_ids(tenant_id, role_ids)
        return [self._to_dict(m) for m in rows]

    def _to_dict(self, menu) -> dict:
        return {
            "id": menu.id,
            "tenant_id": menu.tenant_id,
            "parent_id": menu.parent_id,
            "name": menu.name,
            "path": menu.path,
            "component": menu.component,
            "icon": menu.icon,
            "sort_order": menu.sort_order,
            "menu_type": menu.menu_type,
            "status": menu.status,
            "permission_code": menu.permission_code,
        }

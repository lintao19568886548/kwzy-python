"""菜单管理与当前用户菜单。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.modules.identity.infrastructure.authorization_repository import (
    AuthorizationRepository,
)
from app.modules.identity.infrastructure.identity_admin_repository import (
    IdentityAdminRepository,
)
from app.shared.tenant_context import TenantContext


class MenuAdminService:
    def __init__(self, session: Session, ctx: TenantContext | None = None) -> None:
        self.repo = IdentityAdminRepository(session)
        self.auth_repo = AuthorizationRepository(session)
        self.audit = AuditRecorder(session, ctx) if ctx is not None else None

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
        self._validate_menu_values(
            tenant_id=tenant_id,
            parent_id=parent_id,
            menu_type=menu_type,
            status="ACTIVE",
            permission_code=permission_code,
        )
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
        if self.audit:
            self.audit.record(
                action="create",
                resource_type="IDENTITY_MENU",
                resource_id=menu.id,
                detail={"parent_id": parent_id, "menu_type": menu_type},
            )
        self.repo.commit()
        self.repo.refresh(menu)
        return self._to_dict(menu)

    def update_menu(self, *, tenant_id: int, menu_id: int, data: dict) -> dict:
        menu = self._tenant_menu(tenant_id, menu_id)
        parent_id = data.get("parent_id", menu.parent_id)
        menu_type = data.get("menu_type", menu.menu_type)
        status = data.get("status", menu.status)
        permission_code = data.get("permission_code", menu.permission_code)
        self._validate_menu_values(
            tenant_id=tenant_id,
            parent_id=parent_id,
            menu_type=menu_type,
            status=status,
            permission_code=permission_code,
            menu_id=menu_id,
        )
        allowed = {
            "name",
            "path",
            "parent_id",
            "component",
            "icon",
            "sort_order",
            "menu_type",
            "status",
            "permission_code",
            "remark",
        }
        changed_fields: list[str] = []
        for field, value in data.items():
            if field in allowed and getattr(menu, field) != value:
                setattr(menu, field, value)
                changed_fields.append(field)
        if self.audit:
            self.audit.record(
                action="update",
                resource_type="IDENTITY_MENU",
                resource_id=menu.id,
                detail={"fields": sorted(changed_fields)},
            )
        self.repo.commit()
        self.repo.refresh(menu)
        return self._to_dict(menu)

    def deactivate_menu(self, *, tenant_id: int, menu_id: int) -> dict:
        menu = self._tenant_menu(tenant_id, menu_id)
        affected: list[int] = []
        pending = [menu.id]
        rows = self.repo.list_menus(tenant_id)
        children: dict[int, list[int]] = {}
        for row in rows:
            if row.parent_id is not None:
                children.setdefault(int(row.parent_id), []).append(int(row.id))
        while pending:
            current = pending.pop()
            if current in affected:
                continue
            affected.append(current)
            pending.extend(children.get(current, []))
        for row in rows:
            if row.id in affected:
                row.status = "DISABLED"
        if self.audit:
            self.audit.record(
                action="deactivate",
                resource_type="IDENTITY_MENU",
                resource_id=menu.id,
                detail={"affected_menu_ids": sorted(affected)},
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
            return [
                self._to_dict(menu)
                for menu in self.repo.list_menus(tenant_id)
                if menu.status == "ACTIVE"
            ]
        role_ids = self.repo.active_role_ids_for_user(tenant_id, user_id)
        rows = self.repo.menus_for_role_ids(tenant_id, role_ids)
        return [self._to_dict(m) for m in rows]

    def _tenant_menu(self, tenant_id: int, menu_id: int):
        menu = self.repo.get_menu(menu_id)
        if menu is None or menu.tenant_id != tenant_id:
            raise AppError("菜单不存在", code="MENU_NOT_FOUND", status_code=404)
        return menu

    def _validate_menu_values(
        self,
        *,
        tenant_id: int,
        parent_id: int | None,
        menu_type: str,
        status: str,
        permission_code: str | None,
        menu_id: int | None = None,
    ) -> None:
        if menu_type not in {"DIR", "MENU", "BUTTON"}:
            raise AppError("非法菜单类型", code="MENU_INVALID_TYPE", status_code=400)
        if status not in {"ACTIVE", "DISABLED"}:
            raise AppError("非法菜单状态", code="MENU_INVALID_STATUS", status_code=400)
        if permission_code and self.repo.get_permission_by_code(permission_code) is None:
            raise AppError("权限码不存在", code="PERM_NOT_FOUND", status_code=400)
        if parent_id is None:
            return
        if menu_id is not None and parent_id == menu_id:
            raise AppError("菜单不能以自身为上级", code="MENU_PARENT_CYCLE", status_code=400)
        parent = self._tenant_menu(tenant_id, parent_id)
        visited: set[int] = set()
        while parent.parent_id is not None:
            if parent.id in visited:
                raise AppError("菜单层级存在环", code="MENU_PARENT_CYCLE", status_code=400)
            visited.add(parent.id)
            if menu_id is not None and parent.parent_id == menu_id:
                raise AppError("菜单层级存在环", code="MENU_PARENT_CYCLE", status_code=400)
            parent = self._tenant_menu(tenant_id, int(parent.parent_id))

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
            "remark": menu.remark,
        }

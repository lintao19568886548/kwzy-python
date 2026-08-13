"""角色与权限管理。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.identity.infrastructure.identity_admin_repository import (
    IdentityAdminRepository,
)


class RoleAdminService:
    def __init__(self, session: Session) -> None:
        self.repo = IdentityAdminRepository(session)

    def list_roles(self, *, tenant_id: int) -> list[dict]:
        return [self._to_dict(r) for r in self.repo.list_roles(tenant_id)]

    def create_role(
        self,
        *,
        tenant_id: int,
        code: str,
        name: str,
        remark: str | None = None,
        all_parks: bool = False,
        permission_codes: list[str] | None = None,
        park_ids: list[int] | None = None,
        menu_ids: list[int] | None = None,
    ) -> dict:
        code = code.strip()
        if not code or not name:
            raise AppError("角色编码与名称不能为空", code="ROLE_INVALID", status_code=400)
        if self.repo.find_role_id(tenant_id, code):
            raise AppError("角色编码已存在", code="ROLE_EXISTS", status_code=409)
        role = self.repo.create_role_entity(
            tenant_id=tenant_id,
            code=code,
            name=name,
            remark=remark,
            all_parks=all_parks,
        )
        try:
            self.repo.replace_role_permissions(tenant_id, role.id, permission_codes or [])
        except KeyError as exc:
            raise AppError(f"权限码不存在: {exc.args[0]}", code="PERM_NOT_FOUND", status_code=400) from exc
        self.repo.replace_role_parks(tenant_id, role.id, park_ids or [])
        self.repo.replace_role_menus(tenant_id, role.id, menu_ids or [])
        self.repo.commit()
        self.repo.refresh(role)
        return self._to_dict(role)

    def update_role(
        self,
        *,
        tenant_id: int,
        role_id: int,
        name: str | None = None,
        remark: str | None = None,
        status: str | None = None,
        all_parks: bool | None = None,
        permission_codes: list[str] | None = None,
        park_ids: list[int] | None = None,
        menu_ids: list[int] | None = None,
    ) -> dict:
        role = self.repo.get_role(role_id)
        if role is None or role.tenant_id != tenant_id:
            raise AppError("角色不存在", code="ROLE_NOT_FOUND", status_code=404)
        if name is not None:
            role.name = name
        if remark is not None:
            role.remark = remark
        if status is not None:
            role.status = status
        if all_parks is not None:
            role.all_parks = all_parks
        if permission_codes is not None:
            try:
                self.repo.replace_role_permissions(tenant_id, role.id, permission_codes)
            except KeyError as exc:
                raise AppError(
                    f"权限码不存在: {exc.args[0]}", code="PERM_NOT_FOUND", status_code=400
                ) from exc
        if park_ids is not None:
            self.repo.replace_role_parks(tenant_id, role.id, park_ids)
        if menu_ids is not None:
            self.repo.replace_role_menus(tenant_id, role.id, menu_ids)
        self.repo.commit()
        self.repo.refresh(role)
        return self._to_dict(role)

    def list_permissions(self) -> list[dict]:
        return [
            {"id": p.id, "code": p.code, "name": p.name, "module": p.module}
            for p in self.repo.list_permissions()
        ]

    def _to_dict(self, role) -> dict:
        return {
            "id": role.id,
            "tenant_id": role.tenant_id,
            "code": role.code,
            "name": role.name,
            "status": role.status,
            "remark": role.remark,
            "all_parks": bool(role.all_parks),
            "permission_codes": self.repo.role_permission_codes(role.id),
            "park_ids": self.repo.role_park_ids(role.id),
            "menu_ids": self.repo.role_menu_ids(role.id),
        }

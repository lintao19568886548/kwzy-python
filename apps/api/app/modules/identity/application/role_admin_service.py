"""角色与权限管理。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.modules.identity.infrastructure.identity_admin_repository import (
    IdentityAdminRepository,
)
from app.shared.tenant_context import TenantContext

UTC = timezone.utc


class RoleAdminService:
    def __init__(self, session: Session, ctx: TenantContext | None = None) -> None:
        self.repo = IdentityAdminRepository(session)
        self.audit = AuditRecorder(session, ctx) if ctx is not None else None

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
        if all_parks and park_ids:
            raise AppError(
                "全园区与指定园区不能同时设置",
                code="PARK_SCOPE_CONFLICT",
                status_code=400,
            )
        if not self.repo.validate_park_ids(tenant_id, park_ids or []):
            raise AppError("园区范围无效", code="PARK_SCOPE_INVALID", status_code=400)
        if not self.repo.validate_menu_ids(tenant_id, menu_ids or []):
            raise AppError("菜单授权无效", code="MENU_SCOPE_INVALID", status_code=400)

        try:
            role = self.repo.create_role_entity(
                tenant_id=tenant_id,
                code=code,
                name=name,
                remark=remark,
                all_parks=all_parks,
            )
            try:
                self.repo.replace_role_permissions(
                    tenant_id,
                    role.id,
                    permission_codes or [],
                )
            except KeyError as exc:
                raise AppError(
                    f"权限码不存在: {exc.args[0]}",
                    code="PERM_NOT_FOUND",
                    status_code=400,
                ) from exc
            self.repo.replace_role_parks(tenant_id, role.id, park_ids or [])
            self.repo.replace_role_menus(tenant_id, role.id, menu_ids or [])
            if self.audit:
                self.audit.record(
                    action="create",
                    resource_type="IDENTITY_ROLE",
                    resource_id=role.id,
                    detail={
                        "all_parks": all_parks,
                        "permission_count": len(permission_codes or []),
                        "park_count": len(park_ids or []),
                        "menu_count": len(menu_ids or []),
                    },
                )
            self.repo.commit()
        except IntegrityError as exc:
            self.repo.rollback()
            raise AppError("角色编码已存在", code="ROLE_EXISTS", status_code=409) from exc
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

        invalidates_authorization = False
        changed_fields: list[str] = []
        if name is not None:
            role.name = name
            changed_fields.append("name")
        if remark is not None:
            role.remark = remark
            changed_fields.append("remark")
        if status is not None:
            if status not in {"ACTIVE", "DISABLED"}:
                raise AppError("非法状态", code="ROLE_INVALID_STATUS", status_code=400)
            if role.status != status:
                role.status = status
                invalidates_authorization = True
                changed_fields.append("status")
        if all_parks is not None:
            effective_parks = (
                park_ids if park_ids is not None else self.repo.role_park_ids(role.id)
            )
            if all_parks and effective_parks:
                raise AppError(
                    "全园区与指定园区不能同时设置",
                    code="PARK_SCOPE_CONFLICT",
                    status_code=400,
                )
            if bool(role.all_parks) != all_parks:
                role.all_parks = all_parks
                invalidates_authorization = True
                changed_fields.append("all_parks")
        if permission_codes is not None:
            try:
                self.repo.replace_role_permissions(tenant_id, role.id, permission_codes)
            except KeyError as exc:
                raise AppError(
                    f"权限码不存在: {exc.args[0]}",
                    code="PERM_NOT_FOUND",
                    status_code=400,
                ) from exc
            invalidates_authorization = True
            changed_fields.append("permission_codes")
        if park_ids is not None:
            effective_all = all_parks if all_parks is not None else bool(role.all_parks)
            if effective_all and park_ids:
                raise AppError(
                    "全园区与指定园区不能同时设置",
                    code="PARK_SCOPE_CONFLICT",
                    status_code=400,
                )
            if not self.repo.validate_park_ids(tenant_id, park_ids):
                raise AppError("园区范围无效", code="PARK_SCOPE_INVALID", status_code=400)
            self.repo.replace_role_parks(tenant_id, role.id, park_ids)
            invalidates_authorization = True
            changed_fields.append("park_ids")
        if menu_ids is not None:
            if not self.repo.validate_menu_ids(tenant_id, menu_ids):
                raise AppError("菜单授权无效", code="MENU_SCOPE_INVALID", status_code=400)
            self.repo.replace_role_menus(tenant_id, role.id, menu_ids)
            changed_fields.append("menu_ids")

        if invalidates_authorization:
            self.repo.invalidate_user_sessions(
                self.repo.user_ids_for_role(tenant_id, role.id),
                datetime.now(UTC).replace(tzinfo=None),
            )
        if self.audit:
            self.audit.record(
                action="update",
                resource_type="IDENTITY_ROLE",
                resource_id=role.id,
                detail={"fields": sorted(set(changed_fields))},
            )
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

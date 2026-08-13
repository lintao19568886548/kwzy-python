"""Identity interface — auth session + system admin."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.identity.application.auth_service import AuthService
from app.modules.identity.application.menu_admin_service import MenuAdminService
from app.modules.identity.application.role_admin_service import RoleAdminService
from app.modules.identity.application.user_admin_service import UserAdminService
from app.modules.identity.schemas import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    MenuCreateRequest,
    PasswordChangeRequest,
    RefreshRequest,
    RoleCreateRequest,
    RoleUpdateRequest,
    UserCreateRequest,
    UserInfo,
    UserUpdateRequest,
)
from app.shared.deps import TenantContext, get_tenant_context, require_permissions
from app.shared.response import ok

router = APIRouter(tags=["Identity"])


@router.post("/auth/login")
def login(body: LoginRequest, db: Session = Depends(get_db)) -> dict:
    data = LoginResponse.model_validate(
        AuthService(db).login(
            username=body.username,
            password=body.password,
            tenant_code=body.tenant_code,
        )
    )
    return ok(data.model_dump())


@router.post("/auth/refresh")
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> dict:
    data = LoginResponse.model_validate(AuthService(db).refresh(refresh_token=body.refresh_token))
    return ok(data.model_dump())


@router.post("/auth/logout")
def logout(body: LogoutRequest, db: Session = Depends(get_db)) -> dict:
    AuthService(db).logout(refresh_token=body.refresh_token)
    return ok({"message": "ok"})


@router.post("/auth/password")
def change_password(
    body: PasswordChangeRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    data = AuthService(db).change_password(
        user_id=ctx.user_id,
        tenant_id=ctx.tenant_id,
        old_password=body.old_password,
        new_password=body.new_password,
    )
    return ok(data)


@router.get("/auth/codes")
def auth_codes(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    codes = AuthService(db).permission_codes(user_id=ctx.user_id, tenant_id=ctx.tenant_id)
    return ok(codes)


@router.get("/auth/me")
def me(ctx: TenantContext = Depends(get_tenant_context)) -> dict:
    info = UserInfo(
        id=ctx.user_id,
        tenant_id=ctx.tenant_id,
        username=ctx.username,
        permissions=ctx.permissions,
        park_ids=ctx.park_ids,
    )
    return ok(info.model_dump())


@router.get("/auth/menus")
def my_menus(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    data = MenuAdminService(db).menus_for_user(tenant_id=ctx.tenant_id, user_id=ctx.user_id)
    return ok(data)


# --- system admin ---


@router.get("/system/users")
def list_users(
    ctx: TenantContext = Depends(require_permissions("identity.user.read")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(UserAdminService(db).list_users(tenant_id=ctx.tenant_id))


@router.post("/system/users")
def create_user(
    body: UserCreateRequest,
    ctx: TenantContext = Depends(require_permissions("identity.user.write")),
    db: Session = Depends(get_db),
) -> dict:
    data = UserAdminService(db).create_user(
        tenant_id=ctx.tenant_id,
        username=body.username,
        password=body.password,
        real_name=body.real_name,
        phone=body.phone,
        role_ids=body.role_ids,
        park_ids=body.park_ids,
        all_parks=body.all_parks,
    )
    return ok(data)


@router.put("/system/users/{user_id}")
def update_user(
    user_id: int,
    body: UserUpdateRequest,
    ctx: TenantContext = Depends(require_permissions("identity.user.write")),
    db: Session = Depends(get_db),
) -> dict:
    data = UserAdminService(db).update_user(
        tenant_id=ctx.tenant_id,
        user_id=user_id,
        real_name=body.real_name,
        phone=body.phone,
        status=body.status,
        role_ids=body.role_ids,
        park_ids=body.park_ids,
        all_parks=body.all_parks,
        password=body.password,
    )
    return ok(data)


@router.delete("/system/users/{user_id}")
def disable_user(
    user_id: int,
    ctx: TenantContext = Depends(require_permissions("identity.user.write")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(UserAdminService(db).disable_user(tenant_id=ctx.tenant_id, user_id=user_id))


@router.get("/system/roles")
def list_roles(
    ctx: TenantContext = Depends(require_permissions("identity.role.read")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(RoleAdminService(db).list_roles(tenant_id=ctx.tenant_id))


@router.post("/system/roles")
def create_role(
    body: RoleCreateRequest,
    ctx: TenantContext = Depends(require_permissions("identity.role.write")),
    db: Session = Depends(get_db),
) -> dict:
    data = RoleAdminService(db).create_role(
        tenant_id=ctx.tenant_id,
        code=body.code,
        name=body.name,
        remark=body.remark,
        all_parks=body.all_parks,
        permission_codes=body.permission_codes,
        park_ids=body.park_ids,
        menu_ids=body.menu_ids,
    )
    return ok(data)


@router.put("/system/roles/{role_id}")
def update_role(
    role_id: int,
    body: RoleUpdateRequest,
    ctx: TenantContext = Depends(require_permissions("identity.role.write")),
    db: Session = Depends(get_db),
) -> dict:
    data = RoleAdminService(db).update_role(
        tenant_id=ctx.tenant_id,
        role_id=role_id,
        name=body.name,
        remark=body.remark,
        status=body.status,
        all_parks=body.all_parks,
        permission_codes=body.permission_codes,
        park_ids=body.park_ids,
        menu_ids=body.menu_ids,
    )
    return ok(data)


@router.get("/system/permissions")
def list_permissions(
    ctx: TenantContext = Depends(require_permissions("identity.role.read")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(RoleAdminService(db).list_permissions())


@router.get("/system/menus")
def list_menus(
    ctx: TenantContext = Depends(require_permissions("identity.menu.read")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(MenuAdminService(db).list_menus(tenant_id=ctx.tenant_id))


@router.post("/system/menus")
def create_menu(
    body: MenuCreateRequest,
    ctx: TenantContext = Depends(require_permissions("identity.menu.write")),
    db: Session = Depends(get_db),
) -> dict:
    data = MenuAdminService(db).create_menu(
        tenant_id=ctx.tenant_id,
        name=body.name,
        path=body.path,
        parent_id=body.parent_id,
        component=body.component,
        icon=body.icon,
        sort_order=body.sort_order,
        menu_type=body.menu_type,
        permission_code=body.permission_code,
    )
    return ok(data)

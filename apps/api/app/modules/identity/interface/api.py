"""Identity interface — auth session + system admin."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.infrastructure.database.session import get_db
from app.modules.identity.application.auth_service import AuthService
from app.modules.identity.application.config_admin_service import ConfigAdminService
from app.modules.identity.application.menu_admin_service import MenuAdminService
from app.modules.identity.application.page_access_service import PageAccessService
from app.modules.identity.application.role_admin_service import RoleAdminService
from app.modules.identity.application.user_admin_service import UserAdminService
from app.modules.identity.schemas import (
    DictItemCreateRequest,
    DictTypeCreateRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    MenuCreateRequest,
    MenuUpdateRequest,
    OrgUnitCreateRequest,
    OrgUnitUpdateRequest,
    PageAccessConsumeRequest,
    PageAccessSendRequest,
    PageAccessVerifyRequest,
    PasswordChangeRequest,
    RefreshRequest,
    RoleCreateRequest,
    RoleUpdateRequest,
    SystemParamUpsertRequest,
    UserCreateRequest,
    UserInfo,
    UserUpdateRequest,
)
from app.shared.deps import TenantContext, get_tenant_context, require_permissions
from app.shared.response import ok

router = APIRouter(tags=["Identity"])


def _enforce_cookie_origin(request: Request) -> None:
    """Require an approved browser Origin when a production-like cookie is used."""

    settings = get_settings()
    if settings.app_env not in {"staging", "production"}:
        return
    origin = (request.headers.get("origin") or "").rstrip("/")
    allowed = {
        item.strip().rstrip("/")
        for item in settings.cors_origins.split(",")
        if item.strip()
    }
    if not origin or origin not in allowed:
        raise AppError(
            "请求来源校验失败",
            code="CSRF_ORIGIN_DENIED",
            status_code=403,
        )


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path=f"{settings.api_v1_prefix}/auth",
        secure=settings.app_env in {"staging", "production"},
        httponly=True,
        samesite="strict",
    )


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=f"{settings.api_v1_prefix}/auth",
        secure=settings.app_env in {"staging", "production"},
        httponly=True,
        samesite="strict",
    )


@router.post("/auth/login")
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    data = LoginResponse.model_validate(
        AuthService(db).login(
            username=body.username,
            password=body.password,
            tenant_code=body.tenant_code,
            client_ip=request.client.host if request.client else None,
        )
    )
    _set_refresh_cookie(response, data.refresh_token)
    return ok(data.model_dump())


@router.post("/auth/refresh")
def refresh(
    body: RefreshRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    refresh_token = body.refresh_token or request.cookies.get(settings.refresh_cookie_name)
    if not refresh_token:
        raise AppError("缺少刷新令牌", code="AUTH_REFRESH_REQUIRED", status_code=401)
    if body.refresh_token is None:
        _enforce_cookie_origin(request)
    data = LoginResponse.model_validate(
        AuthService(db).refresh(
            refresh_token=refresh_token,
            client_ip=request.client.host if request.client else None,
        )
    )
    _set_refresh_cookie(response, data.refresh_token)
    return ok(data.model_dump())


@router.post("/auth/logout")
def logout(
    body: LogoutRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    refresh_token = body.refresh_token or request.cookies.get(settings.refresh_cookie_name)
    if body.refresh_token is None and refresh_token:
        _enforce_cookie_origin(request)
    AuthService(db).logout(refresh_token=refresh_token)
    _clear_refresh_cookie(response)
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


@router.post("/auth/page-access/send")
def send_page_access_code(
    body: PageAccessSendRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    return ok(
        PageAccessService(db).send_code(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            purpose=body.purpose,
        ),
        message="sent",
    )


@router.post("/auth/page-access/verify")
def verify_page_access_code(
    body: PageAccessVerifyRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    return ok(
        PageAccessService(db).verify_code(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            purpose=body.purpose,
            code=body.code,
        )
    )


@router.post("/auth/page-access/consume")
def consume_page_access_proof(
    body: PageAccessConsumeRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    return ok(
        PageAccessService(db).consume_proof(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            purpose=body.purpose,
            proof=body.proof,
        )
    )


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
    return ok(UserAdminService(db, ctx).list_users(tenant_id=ctx.tenant_id))


@router.post("/system/users")
def create_user(
    body: UserCreateRequest,
    ctx: TenantContext = Depends(require_permissions("identity.user.write")),
    db: Session = Depends(get_db),
) -> dict:
    data = UserAdminService(db, ctx).create_user(
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
    data = UserAdminService(db, ctx).update_user(
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
    return ok(
        UserAdminService(db, ctx).disable_user(
            tenant_id=ctx.tenant_id,
            user_id=user_id,
        )
    )


@router.post("/system/users/{user_id}/revoke-sessions")
def revoke_user_sessions(
    user_id: int,
    ctx: TenantContext = Depends(require_permissions("identity.user.write")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(
        UserAdminService(db, ctx).revoke_sessions(
            tenant_id=ctx.tenant_id,
            user_id=user_id,
        )
    )


@router.get("/system/roles")
def list_roles(
    ctx: TenantContext = Depends(require_permissions("identity.role.read")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(RoleAdminService(db, ctx).list_roles(tenant_id=ctx.tenant_id))


@router.post("/system/roles")
def create_role(
    body: RoleCreateRequest,
    ctx: TenantContext = Depends(require_permissions("identity.role.write")),
    db: Session = Depends(get_db),
) -> dict:
    data = RoleAdminService(db, ctx).create_role(
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
    data = RoleAdminService(db, ctx).update_role(
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
    return ok(RoleAdminService(db, ctx).list_permissions())


@router.get("/system/menus")
def list_menus(
    ctx: TenantContext = Depends(require_permissions("identity.menu.read")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(MenuAdminService(db, ctx).list_menus(tenant_id=ctx.tenant_id))


@router.post("/system/menus")
def create_menu(
    body: MenuCreateRequest,
    ctx: TenantContext = Depends(require_permissions("identity.menu.write")),
    db: Session = Depends(get_db),
) -> dict:
    data = MenuAdminService(db, ctx).create_menu(
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


@router.put("/system/menus/{menu_id}")
def update_menu(
    menu_id: int,
    body: MenuUpdateRequest,
    ctx: TenantContext = Depends(require_permissions("identity.menu.write")),
    db: Session = Depends(get_db),
) -> dict:
    data = MenuAdminService(db, ctx).update_menu(
        tenant_id=ctx.tenant_id,
        menu_id=menu_id,
        data=body.model_dump(exclude_unset=True),
    )
    return ok(data)


@router.delete("/system/menus/{menu_id}")
def deactivate_menu(
    menu_id: int,
    ctx: TenantContext = Depends(require_permissions("identity.menu.write")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(
        MenuAdminService(db, ctx).deactivate_menu(
            tenant_id=ctx.tenant_id,
            menu_id=menu_id,
        )
    )


@router.get("/system/org-units")
def list_org_units(
    ctx: TenantContext = Depends(require_permissions("identity.org.read")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(ConfigAdminService(db).list_org_units(tenant_id=ctx.tenant_id))


@router.post("/system/org-units")
def create_org_unit(
    body: OrgUnitCreateRequest,
    ctx: TenantContext = Depends(require_permissions("identity.org.write")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(
        ConfigAdminService(db).create_org_unit(tenant_id=ctx.tenant_id, data=body.model_dump()),
        message="created",
    )


@router.patch("/system/org-units/{org_id}")
def update_org_unit(
    org_id: int,
    body: OrgUnitUpdateRequest,
    ctx: TenantContext = Depends(require_permissions("identity.org.write")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(
        ConfigAdminService(db).update_org_unit(
            tenant_id=ctx.tenant_id,
            org_id=org_id,
            data=body.model_dump(exclude_unset=True),
        ),
        message="updated",
    )


@router.get("/system/dict-types")
def list_dict_types(
    ctx: TenantContext = Depends(require_permissions("identity.dict.read")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(ConfigAdminService(db).list_dict_types(tenant_id=ctx.tenant_id))


@router.post("/system/dict-types")
def create_dict_type(
    body: DictTypeCreateRequest,
    ctx: TenantContext = Depends(require_permissions("identity.dict.write")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(
        ConfigAdminService(db).create_dict_type(tenant_id=ctx.tenant_id, data=body.model_dump()),
        message="created",
    )


@router.get("/system/dict-types/{type_code}/items")
def list_dict_items(
    type_code: str,
    ctx: TenantContext = Depends(require_permissions("identity.dict.read")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(
        ConfigAdminService(db).list_dict_items(tenant_id=ctx.tenant_id, type_code=type_code)
    )


@router.post("/system/dict-types/{type_code}/items")
def create_dict_item(
    type_code: str,
    body: DictItemCreateRequest,
    ctx: TenantContext = Depends(require_permissions("identity.dict.write")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(
        ConfigAdminService(db).create_dict_item(
            tenant_id=ctx.tenant_id, type_code=type_code, data=body.model_dump()
        ),
        message="created",
    )


@router.get("/system/params")
def list_params(
    ctx: TenantContext = Depends(require_permissions("identity.param.read")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(ConfigAdminService(db).list_params(tenant_id=ctx.tenant_id))


@router.put("/system/params")
def upsert_param(
    body: SystemParamUpsertRequest,
    ctx: TenantContext = Depends(require_permissions("identity.param.write")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(
        ConfigAdminService(db).upsert_param(tenant_id=ctx.tenant_id, data=body.model_dump()),
        message="saved",
    )


@router.get("/system/params/{param_key}")
def get_param(
    param_key: str,
    ctx: TenantContext = Depends(require_permissions("identity.param.read")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(ConfigAdminService(db).get_param(tenant_id=ctx.tenant_id, param_key=param_key))

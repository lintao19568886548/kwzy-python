"""Identity 租户登录、RBAC 与接口权限测试。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import create_access_token, decode_access_token, hash_password
from app.infrastructure.database.models.identity import (
    Permission,
    Role,
    RoleParkScope,
    RolePermission,
    Tenant,
    User,
    UserRole,
)
from app.main import create_app
from app.modules.identity.application.auth_service import AuthService
from app.modules.identity.application.bootstrap import ensure_default_tenant
from app.modules.park_property.application.park_service import ParkService
from app.shared.tenant_context import ParkScopeMode, TenantContext


def _admin_ctx() -> TenantContext:
    return TenantContext(
        tenant_id=1,
        user_id=1,
        username="admin",
        permissions=["*"],
        park_scope_mode=ParkScopeMode.ALL,
    )


def test_admin_login_has_star_and_all_parks(db_session: Session) -> None:
    result = AuthService(db_session).login(
        username="admin",
        password="admin123",
        tenant_code="default",
    )
    assert "*" in result["user"]["permissions"]
    assert result["user"]["park_scope_mode"] == "ALL"
    claims = decode_access_token(result["access_token"])
    assert claims["park_scope_mode"] == "ALL"
    assert claims["park_ids"] == []


def test_scoped_login_claims_come_from_database(db_session: Session) -> None:
    park = ParkService(db_session, _admin_ctx()).create_park({"name": "授权园区"})
    user = User(
        tenant_id=1,
        username="scoped-user",
        password_hash=hash_password("secret123"),
        real_name="范围用户",
        status="ACTIVE",
    )
    db_session.add(user)
    db_session.flush()
    role = Role(tenant_id=1, code="PARK_VIEWER", name="园区查看", status="ACTIVE")
    db_session.add(role)
    db_session.flush()
    permission = db_session.scalars(
        select(Permission).where(Permission.code == "park:read")
    ).one()
    db_session.add_all(
        [
            UserRole(tenant_id=1, user_id=user.id, role_id=role.id),
            RolePermission(
                tenant_id=1,
                role_id=role.id,
                permission_id=permission.id,
            ),
            RoleParkScope(
                tenant_id=1,
                role_id=role.id,
                park_id=park["id"],
            ),
        ]
    )
    db_session.commit()

    result = AuthService(db_session).login(
        username="scoped-user",
        password="secret123",
        tenant_code="default",
    )
    assert result["user"]["permissions"] == ["park:read"]
    assert result["user"]["park_ids"] == [park["id"]]
    assert result["user"]["park_scope_mode"] == "LIST"
    claims = decode_access_token(result["access_token"])
    assert claims["permissions"] == ["park:read"]
    assert claims["park_ids"] == [park["id"]]
    assert claims["park_scope_mode"] == "LIST"
    assert claims["is_platform_admin"] is False


def test_star_without_park_scope_is_action_only(db_session: Session) -> None:
    """全部动作权限但无园区范围 → park_scope_mode=NONE。"""
    star = db_session.scalars(select(Permission).where(Permission.code == "*")).one()
    user = User(
        tenant_id=1,
        username="star-no-park",
        password_hash=hash_password("secret123"),
        real_name="仅动作",
        status="ACTIVE",
        all_parks=False,
    )
    db_session.add(user)
    db_session.flush()
    role = Role(
        tenant_id=1,
        code="STAR_NO_PARK",
        name="全动作无园区",
        status="ACTIVE",
        all_parks=False,
    )
    db_session.add(role)
    db_session.flush()
    db_session.add_all(
        [
            UserRole(tenant_id=1, user_id=user.id, role_id=role.id),
            RolePermission(
                tenant_id=1, role_id=role.id, permission_id=star.id
            ),
        ]
    )
    db_session.commit()

    result = AuthService(db_session).login(
        username="star-no-park",
        password="secret123",
        tenant_code="default",
    )
    assert "*" in result["user"]["permissions"]
    assert result["user"]["park_scope_mode"] == "NONE"
    assert result["user"]["park_ids"] == []


def test_parks_without_action_permission(db_session: Session) -> None:
    """有园区范围但无动作权限。"""
    park = ParkService(db_session, _admin_ctx()).create_park({"name": "仅范围园"})
    user = User(
        tenant_id=1,
        username="park-no-action",
        password_hash=hash_password("secret123"),
        real_name="仅园区",
        status="ACTIVE",
    )
    db_session.add(user)
    db_session.flush()
    role = Role(
        tenant_id=1,
        code="PARK_ONLY",
        name="仅园区",
        status="ACTIVE",
        all_parks=False,
    )
    db_session.add(role)
    db_session.flush()
    db_session.add_all(
        [
            UserRole(tenant_id=1, user_id=user.id, role_id=role.id),
            RoleParkScope(tenant_id=1, role_id=role.id, park_id=park["id"]),
        ]
    )
    db_session.commit()

    result = AuthService(db_session).login(
        username="park-no-action",
        password="secret123",
        tenant_code="default",
    )
    assert result["user"]["permissions"] == []
    assert result["user"]["park_scope_mode"] == "LIST"
    assert result["user"]["park_ids"] == [park["id"]]


def test_star_plus_list_parks(db_session: Session) -> None:
    """全部动作 + 指定园区 LIST。"""
    park = ParkService(db_session, _admin_ctx()).create_park({"name": "LIST园"})
    star = db_session.scalars(select(Permission).where(Permission.code == "*")).one()
    user = User(
        tenant_id=1,
        username="star-list",
        password_hash=hash_password("secret123"),
        real_name="动作加列表",
        status="ACTIVE",
        all_parks=False,
    )
    db_session.add(user)
    db_session.flush()
    role = Role(
        tenant_id=1,
        code="STAR_LIST",
        name="动作+列表",
        status="ACTIVE",
        all_parks=False,
    )
    db_session.add(role)
    db_session.flush()
    db_session.add_all(
        [
            UserRole(tenant_id=1, user_id=user.id, role_id=role.id),
            RolePermission(tenant_id=1, role_id=role.id, permission_id=star.id),
            RoleParkScope(tenant_id=1, role_id=role.id, park_id=park["id"]),
        ]
    )
    db_session.commit()

    result = AuthService(db_session).login(
        username="star-list",
        password="secret123",
        tenant_code="default",
    )
    assert "*" in result["user"]["permissions"]
    assert result["user"]["park_scope_mode"] == "LIST"
    assert result["user"]["park_ids"] == [park["id"]]


def test_user_all_parks_flag(db_session: Session) -> None:
    """用户级 all_parks=True → ALL。"""
    user = User(
        tenant_id=1,
        username="user-all-parks",
        password_hash=hash_password("secret123"),
        real_name="用户全园",
        status="ACTIVE",
        all_parks=True,
    )
    db_session.add(user)
    db_session.commit()

    result = AuthService(db_session).login(
        username="user-all-parks",
        password="secret123",
        tenant_code="default",
    )
    assert result["user"]["park_scope_mode"] == "ALL"


def test_cross_tenant_role_permissions_ignored(db_session: Session) -> None:
    """跨租户角色/权限关联不得生效。"""
    other = Tenant(code="other-auth", name="其他", status="ACTIVE")
    db_session.add(other)
    db_session.flush()
    star = db_session.scalars(select(Permission).where(Permission.code == "*")).one()
    foreign_role = Role(
        tenant_id=other.id,
        code="FOREIGN_ADMIN",
        name="外租户角色",
        status="ACTIVE",
        all_parks=True,
    )
    db_session.add(foreign_role)
    db_session.flush()
    db_session.add(
        RolePermission(
            tenant_id=other.id,
            role_id=foreign_role.id,
            permission_id=star.id,
        )
    )

    user = User(
        tenant_id=1,
        username="cross-tenant",
        password_hash=hash_password("secret123"),
        real_name="跨租户",
        status="ACTIVE",
    )
    db_session.add(user)
    db_session.flush()
    # 错误地把外租户角色挂到本租户用户（tenant_id 仍写 1）
    db_session.add(
        UserRole(tenant_id=1, user_id=user.id, role_id=foreign_role.id)
    )
    db_session.commit()

    result = AuthService(db_session).login(
        username="cross-tenant",
        password="secret123",
        tenant_code="default",
    )
    # Role.tenant_id 过滤应排除外租户角色
    assert result["user"]["permissions"] == []
    assert result["user"]["park_scope_mode"] == "NONE"


def test_api_rejects_missing_action_permission(client) -> None:
    token = create_access_token(
        subject="reader",
        claims={
            "uid": 99,
            "tenant_id": 1,
            "permissions": ["park:read"],
            "park_ids": [],
            "park_scope_mode": "ALL",
        },
    )
    headers = {"Authorization": f"Bearer {token}"}

    read_response = client.get("/api/v1/parks", headers=headers)
    assert read_response.status_code == 200

    write_response = client.post(
        "/api/v1/parks",
        headers=headers,
        json={"name": "无权创建"},
    )
    assert write_response.status_code == 403
    assert write_response.json() == {
        "code": "PERMISSION_DENIED",
        "message": "无操作权限",
        "data": None,
    }


def test_api_rejects_out_of_scope_park(client, db_session: Session) -> None:
    park_a = ParkService(db_session, _admin_ctx()).create_park({"name": "可见园"})
    park_b = ParkService(db_session, _admin_ctx()).create_park({"name": "不可见园"})
    token = create_access_token(
        subject="scoped",
        claims={
            "uid": 50,
            "tenant_id": 1,
            "permissions": ["park:read", "park:write"],
            "park_ids": [park_a["id"]],
            "park_scope_mode": "LIST",
        },
    )
    headers = {"Authorization": f"Bearer {token}"}
    ok = client.get(f"/api/v1/parks/{park_a['id']}", headers=headers)
    assert ok.status_code == 200
    denied = client.get(f"/api/v1/parks/{park_b['id']}", headers=headers)
    assert denied.status_code == 404


def test_login_requires_tenant_code_when_username_is_ambiguous(
    db_session: Session,
) -> None:
    tenant = Tenant(code="second", name="第二租户", status="ACTIVE")
    db_session.add(tenant)
    db_session.flush()
    db_session.add(
        User(
            tenant_id=tenant.id,
            username="admin",
            password_hash=hash_password("other-secret"),
            real_name="第二管理员",
            status="ACTIVE",
        )
    )
    db_session.commit()

    with pytest.raises(AppError) as exc_info:
        AuthService(db_session).login(username="admin", password="admin123")
    assert exc_info.value.code == "AUTH_TENANT_AMBIGUOUS"

    result = AuthService(db_session).login(
        username="admin",
        password="other-secret",
        tenant_code="second",
    )
    assert result["user"]["tenant_id"] == tenant.id
    assert result["user"]["permissions"] == []


def test_production_requires_token(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "production-test-secret")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.test")
    monkeypatch.setenv("ALLOW_ANON_DEV", "false")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as production_client:
            response = production_client.get("/api/v1/parks")
        assert response.status_code == 401
        assert response.json()["code"] == "UNAUTHORIZED"
    finally:
        get_settings.cache_clear()


def test_production_settings_reject_insecure_defaults() -> None:
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="change-me-in-production",
            cors_origins="https://app.example.test",
            allow_anon_dev=False,
        )
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="production-test-secret",
            cors_origins="*",
            allow_anon_dev=False,
        )

    settings = Settings(
        _env_file=None,
        app_env="production",
        jwt_secret="production-test-secret",
        cors_origins="https://app.example.test",
        allow_anon_dev=False,
    )
    assert settings.app_env == "production"


def test_production_bootstrap_forbidden(db_session: Session, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "production-test-secret")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.test")
    monkeypatch.setenv("ALLOW_ANON_DEV", "false")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="production"):
            ensure_default_tenant(db_session)
    finally:
        get_settings.cache_clear()

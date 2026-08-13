"""FastAPI dependencies — auth fail-closed by default."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import TokenError, safe_decode
from app.infrastructure.database.session import get_db
from app.infrastructure.database.models.identity import User
from app.shared.tenant_context import ParkScopeMode, TenantContext

_bearer = HTTPBearer(auto_error=False)


def _mode_from_claims(
    raw_mode: object,
    park_ids: list[int],
) -> ParkScopeMode:
    """从 JWT 解析园区模式；兼容缺省 claim 的旧令牌（不把 * 当全园）。"""

    if raw_mode:
        try:
            return ParkScopeMode(str(raw_mode))
        except ValueError:
            pass
    if park_ids:
        return ParkScopeMode.LIST
    return ParkScopeMode.NONE


def get_tenant_context(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> TenantContext:
    """
    Resolve tenant context from JWT.

    Fail-closed: missing Bearer raises 401 unless explicit local/test
    ALLOW_ANON_DEV is enabled. Production/staging never allow anonymous.
    """
    settings = get_settings()
    if creds is None or not creds.credentials:
        if not settings.allows_anonymous_dev_identity():
            raise AppError("未登录", code="UNAUTHORIZED", status_code=401)
        return TenantContext(
            tenant_id=1,
            user_id=1,
            username="dev",
            park_ids=[],
            permissions=["*"],
            park_scope_mode=ParkScopeMode.ALL,
            is_platform_admin=False,
            request_id=getattr(request.state, "request_id", ""),
            client_ip=request.client.host if request.client else None,
        )
    try:
        payload = safe_decode(creds.credentials)
    except TokenError as exc:
        raise AppError("未登录或令牌无效", code="UNAUTHORIZED", status_code=401) from exc

    tenant_id = int(payload.get("tenant_id") or 0)
    if tenant_id <= 0:
        raise AppError("令牌缺少有效 tenant_id", code="UNAUTHORIZED", status_code=401)
    user_id = int(payload.get("uid") or 0)
    if user_id <= 0:
        raise AppError("令牌缺少有效用户", code="UNAUTHORIZED", status_code=401)

    # JWT 中的权限/园区仍是短期快照，但账号停用、改密、会话撤销和
    # 授权变更必须立即生效，因此每个受保护请求只读取最小会话版本。
    user_state = db.execute(
        select(User.tenant_id, User.status, User.token_version).where(User.id == user_id)
    ).one_or_none()
    token_version = int(payload.get("tv") or 0)
    if (
        user_state is None
        or int(user_state.tenant_id) != tenant_id
        or str(user_state.status) != "ACTIVE"
        or int(user_state.token_version or 0) != token_version
    ):
        raise AppError("会话已失效，请重新登录", code="AUTH_SESSION_REVOKED", status_code=401)

    park_ids = [int(x) for x in (payload.get("park_ids") or [])]
    permissions = list(payload.get("permissions") or [])
    park_scope_mode = _mode_from_claims(payload.get("park_scope_mode"), park_ids)
    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        username=str(payload.get("sub") or ""),
        park_ids=park_ids,
        permissions=permissions,
        park_scope_mode=park_scope_mode,
        is_platform_admin=bool(payload.get("is_platform_admin", False)),
        request_id=getattr(request.state, "request_id", ""),
        client_ip=request.client.host if request.client else None,
    )


def get_current_user(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
    return ctx


def require_permissions(*permission_codes: str) -> Callable[..., TenantContext]:
    """生成权限依赖；所有指定权限码都必须满足。"""

    def _check(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        missing = [code for code in permission_codes if not ctx.has_permission(code)]
        if missing:
            raise AppError(
                "无操作权限",
                code="PERMISSION_DENIED",
                status_code=403,
            )
        return ctx

    return _check


CurrentUser = TenantContext


def get_tenant_db(db: Session = Depends(get_db)) -> Session:
    return db

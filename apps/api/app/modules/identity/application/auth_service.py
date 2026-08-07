"""Identity 登录应用服务。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import create_access_token, verify_password
from app.modules.identity.infrastructure.authorization_repository import (
    AuthorizationRepository,
)


class AuthService:
    """编排租户用户认证、授权解析与 JWT 签发。"""

    def __init__(self, session: Session) -> None:
        self.repo = AuthorizationRepository(session)

    def login(
        self,
        *,
        username: str,
        password: str,
        tenant_code: str | None = None,
    ) -> dict:
        """验证凭据并返回数据库授权关系生成的登录结果。"""

        candidates = self.repo.find_login_candidates(
            username=username,
            tenant_code=tenant_code.strip() if tenant_code else None,
        )
        if not candidates:
            raise AppError("用户名或密码错误", code="AUTH_BAD_PASSWORD", status_code=403)
        if len(candidates) > 1:
            raise AppError(
                "该用户名对应多个租户，请指定租户后登录",
                code="AUTH_TENANT_AMBIGUOUS",
                status_code=400,
            )

        user = candidates[0]
        if not verify_password(password, user.password_hash):
            raise AppError("用户名或密码错误", code="AUTH_BAD_PASSWORD", status_code=403)

        permissions, park_ids, park_scope_mode = self.repo.resolve_authorization(user)
        # is_platform_admin 保留字段：历史上用 * 表示超管动作；不再表示全园区。
        is_platform_admin = "*" in permissions
        token = create_access_token(
            subject=user.username,
            claims={
                "uid": user.id,
                "tenant_id": user.tenant_id,
                "park_ids": park_ids,
                "park_scope_mode": park_scope_mode.value,
                "permissions": permissions,
                "is_platform_admin": is_platform_admin,
            },
        )
        settings = get_settings()
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
            "user": {
                "id": user.id,
                "tenant_id": user.tenant_id,
                "username": user.username,
                "real_name": user.real_name,
                "permissions": permissions,
                "park_ids": park_ids,
                "park_scope_mode": park_scope_mode.value,
            },
        }

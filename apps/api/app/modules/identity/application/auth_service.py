"""Identity 登录与会话应用服务。"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.modules.identity.infrastructure.authorization_repository import (
    AuthorizationRepository,
)
from app.modules.identity.infrastructure.identity_admin_repository import (
    IdentityAdminRepository,
)

UTC = timezone.utc


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AuthService:
    """编排租户用户认证、会话与 JWT 签发。"""

    def __init__(self, session: Session) -> None:
        self.auth_repo = AuthorizationRepository(session)
        self.admin_repo = IdentityAdminRepository(session)

    def login(
        self,
        *,
        username: str,
        password: str,
        tenant_code: str | None = None,
    ) -> dict:
        candidates = self.auth_repo.find_login_candidates(
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
        return self._issue_session(user)

    def refresh(self, *, refresh_token: str) -> dict:
        token_hash = _hash_token(refresh_token)
        row = self.admin_repo.get_refresh_by_hash(token_hash)
        if row is None or row.revoked_at is not None:
            raise AppError("刷新令牌无效", code="AUTH_REFRESH_INVALID", status_code=401)
        exp = row.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        if exp < datetime.now(UTC):
            raise AppError("刷新令牌已过期", code="AUTH_REFRESH_EXPIRED", status_code=401)
        user = self.admin_repo.get_user(row.user_id)
        if user is None or user.status != "ACTIVE" or user.tenant_id != row.tenant_id:
            raise AppError("刷新令牌无效", code="AUTH_REFRESH_INVALID", status_code=401)
        row.revoked_at = datetime.now(UTC).replace(tzinfo=None)
        result = self._issue_session(user)
        row.replaced_by_hash = _hash_token(result["refresh_token"])
        self.admin_repo.commit()
        return result

    def logout(self, *, refresh_token: str | None) -> None:
        if not refresh_token:
            return
        row = self.admin_repo.get_refresh_by_hash(_hash_token(refresh_token))
        if row and row.revoked_at is None:
            row.revoked_at = datetime.now(UTC).replace(tzinfo=None)
            self.admin_repo.commit()

    def change_password(
        self,
        *,
        user_id: int,
        tenant_id: int,
        old_password: str,
        new_password: str,
    ) -> dict:
        if len(new_password) < 6:
            raise AppError("新密码至少 6 位", code="AUTH_WEAK_PASSWORD", status_code=400)
        user = self.admin_repo.get_user(user_id)
        if user is None or user.tenant_id != tenant_id:
            raise AppError("用户不存在", code="AUTH_USER_NOT_FOUND", status_code=404)
        if not verify_password(old_password, user.password_hash):
            raise AppError("原密码错误", code="AUTH_BAD_PASSWORD", status_code=400)
        user.password_hash = hash_password(new_password)
        user.token_version = int(getattr(user, "token_version", 0) or 0) + 1
        self.admin_repo.revoke_user_refresh(user.id, datetime.now(UTC).replace(tzinfo=None))
        self.admin_repo.commit()
        return {"message": "密码修改成功"}

    def permission_codes(self, *, user_id: int, tenant_id: int) -> list[str]:
        user = self.admin_repo.get_user(user_id)
        if user is None or user.tenant_id != tenant_id:
            raise AppError("用户不存在", code="AUTH_USER_NOT_FOUND", status_code=404)
        permissions, _, _ = self.auth_repo.resolve_authorization(user)
        return permissions

    def _issue_session(self, user) -> dict:
        permissions, park_ids, park_scope_mode = self.auth_repo.resolve_authorization(user)
        is_platform_admin = "*" in permissions
        settings = get_settings()
        token = create_access_token(
            subject=user.username,
            claims={
                "uid": user.id,
                "tenant_id": user.tenant_id,
                "park_ids": park_ids,
                "park_scope_mode": park_scope_mode.value,
                "permissions": permissions,
                "is_platform_admin": is_platform_admin,
                "tv": int(getattr(user, "token_version", 0) or 0),
            },
        )
        raw_refresh = secrets.token_urlsafe(48)
        refresh_days = int(getattr(settings, "refresh_token_expire_days", 14) or 14)
        expires_at = datetime.now(UTC) + timedelta(days=refresh_days)
        self.admin_repo.add_refresh(
            tenant_id=user.tenant_id,
            user_id=user.id,
            token_hash=_hash_token(raw_refresh),
            expires_at=expires_at.replace(tzinfo=None),
        )
        self.admin_repo.commit()
        return {
            "access_token": token,
            "refresh_token": raw_refresh,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
            "user": {
                "id": user.id,
                "tenant_id": user.tenant_id,
                "username": user.username,
                "real_name": user.real_name,
                "phone": user.phone,
                "permissions": permissions,
                "park_ids": park_ids,
                "park_scope_mode": park_scope_mode.value,
                "home_path": user.home_path or "/dashboard",
            },
        }

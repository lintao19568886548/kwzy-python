"""Identity 登录与会话应用服务。"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    hash_password,
    password_policy_violation,
    verify_password,
)
from app.modules.identity.infrastructure.authorization_repository import (
    AuthorizationRepository,
)
from app.modules.identity.infrastructure.auth_security_repository import (
    AuthSecurityRepository,
)
from app.modules.identity.infrastructure.identity_admin_repository import (
    IdentityAdminRepository,
)

UTC = timezone.utc


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _security_digest(kind: str, value: str) -> str:
    key = get_settings().jwt_secret.encode("utf-8")
    payload = f"{kind}:{value.strip().lower()}".encode("utf-8")
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


class AuthService:
    """编排租户用户认证、会话与 JWT 签发。"""

    def __init__(self, session: Session) -> None:
        self.auth_repo = AuthorizationRepository(session)
        self.admin_repo = IdentityAdminRepository(session)
        self.security_repo = AuthSecurityRepository(session)

    def login(
        self,
        *,
        username: str,
        password: str,
        tenant_code: str | None = None,
        client_ip: str | None = None,
    ) -> dict:
        subject_digest = _security_digest(
            "login-subject",
            f"{tenant_code or '*'}:{username}",
        )
        client_digest = _security_digest("login-client", client_ip or "unknown")
        settings = get_settings()
        since = datetime.now(UTC).replace(tzinfo=None) - timedelta(
            seconds=settings.auth_login_window_seconds
        )
        subject_failures = self.security_repo.count_recent_subject_failures(
            subject_digest=subject_digest,
            since=since,
        )
        client_failures = self.security_repo.count_recent_client_failures(
            client_digest=client_digest,
            since=since,
        )
        if (
            subject_failures >= settings.auth_login_max_failures
            or client_failures >= settings.auth_login_ip_max_failures
        ):
            self.security_repo.record(
                event_type="LOGIN_RATE_LIMITED",
                subject_digest=subject_digest,
                client_digest=client_digest,
                reason_code="WINDOW_LIMIT",
            )
            self.security_repo.commit()
            raise AppError(
                "登录尝试过于频繁，请稍后重试",
                code="AUTH_RATE_LIMITED",
                status_code=429,
            )

        candidates = self.auth_repo.find_login_candidates(
            username=username,
            tenant_code=tenant_code.strip() if tenant_code else None,
        )
        if not candidates:
            self._record_login_failure(
                subject_digest=subject_digest,
                client_digest=client_digest,
                reason_code="BAD_CREDENTIALS",
            )
            raise AppError("用户名或密码错误", code="AUTH_BAD_PASSWORD", status_code=403)
        if len(candidates) > 1:
            self._record_login_failure(
                subject_digest=subject_digest,
                client_digest=client_digest,
                reason_code="TENANT_AMBIGUOUS",
            )
            raise AppError(
                "该用户名对应多个租户，请指定租户后登录",
                code="AUTH_TENANT_AMBIGUOUS",
                status_code=400,
            )
        user = candidates[0]
        if not verify_password(password, user.password_hash):
            self._record_login_failure(
                subject_digest=subject_digest,
                client_digest=client_digest,
                reason_code="BAD_CREDENTIALS",
                tenant_id=user.tenant_id,
            )
            raise AppError("用户名或密码错误", code="AUTH_BAD_PASSWORD", status_code=403)
        return self._issue_session(user)

    def refresh(self, *, refresh_token: str, client_ip: str | None = None) -> dict:
        token_hash = _hash_token(refresh_token)
        row = self.admin_repo.get_refresh_by_hash_for_update(token_hash)
        if row is None:
            raise AppError("刷新令牌无效", code="AUTH_REFRESH_INVALID", status_code=401)
        if row.revoked_at is not None:
            if row.replaced_by_hash:
                # 已轮换 token 再次出现说明可能被窃取；吊销该用户的整个
                # refresh 会话族。访问令牌由 token_version 单独控制。
                self.admin_repo.revoke_user_refresh(
                    row.user_id, datetime.now(UTC).replace(tzinfo=None)
                )
                self.security_repo.record(
                    event_type="REFRESH_REUSE",
                    tenant_id=row.tenant_id,
                    subject_digest=_security_digest("refresh-user", str(row.user_id)),
                    client_digest=_security_digest(
                        "refresh-client", client_ip or "unknown"
                    ),
                    reason_code="ROTATED_TOKEN_REUSED",
                )
                self.admin_repo.commit()
                raise AppError(
                    "刷新令牌重放，会话已撤销",
                    code="AUTH_REFRESH_REUSED",
                    status_code=401,
                )
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
        result = self._issue_session(user, commit=False)
        row.replaced_by_hash = _hash_token(result["refresh_token"])
        self.admin_repo.commit()
        return result

    def _record_login_failure(
        self,
        *,
        subject_digest: str,
        client_digest: str,
        reason_code: str,
        tenant_id: int | None = None,
    ) -> None:
        self.security_repo.record(
            event_type="LOGIN_FAILURE",
            tenant_id=tenant_id,
            subject_digest=subject_digest,
            client_digest=client_digest,
            reason_code=reason_code,
        )
        self.security_repo.commit()

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
        user = self.admin_repo.get_user(user_id)
        if user is None or user.tenant_id != tenant_id:
            raise AppError("用户不存在", code="AUTH_USER_NOT_FOUND", status_code=404)
        if not verify_password(old_password, user.password_hash):
            raise AppError("原密码错误", code="AUTH_BAD_PASSWORD", status_code=400)
        violation = password_policy_violation(new_password, username=user.username)
        if violation:
            raise AppError(violation, code="AUTH_WEAK_PASSWORD", status_code=400)
        if verify_password(new_password, user.password_hash):
            raise AppError(
                "新密码不能与原密码相同",
                code="AUTH_PASSWORD_REUSE",
                status_code=400,
            )
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

    def _issue_session(self, user, *, commit: bool = True) -> dict:
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
        if commit:
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

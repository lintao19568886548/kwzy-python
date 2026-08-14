"""租户用户管理。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import hash_password, password_policy_violation, verify_password
from app.infrastructure.database.audit import AuditRecorder
from app.modules.identity.application.organization_governance_service import FieldAccessService
from app.modules.identity.infrastructure.identity_admin_repository import (
    IdentityAdminRepository,
)
from app.shared.tenant_context import TenantContext

UTC = timezone.utc


class UserAdminService:
    def __init__(self, session: Session, ctx: TenantContext | None = None) -> None:
        self.ctx = ctx
        self.repo = IdentityAdminRepository(session)
        self.audit = AuditRecorder(session, ctx) if ctx is not None else None
        self.field_access = FieldAccessService(session, ctx) if ctx is not None else None

    def list_users(self, *, tenant_id: int) -> list[dict]:
        rows = [self._to_dict(u) for u in self.repo.list_users(tenant_id)]
        if self.field_access is None:
            return rows
        return self.field_access.project_many("USER", rows)

    def create_user(
        self,
        *,
        tenant_id: int,
        username: str,
        password: str,
        real_name: str = "",
        phone: str | None = None,
        role_ids: list[int] | None = None,
        park_ids: list[int] | None = None,
        all_parks: bool = False,
    ) -> dict:
        username = username.strip()
        if not username or not password:
            raise AppError("账号和密码不能为空", code="USER_INVALID", status_code=400)
        violation = password_policy_violation(password, username=username)
        if violation:
            raise AppError(violation, code="AUTH_WEAK_PASSWORD", status_code=400)
        if self.repo.find_user_id(tenant_id, username):
            raise AppError("账号已存在", code="USER_EXISTS", status_code=409)
        for rid in role_ids or []:
            role = self.repo.get_role(rid)
            if role is None or role.tenant_id != tenant_id:
                raise AppError("角色无效", code="ROLE_NOT_FOUND", status_code=400)
        if all_parks and park_ids:
            raise AppError(
                "全园区与指定园区不能同时设置",
                code="PARK_SCOPE_CONFLICT",
                status_code=400,
            )
        if not self.repo.validate_park_ids(tenant_id, park_ids or []):
            raise AppError("园区范围无效", code="PARK_SCOPE_INVALID", status_code=400)
        try:
            user = self.repo.create_user_entity(
                tenant_id=tenant_id,
                username=username,
                password_hash=hash_password(password),
                real_name=real_name or username,
                phone=phone,
                all_parks=all_parks,
            )
            self.repo.replace_user_roles(tenant_id, user.id, role_ids or [])
            self.repo.replace_user_parks(tenant_id, user.id, park_ids or [])
            if self.audit:
                self.audit.record(
                    action="create",
                    resource_type="IDENTITY_USER",
                    resource_id=user.id,
                    detail={
                        "all_parks": all_parks,
                        "role_count": len(role_ids or []),
                        "park_count": len(park_ids or []),
                    },
                )
            self.repo.commit()
        except IntegrityError as exc:
            self.repo.rollback()
            raise AppError("账号已存在", code="USER_EXISTS", status_code=409) from exc
        self.repo.refresh(user)
        return self._to_dict(user)

    def update_user(
        self,
        *,
        tenant_id: int,
        user_id: int,
        real_name: str | None = None,
        phone: str | None = None,
        status: str | None = None,
        role_ids: list[int] | None = None,
        park_ids: list[int] | None = None,
        all_parks: bool | None = None,
        password: str | None = None,
    ) -> dict:
        user = self.repo.get_user(user_id)
        if user is None or user.tenant_id != tenant_id:
            raise AppError("用户不存在", code="USER_NOT_FOUND", status_code=404)
        invalidate_session = False
        changed_fields: list[str] = []
        if real_name is not None:
            user.real_name = real_name
            changed_fields.append("real_name")
        if phone is not None:
            user.phone = phone
            changed_fields.append("phone")
        if status is not None:
            if status not in {"ACTIVE", "DISABLED"}:
                raise AppError("非法状态", code="USER_INVALID_STATUS", status_code=400)
            if user.status != status:
                user.status = status
                invalidate_session = True
                changed_fields.append("status")
        if all_parks is not None:
            effective_parks = park_ids if park_ids is not None else self.repo.user_park_ids(user.id)
            if all_parks and effective_parks:
                raise AppError(
                    "全园区与指定园区不能同时设置",
                    code="PARK_SCOPE_CONFLICT",
                    status_code=400,
                )
            if bool(user.all_parks) != all_parks:
                user.all_parks = all_parks
                invalidate_session = True
                changed_fields.append("all_parks")
        if password:
            violation = password_policy_violation(password, username=user.username)
            if violation:
                raise AppError(violation, code="AUTH_WEAK_PASSWORD", status_code=400)
            if verify_password(password, user.password_hash):
                raise AppError(
                    "新密码不能与原密码相同",
                    code="AUTH_PASSWORD_REUSE",
                    status_code=400,
                )
            user.password_hash = hash_password(password)
            invalidate_session = True
            changed_fields.append("password")
        if role_ids is not None:
            for rid in role_ids:
                role = self.repo.get_role(rid)
                if role is None or role.tenant_id != tenant_id:
                    raise AppError("角色无效", code="ROLE_NOT_FOUND", status_code=400)
            self.repo.replace_user_roles(tenant_id, user.id, role_ids)
            invalidate_session = True
            changed_fields.append("role_ids")
        if park_ids is not None:
            if (all_parks if all_parks is not None else bool(user.all_parks)) and park_ids:
                raise AppError(
                    "全园区与指定园区不能同时设置",
                    code="PARK_SCOPE_CONFLICT",
                    status_code=400,
                )
            if not self.repo.validate_park_ids(tenant_id, park_ids):
                raise AppError("园区范围无效", code="PARK_SCOPE_INVALID", status_code=400)
            self.repo.replace_user_parks(tenant_id, user.id, park_ids)
            invalidate_session = True
            changed_fields.append("park_ids")
        if invalidate_session:
            self.repo.invalidate_user_sessions(
                [user.id], datetime.now(UTC).replace(tzinfo=None)
            )
        if self.audit:
            self.audit.record(
                action="update",
                resource_type="IDENTITY_USER",
                resource_id=user.id,
                detail={"fields": sorted(set(changed_fields))},
            )
        self.repo.commit()
        self.repo.refresh(user)
        return self._to_dict(user)

    def disable_user(self, *, tenant_id: int, user_id: int) -> dict:
        return self.update_user(tenant_id=tenant_id, user_id=user_id, status="DISABLED")

    def revoke_sessions(self, *, tenant_id: int, user_id: int) -> dict:
        user = self.repo.get_user(user_id)
        if user is None or user.tenant_id != tenant_id:
            raise AppError("用户不存在", code="USER_NOT_FOUND", status_code=404)
        self.repo.invalidate_user_sessions(
            [user.id], datetime.now(UTC).replace(tzinfo=None)
        )
        if self.audit:
            self.audit.record(
                action="revoke_sessions",
                resource_type="IDENTITY_USER",
                resource_id=user.id,
                detail={"reason": "admin_requested"},
            )
        self.repo.commit()
        self.repo.refresh(user)
        return self._to_dict(user)

    def _to_dict(self, user) -> dict:
        return {
            "id": user.id,
            "tenant_id": user.tenant_id,
            "username": user.username,
            "real_name": user.real_name,
            "phone": user.phone,
            "status": user.status,
            "all_parks": bool(user.all_parks),
            "role_ids": self.repo.user_role_ids(user.id),
            "park_ids": self.repo.user_park_ids(user.id),
            "home_path": user.home_path,
        }

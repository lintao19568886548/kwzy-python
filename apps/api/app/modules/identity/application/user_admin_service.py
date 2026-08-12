"""租户用户管理。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import hash_password
from app.modules.identity.infrastructure.identity_admin_repository import (
    IdentityAdminRepository,
)


class UserAdminService:
    def __init__(self, session: Session) -> None:
        self.repo = IdentityAdminRepository(session)

    def list_users(self, *, tenant_id: int) -> list[dict]:
        return [self._to_dict(u) for u in self.repo.list_users(tenant_id)]

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
        if self.repo.find_user_id(tenant_id, username):
            raise AppError("账号已存在", code="USER_EXISTS", status_code=409)
        for rid in role_ids or []:
            role = self.repo.get_role(rid)
            if role is None or role.tenant_id != tenant_id:
                raise AppError("角色无效", code="ROLE_NOT_FOUND", status_code=400)
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
        self.repo.commit()
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
        if real_name is not None:
            user.real_name = real_name
        if phone is not None:
            user.phone = phone
        if status is not None:
            if status not in {"ACTIVE", "DISABLED"}:
                raise AppError("非法状态", code="USER_INVALID_STATUS", status_code=400)
            user.status = status
        if all_parks is not None:
            user.all_parks = all_parks
        if password:
            user.password_hash = hash_password(password)
            user.token_version = int(getattr(user, "token_version", 0) or 0) + 1
        if role_ids is not None:
            for rid in role_ids:
                role = self.repo.get_role(rid)
                if role is None or role.tenant_id != tenant_id:
                    raise AppError("角色无效", code="ROLE_NOT_FOUND", status_code=400)
            self.repo.replace_user_roles(tenant_id, user.id, role_ids)
        if park_ids is not None:
            self.repo.replace_user_parks(tenant_id, user.id, park_ids)
        self.repo.commit()
        self.repo.refresh(user)
        return self._to_dict(user)

    def disable_user(self, *, tenant_id: int, user_id: int) -> dict:
        return self.update_user(tenant_id=tenant_id, user_id=user_id, status="DISABLED")

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

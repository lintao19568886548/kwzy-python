"""Identity admin ORM 访问（infrastructure）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.infrastructure.database.models.identity import (
    Menu,
    Permission,
    RefreshToken,
    Role,
    RoleMenu,
    RoleParkScope,
    RolePermission,
    User,
    UserParkScope,
    UserRole,
)


class IdentityAdminRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # users
    def list_users(self, tenant_id: int) -> list[User]:
        return list(
            self.session.scalars(
                select(User).where(User.tenant_id == tenant_id).order_by(User.id.asc())
            ).all()
        )

    def get_user(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def find_user_id(self, tenant_id: int, username: str) -> int | None:
        return self.session.scalar(
            select(User.id).where(User.tenant_id == tenant_id, User.username == username)
        )

    def add_user(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        return user

    def create_user_entity(
        self,
        *,
        tenant_id: int,
        username: str,
        password_hash: str,
        real_name: str,
        phone: str | None,
        all_parks: bool,
    ) -> User:
        user = User(
            tenant_id=tenant_id,
            username=username,
            password_hash=password_hash,
            real_name=real_name,
            phone=phone,
            status="ACTIVE",
            all_parks=all_parks,
            token_version=0,
        )
        return self.add_user(user)

    def create_role_entity(
        self,
        *,
        tenant_id: int,
        code: str,
        name: str,
        remark: str | None,
        all_parks: bool,
    ) -> Role:
        role = Role(
            tenant_id=tenant_id,
            code=code,
            name=name,
            remark=remark,
            status="ACTIVE",
            all_parks=all_parks,
        )
        return self.add_role(role)

    def create_menu_entity(
        self,
        *,
        tenant_id: int,
        name: str,
        path: str,
        parent_id: int | None,
        component: str | None,
        icon: str | None,
        sort_order: int,
        menu_type: str,
        permission_code: str | None,
    ) -> Menu:
        menu = Menu(
            tenant_id=tenant_id,
            parent_id=parent_id,
            name=name,
            path=path,
            component=component,
            icon=icon,
            sort_order=sort_order,
            menu_type=menu_type,
            status="ACTIVE",
            permission_code=permission_code,
        )
        return self.add_menu(menu)

    def user_role_ids(self, user_id: int) -> list[int]:
        return [int(x) for x in self.session.scalars(select(UserRole.role_id).where(UserRole.user_id == user_id)).all()]

    def user_park_ids(self, user_id: int) -> list[int]:
        return [
            int(x)
            for x in self.session.scalars(
                select(UserParkScope.park_id).where(UserParkScope.user_id == user_id)
            ).all()
        ]

    def replace_user_roles(self, tenant_id: int, user_id: int, role_ids: list[int]) -> None:
        for row in list(self.session.scalars(select(UserRole).where(UserRole.user_id == user_id)).all()):
            self.session.delete(row)
        for rid in role_ids:
            self.session.add(UserRole(tenant_id=tenant_id, user_id=user_id, role_id=rid))

    def replace_user_parks(self, tenant_id: int, user_id: int, park_ids: list[int]) -> None:
        for row in list(
            self.session.scalars(select(UserParkScope).where(UserParkScope.user_id == user_id)).all()
        ):
            self.session.delete(row)
        for pid in park_ids:
            self.session.add(UserParkScope(tenant_id=tenant_id, user_id=user_id, park_id=int(pid)))

    def get_role(self, role_id: int) -> Role | None:
        return self.session.get(Role, role_id)

    def list_roles(self, tenant_id: int) -> list[Role]:
        return list(
            self.session.scalars(
                select(Role).where(Role.tenant_id == tenant_id).order_by(Role.id.asc())
            ).all()
        )

    def find_role_id(self, tenant_id: int, code: str) -> int | None:
        return self.session.scalar(
            select(Role.id).where(Role.tenant_id == tenant_id, Role.code == code)
        )

    def add_role(self, role: Role) -> Role:
        self.session.add(role)
        self.session.flush()
        return role

    def get_permission_by_code(self, code: str) -> Permission | None:
        return self.session.scalar(select(Permission).where(Permission.code == code))

    def list_permissions(self) -> list[Permission]:
        return list(self.session.scalars(select(Permission).order_by(Permission.code)).all())

    def replace_role_permissions(self, tenant_id: int, role_id: int, codes: list[str]) -> None:
        for row in list(
            self.session.scalars(select(RolePermission).where(RolePermission.role_id == role_id)).all()
        ):
            self.session.delete(row)
        for code in codes:
            perm = self.get_permission_by_code(code)
            if perm is None:
                raise KeyError(code)
            self.session.add(
                RolePermission(tenant_id=tenant_id, role_id=role_id, permission_id=perm.id)
            )

    def replace_role_parks(self, tenant_id: int, role_id: int, park_ids: list[int]) -> None:
        for row in list(
            self.session.scalars(select(RoleParkScope).where(RoleParkScope.role_id == role_id)).all()
        ):
            self.session.delete(row)
        for pid in park_ids:
            self.session.add(RoleParkScope(tenant_id=tenant_id, role_id=role_id, park_id=int(pid)))

    def replace_role_menus(self, tenant_id: int, role_id: int, menu_ids: list[int]) -> None:
        for row in list(self.session.scalars(select(RoleMenu).where(RoleMenu.role_id == role_id)).all()):
            self.session.delete(row)
        for mid in menu_ids:
            self.session.add(RoleMenu(tenant_id=tenant_id, role_id=role_id, menu_id=int(mid)))

    def role_permission_codes(self, role_id: int) -> list[str]:
        return [
            str(x)
            for x in self.session.scalars(
                select(Permission.code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == role_id)
            ).all()
        ]

    def role_park_ids(self, role_id: int) -> list[int]:
        return [
            int(x)
            for x in self.session.scalars(
                select(RoleParkScope.park_id).where(RoleParkScope.role_id == role_id)
            ).all()
        ]

    def role_menu_ids(self, role_id: int) -> list[int]:
        return [
            int(x)
            for x in self.session.scalars(select(RoleMenu.menu_id).where(RoleMenu.role_id == role_id)).all()
        ]

    def list_menus(self, tenant_id: int) -> list[Menu]:
        return list(
            self.session.scalars(
                select(Menu)
                .where(Menu.tenant_id == tenant_id)
                .order_by(Menu.sort_order.asc(), Menu.id.asc())
            ).all()
        )

    def get_menu(self, menu_id: int) -> Menu | None:
        return self.session.get(Menu, menu_id)

    def add_menu(self, menu: Menu) -> Menu:
        self.session.add(menu)
        self.session.flush()
        return menu

    def menus_for_role_ids(self, tenant_id: int, role_ids: list[int]) -> list[Menu]:
        if not role_ids:
            return []
        menu_ids = list(
            self.session.scalars(
                select(RoleMenu.menu_id).where(
                    RoleMenu.tenant_id == tenant_id, RoleMenu.role_id.in_(role_ids)
                )
            ).all()
        )
        if not menu_ids:
            return []
        return list(
            self.session.scalars(
                select(Menu)
                .where(
                    Menu.tenant_id == tenant_id,
                    Menu.id.in_(menu_ids),
                    Menu.status == "ACTIVE",
                )
                .order_by(Menu.sort_order.asc(), Menu.id.asc())
            ).all()
        )

    def active_role_ids_for_user(self, tenant_id: int, user_id: int) -> list[int]:
        return [
            int(x)
            for x in self.session.scalars(
                select(UserRole.role_id)
                .join(Role, Role.id == UserRole.role_id)
                .where(
                    UserRole.user_id == user_id,
                    UserRole.tenant_id == tenant_id,
                    Role.status == "ACTIVE",
                )
            ).all()
        ]

    # refresh tokens
    def add_refresh(
        self,
        *,
        tenant_id: int,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
    ) -> None:
        self.session.add(
            RefreshToken(
                tenant_id=tenant_id,
                user_id=user_id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
        )

    def get_refresh_by_hash(self, token_hash: str) -> RefreshToken | None:
        return self.session.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    def revoke_user_refresh(self, user_id: int, when: datetime) -> None:
        self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=when)
        )

    def commit(self) -> None:
        self.session.commit()

    def refresh(self, obj: object) -> None:
        self.session.refresh(obj)

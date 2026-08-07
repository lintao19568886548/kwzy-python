"""Identity models (step1 minimal set)."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import (
    FK_TYPE,
    Base,
    PrimaryKeyMixin,
    TimestampMixin,
)

if TYPE_CHECKING:
    from app.infrastructure.database.models.park_property import Park


class Tenant(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tenants"

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    db_strategy: Mapped[str] = mapped_column(String(32), nullable=False, default="SHARED")
    dedicated_secret_ref: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    users: Mapped[List["User"]] = relationship(back_populates="tenant")
    parks: Mapped[List["Park"]] = relationship(back_populates="tenant")


class User(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "username", name="uk_users_tenant_username"),)

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    real_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    home_path: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    all_parks: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="users")
    park_scopes: Mapped[List["UserParkScope"]] = relationship(back_populates="user")
    role_assignments: Mapped[List["UserRole"]] = relationship(back_populates="user")


class Role(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uk_roles_tenant_code"),)

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    all_parks: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user_assignments: Mapped[List["UserRole"]] = relationship(back_populates="role")
    permission_assignments: Mapped[List["RolePermission"]] = relationship(
        back_populates="role"
    )
    park_scopes: Mapped[List["RoleParkScope"]] = relationship(back_populates="role")


class Permission(Base, PrimaryKeyMixin):
    """全局权限码字典。"""

    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    module: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    role_assignments: Mapped[List["RolePermission"]] = relationship(
        back_populates="permission"
    )


class RolePermission(Base, PrimaryKeyMixin):
    """租户角色与权限码的关联。"""

    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uk_role_perm"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    role_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("roles.id"), nullable=False)
    permission_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("permissions.id"), nullable=False
    )

    role: Mapped["Role"] = relationship(back_populates="permission_assignments")
    permission: Mapped["Permission"] = relationship(back_populates="role_assignments")


class UserRole(Base, PrimaryKeyMixin):
    """租户用户与角色的关联。"""

    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uk_user_role"),)

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=False)
    role_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("roles.id"), nullable=False)

    user: Mapped["User"] = relationship(back_populates="role_assignments")
    role: Mapped["Role"] = relationship(back_populates="user_assignments")


class UserParkScope(Base, PrimaryKeyMixin):
    """User data scope: which parks a user may access."""

    __tablename__ = "user_park_scopes"
    __table_args__ = (UniqueConstraint("user_id", "park_id", name="uk_user_park"),)

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)

    user: Mapped["User"] = relationship(back_populates="park_scopes")


class RoleParkScope(Base, PrimaryKeyMixin):
    """角色可访问的园区范围。"""

    __tablename__ = "role_park_scopes"
    __table_args__ = (UniqueConstraint("role_id", "park_id", name="uk_role_park"),)

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    role_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("roles.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)

    role: Mapped["Role"] = relationship(back_populates="park_scopes")

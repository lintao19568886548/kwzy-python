"""Identity models (step1 minimal set)."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

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


class RefreshToken(Base, PrimaryKeyMixin, TimestampMixin):
    """Hashed refresh tokens (opaque to clients)."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (UniqueConstraint("token_hash", name="uk_refresh_token_hash"),)

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    replaced_by_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


class AuthSecurityEvent(Base, PrimaryKeyMixin, TimestampMixin):
    """Append-only authentication security evidence without raw credentials/PII."""

    __tablename__ = "auth_security_events"

    tenant_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    client_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False, default="")


class VerificationCode(Base, PrimaryKeyMixin, TimestampMixin):
    """Hashed one-time verification code bound to user, tenant and purpose."""

    __tablename__ = "verification_codes"

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=False, index=True
    )
    purpose: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    recipient_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)


class PageAccessProof(Base, PrimaryKeyMixin, TimestampMixin):
    """Short-lived one-time proof produced by successful secondary verification."""

    __tablename__ = "page_access_proofs"
    __table_args__ = (UniqueConstraint("proof_hash", name="uk_page_access_proof_hash"),)

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=False, index=True
    )
    purpose: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    proof_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Menu(Base, PrimaryKeyMixin, TimestampMixin):
    """Tenant navigation menu node."""

    __tablename__ = "menus"

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    parent_id: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("menus.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    component: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    menu_type: Mapped[str] = mapped_column(String(32), nullable=False, default="MENU")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    permission_code: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class RoleMenu(Base, PrimaryKeyMixin):
    """Role to menu grant."""

    __tablename__ = "role_menus"
    __table_args__ = (UniqueConstraint("role_id", "menu_id", name="uk_role_menu"),)

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    role_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("roles.id"), nullable=False)
    menu_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("menus.id"), nullable=False)

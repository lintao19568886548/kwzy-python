"""集团、区域、园区归属、岗位任职与字段访问策略 ORM。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import (
    FK_TYPE,
    Base,
    PrimaryKeyMixin,
    TimestampMixin,
    utc_now,
)


class OrganizationGroup(Base, PrimaryKeyMixin, TimestampMixin):
    """租户内经营集团主档。"""

    __tablename__ = "organization_groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uk_organization_group_code"),
        CheckConstraint(
            "status IN ('ACTIVE', 'DISABLED')",
            name="ck_organization_group_status",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)


class OrganizationRegion(Base, PrimaryKeyMixin, TimestampMixin):
    """集团下的经营区域主档。"""

    __tablename__ = "organization_regions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uk_organization_region_code"),
        CheckConstraint(
            "status IN ('ACTIVE', 'DISABLED')",
            name="ck_organization_region_status",
        ),
        Index("ix_organization_regions_group_sort", "tenant_id", "group_id", "sort_order"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    group_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("organization_groups.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)


class RegionParkAssignment(Base, PrimaryKeyMixin, TimestampMixin):
    """区域与园区的有效期关系；关闭旧关系而非覆盖历史。"""

    __tablename__ = "region_park_assignments"
    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_region_park_effective_range",
        ),
        Index(
            "uk_region_park_current",
            "tenant_id",
            "park_id",
            unique=True,
            postgresql_where=text("effective_to IS NULL"),
            sqlite_where=text("effective_to IS NULL"),
        ),
        Index(
            "ix_region_park_history",
            "tenant_id",
            "park_id",
            "effective_from",
        ),
        Index(
            "ix_region_current_parks",
            "tenant_id",
            "region_id",
            postgresql_where=text("effective_to IS NULL"),
            sqlite_where=text("effective_to IS NULL"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    region_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("organization_regions.id"), nullable=False, index=True
    )
    park_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("parks.id"), nullable=False, index=True
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, default=utc_now
    )
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    assigned_by: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True
    )
    ended_by: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Position(Base, PrimaryKeyMixin, TimestampMixin):
    """岗位主档；任职不隐式授予 RBAC 或园区范围。"""

    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uk_position_code"),
        CheckConstraint("status IN ('ACTIVE', 'DISABLED')", name="ck_position_status"),
        Index("ix_positions_org_sort", "tenant_id", "org_unit_id", "sort_order"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    org_unit_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("org_units.id"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    responsibilities: Mapped[str | None] = mapped_column(Text, nullable=True)


class UserPositionAssignment(Base, PrimaryKeyMixin, TimestampMixin):
    """用户有效期任职；scope_key 仅用于并发唯一性，不参与授权解析。"""

    __tablename__ = "user_position_assignments"
    __table_args__ = (
        CheckConstraint(
            "ends_at IS NULL OR ends_at >= starts_at",
            name="ck_user_position_effective_range",
        ),
        CheckConstraint(
            "scope_key = 'TENANT' OR scope_key LIKE 'PARK:%'",
            name="ck_user_position_scope_key",
        ),
        Index(
            "uk_user_position_current",
            "tenant_id",
            "user_id",
            "position_id",
            "scope_key",
            unique=True,
            postgresql_where=text("ends_at IS NULL"),
            sqlite_where=text("ends_at IS NULL"),
        ),
        Index(
            "uk_user_primary_position_current",
            "tenant_id",
            "user_id",
            unique=True,
            postgresql_where=text("ends_at IS NULL AND is_primary = true"),
            sqlite_where=text("ends_at IS NULL AND is_primary = 1"),
        ),
        Index(
            "ix_user_position_history",
            "tenant_id",
            "user_id",
            "starts_at",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=False, index=True
    )
    position_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("positions.id"), nullable=False, index=True
    )
    park_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("parks.id"), nullable=True, index=True
    )
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False, default="TENANT")
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, default=utc_now
    )
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    assigned_by: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True
    )
    ended_by: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True
    )
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)


class FieldAccessPolicy(Base, PrimaryKeyMixin, TimestampMixin):
    """同租户角色对受保护资源字段的服务端投影策略。"""

    __tablename__ = "field_access_policies"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "role_id",
            "resource_type",
            "field_name",
            name="uk_field_access_policy",
        ),
        CheckConstraint(
            "access_mode IN ('VISIBLE', 'MASKED', 'HIDDEN')",
            name="ck_field_access_mode",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'DISABLED')",
            name="ck_field_access_policy_status",
        ),
        Index(
            "ix_field_access_policy_resolve",
            "tenant_id",
            "role_id",
            "resource_type",
            "status",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    role_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("roles.id"), nullable=False, index=True
    )
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    access_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    mask_strategy: Mapped[str] = mapped_column(String(32), nullable=False, default="PHONE")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")

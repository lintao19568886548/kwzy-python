"""Park / Building / Unit models (step1 core space)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, List, Optional
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import (
    FK_TYPE,
    Base,
    PrimaryKeyMixin,
    SoftDeleteMixin,
    TimestampMixin,
)

if TYPE_CHECKING:
    from app.infrastructure.database.models.identity import Tenant


class Park(Base, PrimaryKeyMixin, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "parks"
    __table_args__ = (UniqueConstraint("tenant_id", "id", name="uk_parks_tenant_id_id"),)

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    area: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    contact: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    manager: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")

    tenant: Mapped["Tenant"] = relationship(back_populates="parks")
    buildings: Mapped[List["Building"]] = relationship(back_populates="park")
    units: Mapped[List["Unit"]] = relationship(back_populates="park")


class Building(Base, PrimaryKeyMixin, SoftDeleteMixin, TimestampMixin):
    """Typed spatial node; physical table name stays compatible with step1."""

    __tablename__ = "buildings"
    __table_args__ = (
        Index(
            "uk_spatial_root_code",
            "tenant_id",
            "park_id",
            "code",
            unique=True,
            postgresql_where=text("parent_id IS NULL AND is_deleted = false"),
            sqlite_where=text("parent_id IS NULL AND is_deleted = 0"),
        ),
        Index(
            "uk_spatial_child_code",
            "tenant_id",
            "park_id",
            "parent_id",
            "code",
            unique=True,
            postgresql_where=text("parent_id IS NOT NULL AND is_deleted = false"),
            sqlite_where=text("parent_id IS NOT NULL AND is_deleted = 0"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False, index=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("buildings.id"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    node_type: Mapped[str] = mapped_column(String(32), nullable=False, default="BUILDING")
    building_type: Mapped[str] = mapped_column(String(32), nullable=False, default="FACTORY")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    address: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attributes_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    geometry_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    geometry_type: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    coordinate_reference: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    geometry_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    park: Mapped["Park"] = relationship(back_populates="buildings")
    units: Mapped[List["Unit"]] = relationship(back_populates="building")


class Unit(Base, PrimaryKeyMixin, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "units"
    __table_args__ = (
        UniqueConstraint(
            "building_id",
            "code",
            "version_no",
            name="uk_units_space_code_version",
        ),
        UniqueConstraint("tenant_id", "id", name="uk_units_tenant_id_id"),
        UniqueConstraint("tenant_id", "park_id", "id", name="uk_units_tenant_park_id"),
        Index(
            "uk_units_current_space_code",
            "building_id",
            "code",
            unique=True,
            postgresql_where=text("valid_to IS NULL AND is_deleted = false"),
            sqlite_where=text("valid_to IS NULL AND is_deleted = 0"),
        ),
        Index("ix_units_logical_version", "logical_id", "version_no"),
        ForeignKeyConstraint(
            ["tenant_id", "asset_template_version_id"],
            ["asset_template_versions.tenant_id", "asset_template_versions.id"],
            name="fk_units_tenant_asset_template_version",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False, index=True)
    building_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("buildings.id"), nullable=False, index=True
    )
    logical_id: Mapped[str] = mapped_column(
        String(36), nullable=False, default=lambda: str(uuid4()), index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, default=datetime.utcnow
    )
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    supersedes_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("units.id"), nullable=True, index=True
    )
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    usage_type: Mapped[str] = mapped_column(String(32), nullable=False, default="FACTORY")
    billing_unit: Mapped[str] = mapped_column(String(16), nullable=False, default="SQM")
    available_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    rentable_area: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )
    used_area: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )
    base_rent_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="VACANT")
    attributes_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    asset_template_version_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, nullable=True, index=True
    )

    park: Mapped["Park"] = relationship(back_populates="units")
    building: Mapped["Building"] = relationship(back_populates="units")


class UnitLineage(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "unit_lineages"
    __table_args__ = (
        UniqueConstraint(
            "operation_id",
            "source_unit_id",
            "target_unit_id",
            name="uk_unit_lineage_edge",
        ),
        Index("ix_unit_lineages_operation", "tenant_id", "operation_id"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("parks.id"), nullable=False, index=True
    )
    operation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_unit_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("units.id"), nullable=False, index=True
    )
    target_unit_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("units.id"), nullable=False, index=True
    )


class AssetTemplate(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "asset_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uk_asset_template_code"),
        UniqueConstraint("tenant_id", "id", name="uk_asset_template_tenant_id_id"),
        CheckConstraint("status IN ('ACTIVE','RETIRED')", name="ck_asset_template_status"),
        CheckConstraint("current_version >= 0", name="ck_asset_template_current_version"),
        CheckConstraint("lock_version > 0", name="ck_asset_template_lock_version"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)


class AssetTemplateVersion(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "asset_template_versions"
    __table_args__ = (
        UniqueConstraint("template_id", "version", name="uk_asset_template_version"),
        UniqueConstraint(
            "tenant_id", "id", name="uk_asset_template_version_tenant_id_id"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "template_id"],
            ["asset_templates.tenant_id", "asset_templates.id"],
            name="fk_asset_template_versions_tenant_template",
        ),
        CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','RETIRED')",
            name="ck_asset_template_version_status",
        ),
        CheckConstraint("version > 0", name="ck_asset_template_version_positive"),
        Index(
            "uk_asset_template_one_draft",
            "template_id",
            unique=True,
            postgresql_where=text("status = 'DRAFT'"),
            sqlite_where=text("status = 'DRAFT'"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    template_id: Mapped[int] = mapped_column(
        FK_TYPE, nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    field_schema_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    defaults_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    schema_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    published_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)

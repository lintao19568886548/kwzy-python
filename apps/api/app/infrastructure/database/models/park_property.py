"""Park / Building / Unit models (step1 core space)."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any, List, Optional

from sqlalchemy import JSON, ForeignKey, Numeric, String, Text, UniqueConstraint
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
    """Supporting aggregate for Unit FK (step1 minimal)."""

    __tablename__ = "buildings"

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    building_type: Mapped[str] = mapped_column(String(32), nullable=False, default="FACTORY")
    address: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    park: Mapped["Park"] = relationship(back_populates="buildings")
    units: Mapped[List["Unit"]] = relationship(back_populates="building")


class Unit(Base, PrimaryKeyMixin, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "units"
    __table_args__ = (UniqueConstraint("building_id", "code", name="uk_units_building_code"),)

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False, index=True)
    building_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("buildings.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
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

    park: Mapped["Park"] = relationship(back_populates="units")
    building: Mapped["Building"] = relationship(back_populates="units")

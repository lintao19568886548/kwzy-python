"""功能说明：
    Lease ORM 模型（合同、占用行、条款）。

业务职责：
    Infrastructure 持久化；无业务权限逻辑。
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import (
    FK_TYPE,
    Base,
    PrimaryKeyMixin,
    TimestampMixin,
)


class LeaseContract(Base, PrimaryKeyMixin, TimestampMixin):
    """功能说明：
        租赁合同表 lease_contracts。

    业务职责：
        ORM；tenant + park + party 关联。
    """

    __tablename__ = "lease_contracts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "contract_no", name="uk_lease_contract_no"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    party_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parties.id"), nullable=False)
    contract_no: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    increase_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    increase_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    deposit_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0")
    )
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, nullable=True)


class LeaseContractUnit(Base, PrimaryKeyMixin):
    """功能说明：
        合同占用单元表 lease_contract_units。
    """

    __tablename__ = "lease_contract_units"
    __table_args__ = (
        UniqueConstraint("contract_id", "unit_id", name="uk_lcu_contract_unit"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    contract_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("lease_contracts.id"), nullable=False
    )
    unit_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("units.id"), nullable=False)
    occupied_area: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )
    unit_rent_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )


class LeaseTerm(Base, PrimaryKeyMixin):
    """功能说明：
        合同条款表 lease_terms。
    """

    __tablename__ = "lease_terms"

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    contract_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("lease_contracts.id"), nullable=False
    )
    term_type: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

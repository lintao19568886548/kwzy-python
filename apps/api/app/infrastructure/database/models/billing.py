"""功能说明：Billing ORM。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, TimestampMixin


class FeeCatalog(Base, PrimaryKeyMixin):
    __tablename__ = "fee_catalog"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uk_fee_code"),)

    tenant_id: Mapped[Optional[int]] = mapped_column(FK_TYPE, nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Bill(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "bills"
    __table_args__ = (UniqueConstraint("tenant_id", "bill_no", name="uk_bills_no"),)

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    party_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parties.id"), nullable=False)
    contract_id: Mapped[Optional[int]] = mapped_column(
        FK_TYPE, ForeignKey("lease_contracts.id"), nullable=True
    )
    bill_no: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    project_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    overdue_since: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="MANUAL")
    source_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(FK_TYPE, nullable=True)


class BillLine(Base, PrimaryKeyMixin):
    __tablename__ = "bill_lines"

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True)
    bill_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("bills.id"), nullable=False)
    fee_code: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("0"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False, default=Decimal("0"))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    meter_reading_from: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    meter_reading_to: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    multiplier: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

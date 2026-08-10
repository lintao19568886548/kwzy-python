"""功能说明：收款登记 ORM。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, TimestampMixin


class Payment(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("tenant_id", "payment_no", name="uk_payments_no"),)

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    party_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parties.id"), nullable=False)
    payment_no: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(32), nullable=False, default="TRANSFER")
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="CONFIRMED")
    operator_id: Mapped[Optional[int]] = mapped_column(FK_TYPE, nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class PaymentAllocation(Base, PrimaryKeyMixin):
    __tablename__ = "payment_allocations"

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True)
    payment_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("payments.id"), nullable=False)
    bill_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("bills.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

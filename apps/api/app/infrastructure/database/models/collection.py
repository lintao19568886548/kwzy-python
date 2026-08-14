"""功能说明：收款登记 ORM。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, TimestampMixin


class Payment(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "payment_no", name="uk_payments_no"),
        UniqueConstraint("tenant_id", "id", name="uk_payments_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_payments_tenant_park",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_payments_tenant_party",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "source_receipt_id"],
            ["receipt_transactions.tenant_id", "receipt_transactions.id"],
            name="fk_payments_tenant_source_receipt",
            use_alter=True,
            ondelete="RESTRICT",
        ),
        Index(
            "uk_payments_source_receipt",
            "tenant_id",
            "source_receipt_id",
            unique=True,
            postgresql_where=text("source_receipt_id IS NOT NULL"),
            sqlite_where=text("source_receipt_id IS NOT NULL"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    party_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parties.id"), nullable=False)
    payment_no: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(32), nullable=False, default="TRANSFER")
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="CONFIRMED")
    source_receipt_id: Mapped[int | None] = mapped_column(
        FK_TYPE,
        ForeignKey(
            "receipt_transactions.id",
            name="fk_payment_source_receipt",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        nullable=True,
    )
    operator_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)


class PaymentAllocation(Base, PrimaryKeyMixin):
    __tablename__ = "payment_allocations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "payment_id"],
            ["payments.tenant_id", "payments.id"],
            name="fk_payment_allocations_tenant_payment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "bill_id"],
            ["bills.tenant_id", "bills.id"],
            name="fk_payment_allocations_tenant_bill",
            ondelete="RESTRICT",
        ),
        Index("idx_pa_payment", "payment_id"),
        Index("idx_pa_bill", "bill_id"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    payment_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("payments.id"), nullable=False)
    bill_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("bills.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    allocation_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

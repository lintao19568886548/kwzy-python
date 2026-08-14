"""功能说明：Billing ORM。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
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
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, TimestampMixin


class FeeCatalog(Base, PrimaryKeyMixin):
    __tablename__ = "fee_catalog"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uk_fee_code"),)

    tenant_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Bill(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "bills"
    __table_args__ = (
        UniqueConstraint("tenant_id", "bill_no", name="uk_bills_no"),
        UniqueConstraint("tenant_id", "id", name="uk_bills_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_bills_tenant_park",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_bills_tenant_party",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "waiver_amount >= 0 AND bad_debt_amount >= 0 "
            "AND waiver_amount + bad_debt_amount <= total_amount",
            name="ck_bills_receivable_treatments",
        ),
        CheckConstraint("lock_version > 0", name="ck_bills_lock_version"),
        Index("idx_bills_park_status", "tenant_id", "park_id", "status"),
        Index("idx_bills_party_period", "tenant_id", "party_id", "period_start", "period_end"),
        Index("ix_bills_aging", "tenant_id", "park_id", "status", "due_date"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    party_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parties.id"), nullable=False)
    contract_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("lease_contracts.id"), nullable=True
    )
    bill_no: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(128), nullable=True)
    project_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    overdue_since: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal(0)
    )
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal(0))
    waiver_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal(0), server_default="0"
    )
    bad_debt_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal(0), server_default="0"
    )
    deferred_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    collection_hold: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    dispute_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="NONE", server_default="NONE"
    )
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="MANUAL")
    source_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)


class BillLine(Base, PrimaryKeyMixin):
    __tablename__ = "bill_lines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "bill_id"],
            ["bills.tenant_id", "bills.id"],
            name="fk_bill_lines_tenant_bill",
            ondelete="RESTRICT",
        ),
        Index("idx_bill_lines_bill", "bill_id"),
        Index(
            "uk_bill_lines_source_schedule",
            "tenant_id",
            "source_schedule_id",
            unique=True,
            postgresql_where=text("source_schedule_id IS NOT NULL"),
            sqlite_where=text("source_schedule_id IS NOT NULL"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    bill_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("bills.id"), nullable=False)
    source_schedule_id: Mapped[int | None] = mapped_column(
        FK_TYPE,
        ForeignKey(
            "lease_performance_schedules.id",
            name="fk_bill_line_source_schedule",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    fee_code: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal(0))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False, default=Decimal(0))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal(0))
    meter_reading_from: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    meter_reading_to: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    multiplier: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

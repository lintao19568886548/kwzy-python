"""功能说明：催缴案件 ORM（最小可运行）。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
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
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, TimestampMixin


class CollectionCase(Base, PrimaryKeyMixin, TimestampMixin):
    """催缴案件（过程记录，不替代 Payment）。"""

    __tablename__ = "collection_cases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uk_collection_cases_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_collection_cases_tenant_park",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_collection_cases_tenant_party",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "bill_id"],
            ["bills.tenant_id", "bills.id"],
            name="fk_collection_cases_tenant_bill",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("tenant_id", "active_bill_key", name="uk_collection_case_active_bill_key"),
        Index("ix_collection_case_aging", "tenant_id", "park_id", "status", "level"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("parks.id"), nullable=False, index=True
    )
    party_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("parties.id"), nullable=False, index=True
    )
    bill_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("bills.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN", index=True)
    # New writes set this to the decimal bill id while active and clear it on close.
    # Legacy rows remain NULL so migration never guesses which historical case to close.
    active_bill_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="L1")
    assignee_user_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True
    )
    amount_snapshot: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal(0), server_default="0"
    )
    overdue_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    effective_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    strategy_code: Mapped[str] = mapped_column(
        String(32), nullable=False, default="AGING_V1", server_default="AGING_V1"
    )
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    resolution_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

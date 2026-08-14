"""Tenant-safe receipt matching, dunning history and receivable treatments."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
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
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, TimestampMixin


class ReceiptTransaction(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "receipt_transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_receipt_amount_positive"),
        CheckConstraint(
            "status IN ('PENDING','SUGGESTED','EXCEPTION','DISPUTED','CONFIRMED','REJECTED')",
            name="ck_receipt_status",
        ),
        CheckConstraint("lock_version > 0", name="ck_receipt_lock_version"),
        UniqueConstraint("tenant_id", "source_provider", "source_ref", name="uk_receipt_source"),
        UniqueConstraint("tenant_id", "id", name="uk_receipts_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_receipts_tenant_park",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_receipts_tenant_party",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "payment_id"],
            ["payments.tenant_id", "payments.id"],
            name="fk_receipts_tenant_payment",
            use_alter=True,
            ondelete="RESTRICT",
        ),
        Index("ix_receipt_inbox", "tenant_id", "park_id", "status", "received_at"),
        Index("ix_receipt_party", "tenant_id", "party_id", "received_at"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    party_id: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("parties.id"), nullable=True)
    transaction_no: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    received_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    source_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    payer_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payer_account_masked: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bank_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    purpose: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="PENDING", server_default="PENDING"
    )
    exception_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_remark: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    dispute_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    dispute_resolution: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dispute_reviewed_by: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True
    )
    dispute_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    payment_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("payments.id"), nullable=True
    )
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)


class ReceiptMatchCandidate(Base, PrimaryKeyMixin):
    __tablename__ = "receipt_match_candidates"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_receipt_candidate_score"),
        CheckConstraint("proposed_amount > 0", name="ck_receipt_candidate_amount"),
        ForeignKeyConstraint(
            ["tenant_id", "receipt_id"],
            ["receipt_transactions.tenant_id", "receipt_transactions.id"],
            name="fk_receipt_candidate_tenant_receipt",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "bill_id"],
            ["bills.tenant_id", "bills.id"],
            name="fk_receipt_candidate_tenant_bill",
        ),
        UniqueConstraint("tenant_id", "receipt_id", "bill_id", name="uk_receipt_candidate_bill"),
        Index("ix_receipt_candidate_rank", "tenant_id", "receipt_id", "rank"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    receipt_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    bill_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    proposed_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    rule_codes_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)


class CollectionRecord(Base, PrimaryKeyMixin):
    __tablename__ = "collection_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["collection_cases.tenant_id", "collection_cases.id"],
            name="fk_collection_record_tenant_case",
        ),
        Index(
            "uk_collection_record_source",
            "tenant_id",
            "source_ref",
            unique=True,
            postgresql_where=text("source_ref IS NOT NULL"),
            sqlite_where=text("source_ref IS NOT NULL"),
        ),
        Index("ix_collection_record_case_time", "tenant_id", "case_id", "created_at"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    case_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    action_type: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    channel: Mapped[str | None] = mapped_column(String(24), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    external_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)


class DunningRun(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "dunning_runs"
    __table_args__ = (
        CheckConstraint("mode IN ('PREVIEW','APPLY')", name="ck_dunning_run_mode"),
        CheckConstraint("status IN ('RUNNING','COMPLETED','FAILED')", name="ck_dunning_run_status"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_dunning_runs_tenant_park",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("tenant_id", "run_key", name="uk_dunning_run_key"),
        Index("ix_dunning_run_scope", "tenant_id", "park_id", "as_of"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=True)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    mode: Mapped[str] = mapped_column(String(8), nullable=False)
    run_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="RUNNING")
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)


class ReceivableAdjustment(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "receivable_adjustments"
    __table_args__ = (
        CheckConstraint(
            "adjustment_type IN ('WAIVER','EXTENSION','BAD_DEBT','DISPUTE','DISPUTE_RESOLUTION')",
            name="ck_receivable_adjustment_type",
        ),
        CheckConstraint(
            "status IN ('PENDING_APPROVAL','APPROVED','REJECTED','APPLIED','WITHDRAWN')",
            name="ck_receivable_adjustment_status",
        ),
        CheckConstraint("amount IS NULL OR amount > 0", name="ck_receivable_adjustment_amount"),
        CheckConstraint("lock_version > 0", name="ck_receivable_adjustment_lock_version"),
        ForeignKeyConstraint(
            ["tenant_id", "bill_id"],
            ["bills.tenant_id", "bills.id"],
            name="fk_receivable_adjustment_tenant_bill",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_receivable_adjustments_tenant_park",
            ondelete="RESTRICT",
        ),
        Index("ix_receivable_adjustment_bill", "tenant_id", "bill_id", "status"),
        Index(
            "uk_receivable_adjustment_request_key",
            "tenant_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
            sqlite_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    bill_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    adjustment_type: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    requested_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="PENDING_APPROVAL", server_default="PENDING_APPROVAL"
    )
    bill_lock_version_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    open_amount_snapshot: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    approval_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("approval_requests.id"), nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    requested_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    applied_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

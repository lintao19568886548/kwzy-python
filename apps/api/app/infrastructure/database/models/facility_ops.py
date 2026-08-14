"""功能说明：运维工单 ORM。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
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


class WorkOrder(Base, PrimaryKeyMixin, TimestampMixin):
    """园区运维工单。"""

    __tablename__ = "work_orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('SUBMITTED','ASSIGNED','IN_PROGRESS','WAITING_QUOTE_APPROVAL',"
            "'IN_PROGRESS_AFTER_QUOTE','WAITING_ACCEPTANCE','COMPLETED','CANCELLED')",
            name="ck_work_orders_status_v2",
        ),
        CheckConstraint(
            "priority IN ('LOW','MEDIUM','HIGH','URGENT')",
            name="ck_work_orders_priority_v2",
        ),
        CheckConstraint("lock_version > 0", name="ck_work_orders_lock_version_v2"),
        UniqueConstraint("tenant_id", "id", name="uk_work_orders_tenant_id_id"),
        UniqueConstraint(
            "tenant_id", "park_id", "id", name="uk_work_orders_tenant_park_id"
        ),
        UniqueConstraint("tenant_id", "order_no", name="uk_work_orders_tenant_order_no"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_work_orders_tenant_park_v2",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_work_orders_tenant_party_v2",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "assignee_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_work_orders_tenant_assignee_v2",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reporter_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_work_orders_tenant_reporter_v2",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "party_id", "contact_id"],
            ["party_contacts.tenant_id", "party_contacts.party_id", "party_contacts.id"],
            name="fk_work_orders_tenant_party_contact_v2",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["units.tenant_id", "units.id"],
            name="fk_work_orders_tenant_unit_v2",
            ondelete="RESTRICT",
        ),
        Index(
            "uk_work_orders_source_v2",
            "tenant_id",
            "source_type",
            "source_id",
            unique=True,
            postgresql_where=text("source_id <> ''"),
            sqlite_where=text("source_id <> ''"),
        ),
        Index("ix_work_orders_service_queue_v2", "tenant_id", "park_id", "status", "priority"),
        Index("ix_work_orders_party_v2", "tenant_id", "party_id", "created_at"),
        Index("ix_work_orders_sla_v2", "tenant_id", "status", "response_due_at", "resolution_due_at"),
    )

    tenant_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("tenants.id"), nullable=False, index=True
    )
    park_id: Mapped[int] = mapped_column(
        FK_TYPE, ForeignKey("parks.id"), nullable=False, index=True
    )
    order_no: Mapped[str] = mapped_column(String(64), nullable=False)
    party_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("parties.id"), nullable=True
    )
    contact_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("party_contacts.id"), nullable=True
    )
    contact_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contact_phone_masked: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="GENERAL")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="MEDIUM")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="SUBMITTED", server_default="SUBMITTED", index=True
    )
    reporter_user_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True
    )
    assignee_user_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True, index=True
    )
    unit_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("units.id"), nullable=True
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="MANUAL")
    source_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    quote_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    assignment_rule_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    assignment_rule_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolution_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted_for_acceptance_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolution_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    no_evidence_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )


class TenantServicePrincipal(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tenant_service_principals"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','DISABLED')", name="ck_tenant_service_principal_status"),
        UniqueConstraint("tenant_id", "user_id", name="uk_tenant_service_principal_user"),
        UniqueConstraint("tenant_id", "id", name="uk_tenant_service_principal_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_tenant_service_principal_user",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_tenant_service_principal_party",
        ),
        Index("ix_tenant_service_principal_party", "tenant_id", "party_id", "status"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=False)
    party_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parties.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    disabled_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TenantServicePrincipalPark(Base, PrimaryKeyMixin):
    __tablename__ = "tenant_service_principal_parks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "principal_id", "park_id", name="uk_tenant_service_principal_park"),
        ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["tenant_service_principals.tenant_id", "tenant_service_principals.id"],
            name="fk_tenant_service_principal_park_principal",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_tenant_service_principal_park_park",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    principal_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)


class WorkOrderAssignmentRule(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "work_order_assignment_rules"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT','PUBLISHED','RETIRED')", name="ck_work_order_rule_status"),
        CheckConstraint("response_minutes > 0", name="ck_work_order_rule_response_minutes"),
        CheckConstraint("resolution_minutes > 0", name="ck_work_order_rule_resolution_minutes"),
        CheckConstraint("sort_order >= 0", name="ck_work_order_rule_sort_order"),
        UniqueConstraint("tenant_id", "code", "version_no", name="uk_work_order_rule_version"),
        UniqueConstraint("tenant_id", "id", name="uk_work_order_rules_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_work_order_rule_park",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "assignee_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_work_order_rule_assignee",
        ),
        Index(
            "uk_work_order_rule_published",
            "tenant_id",
            "code",
            unique=True,
            postgresql_where=text("status = 'PUBLISHED'"),
            sqlite_where=text("status = 'PUBLISHED'"),
        ),
        Index("ix_work_order_rule_match", "tenant_id", "status", "park_id", "category", "priority", "sort_order"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    park_id: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(16), nullable=True)
    assignee_user_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=False)
    response_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    published_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    retired_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class WorkOrderEvent(Base, PrimaryKeyMixin):
    __tablename__ = "work_order_events"
    __table_args__ = (
        CheckConstraint("actor_type IN ('STAFF','TENANT','SYSTEM','MIGRATION')", name="ck_work_order_event_actor_type"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "work_order_id"],
            ["work_orders.tenant_id", "work_orders.park_id", "work_orders.id"],
            name="fk_work_order_event_order",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_work_order_event_key"),
        Index("ix_work_order_event_timeline", "tenant_id", "work_order_id", "occurred_at"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    work_order_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    detail_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class WorkOrderQuote(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "work_order_quotes"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT','SUBMITTED','ACCEPTED','REJECTED')", name="ck_work_order_quote_status"),
        CheckConstraint("total_amount >= 0", name="ck_work_order_quote_total"),
        CheckConstraint("lock_version > 0", name="ck_work_order_quote_lock_version"),
        UniqueConstraint("tenant_id", "work_order_id", "version_no", name="uk_work_order_quote_version"),
        UniqueConstraint("tenant_id", "id", name="uk_work_order_quotes_tenant_id_id"),
        UniqueConstraint("tenant_id", "decision_key", name="uk_work_order_quote_decision_key"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "work_order_id"],
            ["work_orders.tenant_id", "work_orders.park_id", "work_orders.id"],
            name="fk_work_order_quote_order",
        ),
        Index("ix_work_order_quote_status", "tenant_id", "work_order_id", "status"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    work_order_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal(0))
    remark: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    submitted_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_by_user_id: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    decided_by_party_id: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("parties.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decision_remark: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    decision_key: Mapped[str | None] = mapped_column(String(128), nullable=True)


class WorkOrderQuoteLine(Base, PrimaryKeyMixin):
    __tablename__ = "work_order_quote_lines"
    __table_args__ = (
        CheckConstraint("line_type IN ('LABOR','MATERIAL','OUTSOURCE','OTHER')", name="ck_work_order_quote_line_type"),
        CheckConstraint("quantity > 0", name="ck_work_order_quote_line_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_work_order_quote_line_price"),
        CheckConstraint("amount >= 0", name="ck_work_order_quote_line_amount"),
        ForeignKeyConstraint(
            ["tenant_id", "quote_id"],
            ["work_order_quotes.tenant_id", "work_order_quotes.id"],
            name="fk_work_order_quote_line_quote",
        ),
        Index("ix_work_order_quote_line_quote", "tenant_id", "quote_id", "id"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    quote_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    line_type: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)


class WorkOrderCostEntry(Base, PrimaryKeyMixin):
    __tablename__ = "work_order_cost_entries"
    __table_args__ = (
        CheckConstraint("entry_type IN ('LABOR','MATERIAL','OUTSOURCE','OTHER')", name="ck_work_order_cost_type"),
        CheckConstraint("quantity > 0", name="ck_work_order_cost_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_work_order_cost_price"),
        CheckConstraint("amount <> 0", name="ck_work_order_cost_amount"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "work_order_id"],
            ["work_orders.tenant_id", "work_orders.park_id", "work_orders.id"],
            name="fk_work_order_cost_order",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reverses_entry_id"],
            ["work_order_cost_entries.tenant_id", "work_order_cost_entries.id"],
            name="fk_work_order_cost_reversal",
        ),
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_work_order_cost_key"),
        UniqueConstraint("tenant_id", "id", name="uk_work_order_cost_tenant_id_id"),
        Index("ix_work_order_cost_order", "tenant_id", "work_order_id", "occurred_at"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    work_order_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    entry_type: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reverses_entry_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class WorkOrderAcceptance(Base, PrimaryKeyMixin):
    __tablename__ = "work_order_acceptances"
    __table_args__ = (
        CheckConstraint("decision IN ('ACCEPTED','REWORK')", name="ck_work_order_acceptance_decision"),
        UniqueConstraint("tenant_id", "work_order_id", "attempt_no", name="uk_work_order_acceptance_attempt"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_work_order_acceptance_key"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "work_order_id"],
            ["work_orders.tenant_id", "work_orders.park_id", "work_orders.id"],
            name="fk_work_order_acceptance_order",
        ),
        Index("ix_work_order_acceptance_order", "tenant_id", "work_order_id", "attempt_no"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    work_order_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    actor_party_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parties.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class WorkOrderRating(Base, PrimaryKeyMixin):
    __tablename__ = "work_order_ratings"
    __table_args__ = (
        CheckConstraint("score >= 1 AND score <= 5", name="ck_work_order_rating_score"),
        UniqueConstraint("tenant_id", "work_order_id", name="uk_work_order_rating_order"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_work_order_rating_key"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id", "work_order_id"],
            ["work_orders.tenant_id", "work_orders.park_id", "work_orders.id"],
            name="fk_work_order_rating_order",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parks.id"), nullable=False)
    work_order_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    tags_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    actor_party_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("parties.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

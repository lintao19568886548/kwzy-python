"""receivables matching allocation dunning and adjustment lifecycle

Revision ID: u7d35f0a2b19
Revises: t6c24e9f1a08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "u7d35f0a2b19"
down_revision: str | None = "t6c24e9f1a08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
FK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def upgrade() -> None:
    with op.batch_alter_table("bills") as batch:
        batch.add_column(
            sa.Column("waiver_amount", sa.Numeric(14, 2), server_default="0", nullable=False)
        )
        batch.add_column(
            sa.Column("bad_debt_amount", sa.Numeric(14, 2), server_default="0", nullable=False)
        )
        batch.add_column(sa.Column("deferred_due_date", sa.Date(), nullable=True))
        batch.add_column(
            sa.Column("collection_hold", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch.add_column(
            sa.Column("dispute_status", sa.String(16), server_default="NONE", nullable=False)
        )
        batch.add_column(sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False))
        batch.create_unique_constraint("uk_bills_tenant_id_id", ["tenant_id", "id"])
        batch.create_check_constraint(
            "ck_bills_receivable_treatments",
            "waiver_amount >= 0 AND bad_debt_amount >= 0 "
            "AND waiver_amount + bad_debt_amount <= total_amount",
        )
        batch.create_check_constraint("ck_bills_lock_version", "lock_version > 0")
    op.create_index(
        "ix_bills_aging", "bills", ["tenant_id", "park_id", "status", "due_date"]
    )

    with op.batch_alter_table("lease_performance_schedules") as batch:
        batch.add_column(sa.Column("bill_id", FK_TYPE, nullable=True))
        batch.add_column(sa.Column("billed_at", sa.DateTime(), nullable=True))
        batch.create_foreign_key(
            "fk_lease_schedule_bill", "bills", ["bill_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_unique_constraint(
            "uk_lease_schedules_tenant_id_id", ["tenant_id", "id"]
        )

    with op.batch_alter_table("bill_lines") as batch:
        batch.add_column(sa.Column("source_schedule_id", FK_TYPE, nullable=True))
        batch.create_foreign_key(
            "fk_bill_line_source_schedule",
            "lease_performance_schedules",
            ["source_schedule_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    op.create_index(
        "uk_bill_lines_source_schedule",
        "bill_lines",
        ["tenant_id", "source_schedule_id"],
        unique=True,
        postgresql_where=sa.text("source_schedule_id IS NOT NULL"),
        sqlite_where=sa.text("source_schedule_id IS NOT NULL"),
    )

    with op.batch_alter_table("payments") as batch:
        batch.create_unique_constraint("uk_payments_tenant_id_id", ["tenant_id", "id"])

    op.create_table(
        "receipt_transactions",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("party_id", FK_TYPE, nullable=True),
        sa.Column("transaction_no", sa.String(64), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="CNY", nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("source_provider", sa.String(64), nullable=False),
        sa.Column("source_ref", sa.String(128), nullable=False),
        sa.Column("payer_name", sa.String(128), nullable=True),
        sa.Column("payer_account_masked", sa.String(64), nullable=True),
        sa.Column("bank_reference", sa.String(128), nullable=True),
        sa.Column("purpose", sa.String(512), nullable=True),
        sa.Column("status", sa.String(16), server_default="PENDING", nullable=False),
        sa.Column("exception_code", sa.String(64), nullable=True),
        sa.Column("review_remark", sa.String(1000), nullable=True),
        sa.Column("reviewed_by", FK_TYPE, nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("dispute_reason", sa.String(1000), nullable=True),
        sa.Column("dispute_resolution", sa.String(32), nullable=True),
        sa.Column("dispute_reviewed_by", FK_TYPE, nullable=True),
        sa.Column("dispute_reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("payment_id", FK_TYPE, nullable=True),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        *_timestamps(),
        sa.CheckConstraint("amount > 0", name="ck_receipt_amount_positive"),
        sa.CheckConstraint(
            "status IN ('PENDING','SUGGESTED','EXCEPTION','DISPUTED','CONFIRMED','REJECTED')",
            name="ck_receipt_status",
        ),
        sa.CheckConstraint("lock_version > 0", name="ck_receipt_lock_version"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["party_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["dispute_reviewed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "source_provider", "source_ref", name="uk_receipt_source"
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uk_receipts_tenant_id_id"),
    )
    op.create_index(
        "ix_receipt_inbox",
        "receipt_transactions",
        ["tenant_id", "park_id", "status", "received_at"],
    )
    op.create_index(
        "ix_receipt_party", "receipt_transactions", ["tenant_id", "party_id", "received_at"]
    )

    with op.batch_alter_table("payments") as batch:
        batch.add_column(sa.Column("source_receipt_id", FK_TYPE, nullable=True))
        batch.create_foreign_key(
            "fk_payment_source_receipt",
            "receipt_transactions",
            ["source_receipt_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    op.create_index(
        "uk_payments_source_receipt",
        "payments",
        ["tenant_id", "source_receipt_id"],
        unique=True,
        postgresql_where=sa.text("source_receipt_id IS NOT NULL"),
        sqlite_where=sa.text("source_receipt_id IS NOT NULL"),
    )
    with op.batch_alter_table("payment_allocations") as batch:
        batch.add_column(sa.Column("allocation_key", sa.String(128), nullable=True))
        batch.add_column(sa.Column("reversed_at", sa.DateTime(), nullable=True))

    op.create_table(
        "receipt_match_candidates",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("receipt_id", FK_TYPE, nullable=False),
        sa.Column("bill_id", FK_TYPE, nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("proposed_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("rule_codes_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_receipt_candidate_score"),
        sa.CheckConstraint("proposed_amount > 0", name="ck_receipt_candidate_amount"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "receipt_id"],
            ["receipt_transactions.tenant_id", "receipt_transactions.id"],
            name="fk_receipt_candidate_tenant_receipt",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "bill_id"],
            ["bills.tenant_id", "bills.id"],
            name="fk_receipt_candidate_tenant_bill",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "receipt_id", "bill_id", name="uk_receipt_candidate_bill"
        ),
    )
    op.create_index(
        "ix_receipt_candidate_rank",
        "receipt_match_candidates",
        ["tenant_id", "receipt_id", "rank"],
    )

    with op.batch_alter_table("collection_cases") as batch:
        batch.add_column(sa.Column("active_bill_key", sa.String(64), nullable=True))
        batch.add_column(
            sa.Column("amount_snapshot", sa.Numeric(14, 2), server_default="0", nullable=False)
        )
        batch.add_column(sa.Column("overdue_days", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(sa.Column("effective_due_date", sa.Date(), nullable=True))
        batch.add_column(
            sa.Column("strategy_code", sa.String(32), server_default="AGING_V1", nullable=False)
        )
        batch.add_column(sa.Column("next_action_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("last_contact_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("resolution_code", sa.String(32), nullable=True))
        batch.add_column(sa.Column("closed_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False))
        batch.create_unique_constraint(
            "uk_collection_cases_tenant_id_id", ["tenant_id", "id"]
        )
        batch.create_unique_constraint(
            "uk_collection_case_active_bill_key", ["tenant_id", "active_bill_key"]
        )
    op.create_index(
        "ix_collection_case_aging",
        "collection_cases",
        ["tenant_id", "park_id", "status", "level"],
    )

    op.create_table(
        "collection_records",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("case_id", FK_TYPE, nullable=False),
        sa.Column("action_type", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("channel", sa.String(24), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("source_ref", sa.String(128), nullable=True),
        sa.Column("external_ref", sa.String(128), nullable=True),
        sa.Column("next_follow_up_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["collection_cases.tenant_id", "collection_cases.id"],
            name="fk_collection_record_tenant_case",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uk_collection_record_source",
        "collection_records",
        ["tenant_id", "source_ref"],
        unique=True,
        postgresql_where=sa.text("source_ref IS NOT NULL"),
        sqlite_where=sa.text("source_ref IS NOT NULL"),
    )
    op.create_index(
        "ix_collection_record_case_time",
        "collection_records",
        ["tenant_id", "case_id", "created_at"],
    )

    op.create_table(
        "dunning_runs",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=True),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("run_key", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), server_default="RUNNING", nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=True),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        *_timestamps(),
        sa.CheckConstraint("mode IN ('PREVIEW','APPLY')", name="ck_dunning_run_mode"),
        sa.CheckConstraint(
            "status IN ('RUNNING','COMPLETED','FAILED')", name="ck_dunning_run_status"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "run_key", name="uk_dunning_run_key"),
    )
    op.create_index(
        "ix_dunning_run_scope", "dunning_runs", ["tenant_id", "park_id", "as_of"]
    )

    op.create_table(
        "receivable_adjustments",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("bill_id", FK_TYPE, nullable=False),
        sa.Column("adjustment_type", sa.String(16), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("requested_due_date", sa.Date(), nullable=True),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(24), server_default="PENDING_APPROVAL", nullable=False),
        sa.Column("bill_lock_version_snapshot", sa.Integer(), nullable=False),
        sa.Column("open_amount_snapshot", sa.Numeric(14, 2), nullable=False),
        sa.Column("approval_id", FK_TYPE, nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("requested_by", FK_TYPE, nullable=True),
        sa.Column("applied_by", FK_TYPE, nullable=True),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "adjustment_type IN ('WAIVER','EXTENSION','BAD_DEBT','DISPUTE')",
            name="ck_receivable_adjustment_type",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING_APPROVAL','APPROVED','REJECTED','APPLIED','WITHDRAWN')",
            name="ck_receivable_adjustment_status",
        ),
        sa.CheckConstraint(
            "amount IS NULL OR amount > 0", name="ck_receivable_adjustment_amount"
        ),
        sa.CheckConstraint("lock_version > 0", name="ck_receivable_adjustment_lock_version"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "bill_id"],
            ["bills.tenant_id", "bills.id"],
            name="fk_receivable_adjustment_tenant_bill",
        ),
        sa.ForeignKeyConstraint(["approval_id"], ["approval_requests.id"]),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["applied_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_receivable_adjustment_bill",
        "receivable_adjustments",
        ["tenant_id", "bill_id", "status"],
    )
    op.create_index(
        "uk_receivable_adjustment_request_key",
        "receivable_adjustments",
        ["tenant_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        sqlite_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("receivable_adjustments")
    op.drop_table("dunning_runs")
    op.drop_table("collection_records")
    op.drop_index("ix_collection_case_aging", table_name="collection_cases")
    with op.batch_alter_table("collection_cases") as batch:
        batch.drop_constraint("uk_collection_case_active_bill_key", type_="unique")
        batch.drop_constraint("uk_collection_cases_tenant_id_id", type_="unique")
        for column in (
            "lock_version",
            "closed_at",
            "resolution_code",
            "last_contact_at",
            "next_action_at",
            "strategy_code",
            "effective_due_date",
            "overdue_days",
            "amount_snapshot",
            "active_bill_key",
        ):
            batch.drop_column(column)
    op.drop_table("receipt_match_candidates")
    op.drop_index("uk_payments_source_receipt", table_name="payments")
    with op.batch_alter_table("payment_allocations") as batch:
        batch.drop_column("reversed_at")
        batch.drop_column("allocation_key")
    with op.batch_alter_table("payments") as batch:
        batch.drop_constraint("fk_payment_source_receipt", type_="foreignkey")
        batch.drop_column("source_receipt_id")
    op.drop_table("receipt_transactions")
    with op.batch_alter_table("payments") as batch:
        batch.drop_constraint("uk_payments_tenant_id_id", type_="unique")
    op.drop_index("uk_bill_lines_source_schedule", table_name="bill_lines")
    with op.batch_alter_table("bill_lines") as batch:
        batch.drop_constraint("fk_bill_line_source_schedule", type_="foreignkey")
        batch.drop_column("source_schedule_id")
    with op.batch_alter_table("lease_performance_schedules") as batch:
        batch.drop_constraint("uk_lease_schedules_tenant_id_id", type_="unique")
        batch.drop_constraint("fk_lease_schedule_bill", type_="foreignkey")
        batch.drop_column("billed_at")
        batch.drop_column("bill_id")
    op.drop_index("ix_bills_aging", table_name="bills")
    with op.batch_alter_table("bills") as batch:
        batch.drop_constraint("ck_bills_lock_version", type_="check")
        batch.drop_constraint("ck_bills_receivable_treatments", type_="check")
        batch.drop_constraint("uk_bills_tenant_id_id", type_="unique")
        batch.drop_column("lock_version")
        batch.drop_column("dispute_status")
        batch.drop_column("collection_hold")
        batch.drop_column("deferred_due_date")
        batch.drop_column("bad_debt_amount")
        batch.drop_column("waiver_amount")

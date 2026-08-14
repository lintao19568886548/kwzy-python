"""enforce tenant-consistent foreign keys for finance records

Revision ID: w9f57b2c4d31
Revises: v8e46a1b3c20
"""

from collections.abc import Sequence

from alembic import op

revision: str = "w9f57b2c4d31"
down_revision: str | None = "v8e46a1b3c20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CONSTRAINTS: tuple[tuple[str, str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("fk_bills_tenant_park", "bills", "parks", ("tenant_id", "park_id"), ("tenant_id", "id")),
    (
        "fk_bills_tenant_party",
        "bills",
        "parties",
        ("tenant_id", "party_id"),
        ("tenant_id", "id"),
    ),
    (
        "fk_bill_lines_tenant_bill",
        "bill_lines",
        "bills",
        ("tenant_id", "bill_id"),
        ("tenant_id", "id"),
    ),
    (
        "fk_receipts_tenant_park",
        "receipt_transactions",
        "parks",
        ("tenant_id", "park_id"),
        ("tenant_id", "id"),
    ),
    (
        "fk_receipts_tenant_party",
        "receipt_transactions",
        "parties",
        ("tenant_id", "party_id"),
        ("tenant_id", "id"),
    ),
    (
        "fk_receipts_tenant_payment",
        "receipt_transactions",
        "payments",
        ("tenant_id", "payment_id"),
        ("tenant_id", "id"),
    ),
    (
        "fk_payments_tenant_park",
        "payments",
        "parks",
        ("tenant_id", "park_id"),
        ("tenant_id", "id"),
    ),
    (
        "fk_payments_tenant_party",
        "payments",
        "parties",
        ("tenant_id", "party_id"),
        ("tenant_id", "id"),
    ),
    (
        "fk_payments_tenant_source_receipt",
        "payments",
        "receipt_transactions",
        ("tenant_id", "source_receipt_id"),
        ("tenant_id", "id"),
    ),
    (
        "fk_payment_allocations_tenant_payment",
        "payment_allocations",
        "payments",
        ("tenant_id", "payment_id"),
        ("tenant_id", "id"),
    ),
    (
        "fk_payment_allocations_tenant_bill",
        "payment_allocations",
        "bills",
        ("tenant_id", "bill_id"),
        ("tenant_id", "id"),
    ),
    (
        "fk_collection_cases_tenant_park",
        "collection_cases",
        "parks",
        ("tenant_id", "park_id"),
        ("tenant_id", "id"),
    ),
    (
        "fk_collection_cases_tenant_party",
        "collection_cases",
        "parties",
        ("tenant_id", "party_id"),
        ("tenant_id", "id"),
    ),
    (
        "fk_collection_cases_tenant_bill",
        "collection_cases",
        "bills",
        ("tenant_id", "bill_id"),
        ("tenant_id", "id"),
    ),
    (
        "fk_dunning_runs_tenant_park",
        "dunning_runs",
        "parks",
        ("tenant_id", "park_id"),
        ("tenant_id", "id"),
    ),
    (
        "fk_receivable_adjustments_tenant_park",
        "receivable_adjustments",
        "parks",
        ("tenant_id", "park_id"),
        ("tenant_id", "id"),
    ),
)


def upgrade() -> None:
    for name, source, target, local_columns, remote_columns in CONSTRAINTS:
        op.create_foreign_key(
            name,
            source,
            target,
            list(local_columns),
            list(remote_columns),
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    for name, source, _target, _local_columns, _remote_columns in reversed(CONSTRAINTS):
        op.drop_constraint(name, source, type_="foreignkey")

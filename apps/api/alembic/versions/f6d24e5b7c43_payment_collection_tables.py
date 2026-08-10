"""payment collection tables

Revision ID: f6d24e5b7c43
Revises: e5c13d4a6b32
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision = "f6d24e5b7c43"
down_revision = "e5c13d4a6b32"
branch_labels = None
depends_on = None

PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
FK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("party_id", FK_TYPE, nullable=False),
        sa.Column("payment_no", sa.String(64), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("operator_id", FK_TYPE, nullable=True),
        sa.Column("remark", sa.String(255), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["party_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "payment_no", name="uk_payments_no"),
    )
    op.create_index("ix_payments_tenant_id", "payments", ["tenant_id"])

    op.create_table(
        "payment_allocations",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("payment_id", FK_TYPE, nullable=False),
        sa.Column("bill_id", FK_TYPE, nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["bill_id"], ["bills.id"]),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_allocations_tenant_id", "payment_allocations", ["tenant_id"])
    op.create_index("idx_pa_payment", "payment_allocations", ["payment_id"])
    op.create_index("idx_pa_bill", "payment_allocations", ["bill_id"])


def downgrade() -> None:
    op.drop_index("idx_pa_bill", table_name="payment_allocations")
    op.drop_index("idx_pa_payment", table_name="payment_allocations")
    op.drop_index("ix_payment_allocations_tenant_id", table_name="payment_allocations")
    op.drop_table("payment_allocations")
    op.drop_index("ix_payments_tenant_id", table_name="payments")
    op.drop_table("payments")

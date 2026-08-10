"""bill master tables

Revision ID: e5c13d4a6b32
Revises: d4b02c3f5a21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5c13d4a6b32"
down_revision: Union[str, None] = "d4b02c3f5a21"
branch_labels = None
depends_on = None

PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
FK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "fee_catalog",
        sa.Column("tenant_id", FK_TYPE, nullable=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uk_fee_code"),
    )
    op.create_index("ix_fee_catalog_tenant_id", "fee_catalog", ["tenant_id"])

    op.create_table(
        "bills",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("party_id", FK_TYPE, nullable=False),
        sa.Column("contract_id", FK_TYPE, nullable=True),
        sa.Column("bill_no", sa.String(64), nullable=False),
        sa.Column("title", sa.String(128), nullable=True),
        sa.Column("project_name", sa.String(128), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("overdue_since", sa.Date(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("paid_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_ref", sa.String(64), nullable=True),
        sa.Column("remark", sa.String(255), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["contract_id"], ["lease_contracts.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["party_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "bill_no", name="uk_bills_no"),
    )
    op.create_index("ix_bills_tenant_id", "bills", ["tenant_id"])
    op.create_index("idx_bills_park_status", "bills", ["tenant_id", "park_id", "status"])
    op.create_index("idx_bills_party_period", "bills", ["tenant_id", "party_id", "period_start", "period_end"])

    op.create_table(
        "bill_lines",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("bill_id", FK_TYPE, nullable=False),
        sa.Column("fee_code", sa.String(32), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 6), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("meter_reading_from", sa.Numeric(14, 4), nullable=True),
        sa.Column("meter_reading_to", sa.Numeric(14, 4), nullable=True),
        sa.Column("multiplier", sa.Numeric(14, 4), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["bill_id"], ["bills.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bill_lines_tenant_id", "bill_lines", ["tenant_id"])
    op.create_index("idx_bill_lines_bill", "bill_lines", ["bill_id"])


def downgrade() -> None:
    op.drop_index("idx_bill_lines_bill", table_name="bill_lines")
    op.drop_index("ix_bill_lines_tenant_id", table_name="bill_lines")
    op.drop_table("bill_lines")
    op.drop_index("idx_bills_party_period", table_name="bills")
    op.drop_index("idx_bills_park_status", table_name="bills")
    op.drop_index("ix_bills_tenant_id", table_name="bills")
    op.drop_table("bills")
    op.drop_index("ix_fee_catalog_tenant_id", table_name="fee_catalog")
    op.drop_table("fee_catalog")

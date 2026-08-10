"""lease contract tables

Revision ID: d4b02c3f5a21
Revises: c3a91b2e4f10
Create Date: 2026-08-10

Lease contracts, contract units, terms. PostgreSQL 16 authoritative.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4b02c3f5a21"
down_revision: Union[str, None] = "c3a91b2e4f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
FK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "lease_contracts",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("party_id", FK_TYPE, nullable=False),
        sa.Column("contract_no", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("increase_date", sa.Date(), nullable=True),
        sa.Column("increase_rate", sa.Numeric(8, 4), nullable=True),
        sa.Column("deposit_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("remark", sa.String(length=255), nullable=True),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["party_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "contract_no", name="uk_lease_contract_no"),
    )
    op.create_index("ix_lease_contracts_tenant_id", "lease_contracts", ["tenant_id"])
    op.create_index(
        "idx_lease_park_status", "lease_contracts", ["tenant_id", "park_id", "status"]
    )
    op.create_index("idx_lease_party", "lease_contracts", ["tenant_id", "party_id"])
    op.create_index("idx_lease_end_date", "lease_contracts", ["tenant_id", "end_date"])

    op.create_table(
        "lease_contract_units",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("contract_id", FK_TYPE, nullable=False),
        sa.Column("unit_id", FK_TYPE, nullable=False),
        sa.Column("occupied_area", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit_rent_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["contract_id"], ["lease_contracts.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contract_id", "unit_id", name="uk_lcu_contract_unit"),
    )
    op.create_index("ix_lease_contract_units_tenant_id", "lease_contract_units", ["tenant_id"])
    op.create_index("idx_lcu_unit", "lease_contract_units", ["unit_id"])

    op.create_table(
        "lease_terms",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("contract_id", FK_TYPE, nullable=False),
        sa.Column("term_type", sa.String(length=32), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("rate", sa.Numeric(8, 4), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["contract_id"], ["lease_contracts.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lease_terms_tenant_id", "lease_terms", ["tenant_id"])
    op.create_index(
        "idx_lease_terms_contract", "lease_terms", ["tenant_id", "contract_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_lease_terms_contract", table_name="lease_terms")
    op.drop_index("ix_lease_terms_tenant_id", table_name="lease_terms")
    op.drop_table("lease_terms")
    op.drop_index("idx_lcu_unit", table_name="lease_contract_units")
    op.drop_index("ix_lease_contract_units_tenant_id", table_name="lease_contract_units")
    op.drop_table("lease_contract_units")
    op.drop_index("idx_lease_end_date", table_name="lease_contracts")
    op.drop_index("idx_lease_party", table_name="lease_contracts")
    op.drop_index("idx_lease_park_status", table_name="lease_contracts")
    op.drop_index("ix_lease_contracts_tenant_id", table_name="lease_contracts")
    op.drop_table("lease_contracts")

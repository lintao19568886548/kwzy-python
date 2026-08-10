"""auth payment integrity tables

Revision ID: a7e35f6c8d54
Revises: f6d24e5b7c43
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision = "a7e35f6c8d54"
down_revision = "f6d24e5b7c43"
branch_labels = None
depends_on = None

PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
FK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "number_sequences",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("biz_type", sa.String(32), nullable=False),
        sa.Column("period_key", sa.String(16), nullable=False, server_default=""),
        sa.Column("next_val", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "biz_type", "period_key", name="uk_number_seq"),
    )
    op.create_index("ix_number_sequences_tenant_id", "number_sequences", ["tenant_id"])

    op.create_table(
        "idempotency_keys",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("user_id", FK_TYPE, nullable=True),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("idem_key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("response_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "operation", "idem_key", name="uk_idem_tenant_op_key"),
    )
    op.create_index("ix_idempotency_keys_tenant_id", "idempotency_keys", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_idempotency_keys_tenant_id", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
    op.drop_index("ix_number_sequences_tenant_id", table_name="number_sequences")
    op.drop_table("number_sequences")

"""approval requests minimal

Revision ID: f2a80e5c3b64
Revises: e1c79d4f2b53
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision = "f2a80e5c3b64"
down_revision = "e1c79d4f2b53"
branch_labels = None
depends_on = None

PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
FK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "approval_requests",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=True),
        sa.Column("biz_type", sa.String(64), nullable=False),
        sa.Column("biz_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("applicant_user_id", FK_TYPE, nullable=True),
        sa.Column("approver_user_id", FK_TYPE, nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("decision_remark", sa.Text(), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["applicant_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["approver_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "biz_type", "biz_id", name="uk_approval_biz"),
    )
    op.create_index("ix_approval_requests_tenant_id", "approval_requests", ["tenant_id"])
    op.create_index("ix_approval_requests_park_id", "approval_requests", ["park_id"])
    op.create_index("ix_approval_requests_biz_type", "approval_requests", ["biz_type"])


def downgrade() -> None:
    op.drop_index("ix_approval_requests_biz_type", table_name="approval_requests")
    op.drop_index("ix_approval_requests_park_id", table_name="approval_requests")
    op.drop_index("ix_approval_requests_tenant_id", table_name="approval_requests")
    op.drop_table("approval_requests")

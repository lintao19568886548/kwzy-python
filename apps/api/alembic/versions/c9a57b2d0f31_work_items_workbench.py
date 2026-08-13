"""work items workbench

Revision ID: c9a57b2d0f31
Revises: b8f46a1c9e20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision = "c9a57b2d0f31"
down_revision = "b8f46a1c9e20"
branch_labels = None
depends_on = None

PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
FK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "work_items",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=True),
        sa.Column("item_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
        sa.Column("priority", sa.String(16), nullable=False, server_default="MEDIUM"),
        sa.Column("assignee_user_id", FK_TYPE, nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("source_type", sa.String(64), nullable=False, server_default="MANUAL"),
        sa.Column("source_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("completed_by", FK_TYPE, nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["assignee_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["completed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "source_type", "source_id", "item_type", name="uk_work_item_source"
        ),
    )
    op.create_index("ix_work_items_tenant_id", "work_items", ["tenant_id"])
    op.create_index("ix_work_items_park_id", "work_items", ["park_id"])
    op.create_index("ix_work_items_item_type", "work_items", ["item_type"])
    op.create_index("ix_work_items_assignee_user_id", "work_items", ["assignee_user_id"])


def downgrade() -> None:
    op.drop_index("ix_work_items_assignee_user_id", table_name="work_items")
    op.drop_index("ix_work_items_item_type", table_name="work_items")
    op.drop_index("ix_work_items_park_id", table_name="work_items")
    op.drop_index("ix_work_items_tenant_id", table_name="work_items")
    op.drop_table("work_items")

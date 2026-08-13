"""identity org dict params + work orders + collection cases

Revision ID: e1c79d4f2b53
Revises: d0b68c3e1a42
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision = "e1c79d4f2b53"
down_revision = "d0b68c3e1a42"
branch_labels = None
depends_on = None

PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
FK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "org_units",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("parent_id", FK_TYPE, nullable=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("remark", sa.String(255), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["org_units.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uk_org_unit_code"),
    )
    op.create_index("ix_org_units_tenant_id", "org_units", ["tenant_id"])
    op.create_index("ix_org_units_parent_id", "org_units", ["parent_id"])

    op.create_table(
        "dict_types",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("remark", sa.String(255), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uk_dict_type_code"),
    )
    op.create_index("ix_dict_types_tenant_id", "dict_types", ["tenant_id"])

    op.create_table(
        "dict_items",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("dict_type_id", FK_TYPE, nullable=False),
        sa.Column("item_label", sa.String(128), nullable=False),
        sa.Column("item_value", sa.String(128), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("remark", sa.String(255), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["dict_type_id"], ["dict_types.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "dict_type_id", "item_value", name="uk_dict_item_value"
        ),
    )
    op.create_index("ix_dict_items_tenant_id", "dict_items", ["tenant_id"])
    op.create_index("ix_dict_items_dict_type_id", "dict_items", ["dict_type_id"])

    op.create_table(
        "system_params",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("param_key", sa.String(128), nullable=False),
        sa.Column("param_value", sa.Text(), nullable=False),
        sa.Column("value_type", sa.String(32), nullable=False, server_default="STRING"),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("remark", sa.String(255), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "param_key", name="uk_system_param_key"),
    )
    op.create_index("ix_system_params_tenant_id", "system_params", ["tenant_id"])

    op.create_table(
        "work_orders",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(64), nullable=False, server_default="GENERAL"),
        sa.Column("priority", sa.String(16), nullable=False, server_default="MEDIUM"),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
        sa.Column("reporter_user_id", FK_TYPE, nullable=True),
        sa.Column("assignee_user_id", FK_TYPE, nullable=True),
        sa.Column("unit_id", FK_TYPE, nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("source_type", sa.String(64), nullable=False, server_default="MANUAL"),
        sa.Column("source_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["assignee_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_work_orders_tenant_id", "work_orders", ["tenant_id"])
    op.create_index("ix_work_orders_park_id", "work_orders", ["park_id"])
    op.create_index("ix_work_orders_status", "work_orders", ["status"])
    op.create_index("ix_work_orders_assignee_user_id", "work_orders", ["assignee_user_id"])

    op.create_table(
        "collection_cases",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("party_id", FK_TYPE, nullable=False),
        sa.Column("bill_id", FK_TYPE, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
        sa.Column("level", sa.String(16), nullable=False, server_default="L1"),
        sa.Column("assignee_user_id", FK_TYPE, nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["party_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(["bill_id"], ["bills.id"]),
        sa.ForeignKeyConstraint(["assignee_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collection_cases_tenant_id", "collection_cases", ["tenant_id"])
    op.create_index("ix_collection_cases_park_id", "collection_cases", ["park_id"])
    op.create_index("ix_collection_cases_party_id", "collection_cases", ["party_id"])
    op.create_index("ix_collection_cases_bill_id", "collection_cases", ["bill_id"])
    op.create_index("ix_collection_cases_status", "collection_cases", ["status"])


def downgrade() -> None:
    for name in (
        "ix_collection_cases_status",
        "ix_collection_cases_bill_id",
        "ix_collection_cases_party_id",
        "ix_collection_cases_park_id",
        "ix_collection_cases_tenant_id",
    ):
        op.drop_index(name, table_name="collection_cases")
    op.drop_table("collection_cases")
    for name in (
        "ix_work_orders_assignee_user_id",
        "ix_work_orders_status",
        "ix_work_orders_park_id",
        "ix_work_orders_tenant_id",
    ):
        op.drop_index(name, table_name="work_orders")
    op.drop_table("work_orders")
    op.drop_index("ix_system_params_tenant_id", table_name="system_params")
    op.drop_table("system_params")
    op.drop_index("ix_dict_items_dict_type_id", table_name="dict_items")
    op.drop_index("ix_dict_items_tenant_id", table_name="dict_items")
    op.drop_table("dict_items")
    op.drop_index("ix_dict_types_tenant_id", table_name="dict_types")
    op.drop_table("dict_types")
    op.drop_index("ix_org_units_parent_id", table_name="org_units")
    op.drop_index("ix_org_units_tenant_id", table_name="org_units")
    op.drop_table("org_units")

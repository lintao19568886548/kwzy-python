"""identity session menu admin

Revision ID: b8f46a1c9e20
Revises: a7e35f6c8d54
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision = "b8f46a1c9e20"
down_revision = "a7e35f6c8d54"
branch_labels = None
depends_on = None

PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
FK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("user_id", FK_TYPE, nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("replaced_by_hash", sa.String(128), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uk_refresh_token_hash"),
    )
    op.create_index("ix_refresh_tokens_tenant_id", "refresh_tokens", ["tenant_id"])
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table(
        "menus",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("parent_id", FK_TYPE, nullable=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("path", sa.String(255), nullable=False, server_default=""),
        sa.Column("component", sa.String(255), nullable=True),
        sa.Column("icon", sa.String(64), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("menu_type", sa.String(32), nullable=False, server_default="MENU"),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("permission_code", sa.String(128), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["menus.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_menus_tenant_id", "menus", ["tenant_id"])

    op.create_table(
        "role_menus",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("role_id", FK_TYPE, nullable=False),
        sa.Column("menu_id", FK_TYPE, nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.ForeignKeyConstraint(["menu_id"], ["menus.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "menu_id", name="uk_role_menu"),
    )
    op.create_index("ix_role_menus_tenant_id", "role_menus", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_role_menus_tenant_id", table_name="role_menus")
    op.drop_table("role_menus")
    op.drop_index("ix_menus_tenant_id", table_name="menus")
    op.drop_table("menus")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_tenant_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_column("users", "token_version")

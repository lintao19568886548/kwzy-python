"""step1 foundation hardening

Revision ID: 8c2f4aa10b7d
Revises: 44cb70117ff4
Create Date: 2026-08-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "8c2f4aa10b7d"
down_revision: Union[str, None] = "44cb70117ff4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
FK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("module", sa.String(length=64), nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "role_permissions",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("role_id", FK_TYPE, nullable=False),
        sa.Column("permission_id", FK_TYPE, nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "permission_id", name="uk_role_perm"),
    )
    op.create_index("ix_role_permissions_tenant_id", "role_permissions", ["tenant_id"])
    op.create_table(
        "user_roles",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("user_id", FK_TYPE, nullable=False),
        sa.Column("role_id", FK_TYPE, nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role_id", name="uk_user_role"),
    )
    op.create_index("ix_user_roles_tenant_id", "user_roles", ["tenant_id"])
    op.create_table(
        "role_park_scopes",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("role_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "park_id", name="uk_role_park"),
    )
    op.create_index("ix_role_park_scopes_tenant_id", "role_park_scopes", ["tenant_id"])
    op.create_table(
        "audit_logs",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("user_id", FK_TYPE, nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("park_id", FK_TYPE, nullable=True),
        sa.Column("detail_json", sa.JSON(), nullable=True),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index(
        "ix_audit_logs_tenant_created_at", "audit_logs", ["tenant_id", "created_at"]
    )
    op.create_index(
        "ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_resource", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_role_park_scopes_tenant_id", table_name="role_park_scopes")
    op.drop_table("role_park_scopes")
    op.drop_index("ix_user_roles_tenant_id", table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_index("ix_role_permissions_tenant_id", table_name="role_permissions")
    op.drop_table("role_permissions")
    op.drop_table("permissions")

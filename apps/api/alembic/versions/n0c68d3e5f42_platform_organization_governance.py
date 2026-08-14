"""platform organization governance

Revision ID: n0c68d3e5f42
Revises: m9b57c2d4e31
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n0c68d3e5f42"
down_revision: Union[str, None] = "m9b57c2d4e31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
FK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _identity_columns() -> list[sa.Column]:
    return [
        sa.Column("id", PK_TYPE, primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "organization_groups",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("remark", sa.String(500), nullable=True),
        *_identity_columns(),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'DISABLED')",
            name="ck_organization_group_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.UniqueConstraint("tenant_id", "code", name="uk_organization_group_code"),
    )
    op.create_index("ix_organization_groups_tenant_id", "organization_groups", ["tenant_id"])

    op.create_table(
        "organization_regions",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("group_id", FK_TYPE, nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("remark", sa.String(500), nullable=True),
        *_identity_columns(),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'DISABLED')",
            name="ck_organization_region_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["group_id"], ["organization_groups.id"]),
        sa.UniqueConstraint("tenant_id", "code", name="uk_organization_region_code"),
    )
    op.create_index("ix_organization_regions_tenant_id", "organization_regions", ["tenant_id"])
    op.create_index("ix_organization_regions_group_id", "organization_regions", ["group_id"])
    op.create_index(
        "ix_organization_regions_group_sort",
        "organization_regions",
        ["tenant_id", "group_id", "sort_order"],
    )

    op.create_table(
        "region_park_assignments",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("region_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("effective_from", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("effective_to", sa.DateTime(), nullable=True),
        sa.Column("assigned_by", FK_TYPE, nullable=True),
        sa.Column("ended_by", FK_TYPE, nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        *_identity_columns(),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_region_park_effective_range",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["region_id"], ["organization_regions.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["ended_by"], ["users.id"]),
    )
    for column in ("tenant_id", "region_id", "park_id"):
        op.create_index(
            f"ix_region_park_assignments_{column}",
            "region_park_assignments",
            [column],
        )
    op.create_index(
        "uk_region_park_current",
        "region_park_assignments",
        ["tenant_id", "park_id"],
        unique=True,
        postgresql_where=sa.text("effective_to IS NULL"),
        sqlite_where=sa.text("effective_to IS NULL"),
    )
    op.create_index(
        "ix_region_park_history",
        "region_park_assignments",
        ["tenant_id", "park_id", "effective_from"],
    )
    op.create_index(
        "ix_region_current_parks",
        "region_park_assignments",
        ["tenant_id", "region_id"],
        postgresql_where=sa.text("effective_to IS NULL"),
        sqlite_where=sa.text("effective_to IS NULL"),
    )

    op.create_table(
        "positions",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("org_unit_id", FK_TYPE, nullable=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("responsibilities", sa.Text(), nullable=True),
        *_identity_columns(),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'DISABLED')",
            name="ck_position_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["org_unit_id"], ["org_units.id"]),
        sa.UniqueConstraint("tenant_id", "code", name="uk_position_code"),
    )
    op.create_index("ix_positions_tenant_id", "positions", ["tenant_id"])
    op.create_index("ix_positions_org_unit_id", "positions", ["org_unit_id"])
    op.create_index(
        "ix_positions_org_sort",
        "positions",
        ["tenant_id", "org_unit_id", "sort_order"],
    )

    op.create_table(
        "user_position_assignments",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("user_id", FK_TYPE, nullable=False),
        sa.Column("position_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=True),
        sa.Column("scope_key", sa.String(64), server_default="TENANT", nullable=False),
        sa.Column("starts_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("assigned_by", FK_TYPE, nullable=True),
        sa.Column("ended_by", FK_TYPE, nullable=True),
        sa.Column("remark", sa.String(500), nullable=True),
        *_identity_columns(),
        sa.CheckConstraint(
            "ends_at IS NULL OR ends_at >= starts_at",
            name="ck_user_position_effective_range",
        ),
        sa.CheckConstraint(
            "scope_key = 'TENANT' OR scope_key LIKE 'PARK:%'",
            name="ck_user_position_scope_key",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["ended_by"], ["users.id"]),
    )
    for column in ("tenant_id", "user_id", "position_id", "park_id"):
        op.create_index(
            f"ix_user_position_assignments_{column}",
            "user_position_assignments",
            [column],
        )
    op.create_index(
        "uk_user_position_current",
        "user_position_assignments",
        ["tenant_id", "user_id", "position_id", "scope_key"],
        unique=True,
        postgresql_where=sa.text("ends_at IS NULL"),
        sqlite_where=sa.text("ends_at IS NULL"),
    )
    op.create_index(
        "uk_user_primary_position_current",
        "user_position_assignments",
        ["tenant_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("ends_at IS NULL AND is_primary = true"),
        sqlite_where=sa.text("ends_at IS NULL AND is_primary = 1"),
    )
    op.create_index(
        "ix_user_position_history",
        "user_position_assignments",
        ["tenant_id", "user_id", "starts_at"],
    )

    op.create_table(
        "field_access_policies",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("role_id", FK_TYPE, nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("field_name", sa.String(64), nullable=False),
        sa.Column("access_mode", sa.String(16), nullable=False),
        sa.Column("mask_strategy", sa.String(32), server_default="PHONE", nullable=False),
        sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
        *_identity_columns(),
        sa.CheckConstraint(
            "access_mode IN ('VISIBLE', 'MASKED', 'HIDDEN')",
            name="ck_field_access_mode",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'DISABLED')",
            name="ck_field_access_policy_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.UniqueConstraint(
            "tenant_id",
            "role_id",
            "resource_type",
            "field_name",
            name="uk_field_access_policy",
        ),
    )
    op.create_index("ix_field_access_policies_tenant_id", "field_access_policies", ["tenant_id"])
    op.create_index("ix_field_access_policies_role_id", "field_access_policies", ["role_id"])
    op.create_index(
        "ix_field_access_policy_resolve",
        "field_access_policies",
        ["tenant_id", "role_id", "resource_type", "status"],
    )


def downgrade() -> None:
    op.drop_table("field_access_policies")
    op.drop_table("user_position_assignments")
    op.drop_table("positions")
    op.drop_table("region_park_assignments")
    op.drop_table("organization_regions")
    op.drop_table("organization_groups")

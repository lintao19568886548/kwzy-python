"""asset templates, spatial geometry and portfolio views

Revision ID: q3f91b6c8d75
Revises: p2e80a5b7c64
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "q3f91b6c8d75"
down_revision: str | None = "p2e80a5b7c64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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
        "asset_templates",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), server_default="ACTIVE", nullable=False),
        sa.Column("is_builtin", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("updated_by", FK_TYPE, nullable=True),
        *_identity_columns(),
        sa.CheckConstraint("status IN ('ACTIVE','RETIRED')", name="ck_asset_template_status"),
        sa.CheckConstraint("current_version >= 0", name="ck_asset_template_current_version"),
        sa.CheckConstraint("lock_version > 0", name="ck_asset_template_lock_version"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.UniqueConstraint("tenant_id", "code", name="uk_asset_template_code"),
    )
    op.create_index("ix_asset_templates_tenant_id", "asset_templates", ["tenant_id"])
    op.create_index("ix_asset_templates_category", "asset_templates", ["category"])

    op.create_table(
        "asset_template_versions",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("template_id", FK_TYPE, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), server_default="DRAFT", nullable=False),
        sa.Column("field_schema_json", sa.JSON(), nullable=False),
        sa.Column("defaults_json", sa.JSON(), nullable=False),
        sa.Column("schema_checksum", sa.String(64), nullable=False),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("published_by", FK_TYPE, nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        *_identity_columns(),
        sa.CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','RETIRED')",
            name="ck_asset_template_version_status",
        ),
        sa.CheckConstraint("version > 0", name="ck_asset_template_version_positive"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["asset_templates.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"]),
        sa.UniqueConstraint("template_id", "version", name="uk_asset_template_version"),
    )
    op.create_index(
        "ix_asset_template_versions_tenant_id", "asset_template_versions", ["tenant_id"]
    )
    op.create_index(
        "ix_asset_template_versions_template_id", "asset_template_versions", ["template_id"]
    )
    op.create_index(
        "uk_asset_template_one_draft",
        "asset_template_versions",
        ["template_id"],
        unique=True,
        postgresql_where=sa.text("status = 'DRAFT'"),
        sqlite_where=sa.text("status = 'DRAFT'"),
    )

    with op.batch_alter_table("buildings") as batch_op:
        batch_op.add_column(sa.Column("geometry_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("geometry_type", sa.String(16), nullable=True))
        batch_op.add_column(sa.Column("coordinate_reference", sa.String(32), nullable=True))
        batch_op.add_column(
            sa.Column("geometry_version", sa.Integer(), server_default="1", nullable=False)
        )

    with op.batch_alter_table("units") as batch_op:
        batch_op.add_column(sa.Column("asset_template_version_id", FK_TYPE, nullable=True))
        batch_op.create_foreign_key(
            "fk_units_asset_template_version_id",
            "asset_template_versions",
            ["asset_template_version_id"],
            ["id"],
        )
        batch_op.create_index("ix_units_asset_template_version_id", ["asset_template_version_id"])


def downgrade() -> None:
    with op.batch_alter_table("units") as batch_op:
        batch_op.drop_index("ix_units_asset_template_version_id")
        batch_op.drop_constraint("fk_units_asset_template_version_id", type_="foreignkey")
        batch_op.drop_column("asset_template_version_id")
    with op.batch_alter_table("buildings") as batch_op:
        batch_op.drop_column("geometry_version")
        batch_op.drop_column("coordinate_reference")
        batch_op.drop_column("geometry_type")
        batch_op.drop_column("geometry_json")
    op.drop_index("uk_asset_template_one_draft", table_name="asset_template_versions")
    op.drop_index("ix_asset_template_versions_template_id", table_name="asset_template_versions")
    op.drop_index("ix_asset_template_versions_tenant_id", table_name="asset_template_versions")
    op.drop_table("asset_template_versions")
    op.drop_index("ix_asset_templates_category", table_name="asset_templates")
    op.drop_index("ix_asset_templates_tenant_id", table_name="asset_templates")
    op.drop_table("asset_templates")

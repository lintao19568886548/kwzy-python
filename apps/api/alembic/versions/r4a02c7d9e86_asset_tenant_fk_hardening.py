"""enforce tenant-local asset template references

Revision ID: r4a02c7d9e86
Revises: q3f91b6c8d75
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "r4a02c7d9e86"
down_revision: str | None = "q3f91b6c8d75"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _fk_name(table_name: str, constrained_columns: list[str]) -> str:
    inspector = sa.inspect(op.get_bind())
    for foreign_key in inspector.get_foreign_keys(table_name):
        if foreign_key["constrained_columns"] == constrained_columns:
            name = foreign_key.get("name")
            if name:
                return str(name)
    raise RuntimeError(
        f"named foreign key not found: {table_name}({','.join(constrained_columns)})"
    )


def upgrade() -> None:
    op.create_unique_constraint(
        "uk_asset_template_tenant_id_id", "asset_templates", ["tenant_id", "id"]
    )
    op.create_unique_constraint(
        "uk_asset_template_version_tenant_id_id",
        "asset_template_versions",
        ["tenant_id", "id"],
    )

    version_fk = _fk_name("asset_template_versions", ["template_id"])
    op.drop_constraint(version_fk, "asset_template_versions", type_="foreignkey")
    op.create_foreign_key(
        "fk_asset_template_versions_tenant_template",
        "asset_template_versions",
        "asset_templates",
        ["tenant_id", "template_id"],
        ["tenant_id", "id"],
    )

    unit_fk = _fk_name("units", ["asset_template_version_id"])
    op.drop_constraint(unit_fk, "units", type_="foreignkey")
    op.create_foreign_key(
        "fk_units_tenant_asset_template_version",
        "units",
        "asset_template_versions",
        ["tenant_id", "asset_template_version_id"],
        ["tenant_id", "id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_units_tenant_asset_template_version", "units", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_units_asset_template_version_id",
        "units",
        "asset_template_versions",
        ["asset_template_version_id"],
        ["id"],
    )
    op.drop_constraint(
        "fk_asset_template_versions_tenant_template",
        "asset_template_versions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_asset_template_versions_template_id",
        "asset_template_versions",
        "asset_templates",
        ["template_id"],
        ["id"],
    )
    op.drop_constraint(
        "uk_asset_template_version_tenant_id_id",
        "asset_template_versions",
        type_="unique",
    )
    op.drop_constraint(
        "uk_asset_template_tenant_id_id", "asset_templates", type_="unique"
    )

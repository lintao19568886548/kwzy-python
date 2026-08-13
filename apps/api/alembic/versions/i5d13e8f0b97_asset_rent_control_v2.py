"""asset rent control v2

Revision ID: i5d13e8f0b97
Revises: h4c02d7e9a86
"""

from typing import Sequence, Union
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "i5d13e8f0b97"
down_revision: Union[str, None] = "h4c02d7e9a86"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
FK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    with op.batch_alter_table("buildings") as batch:
        batch.add_column(sa.Column("parent_id", FK_TYPE, nullable=True))
        batch.add_column(sa.Column("code", sa.String(64), nullable=True))
        batch.add_column(
            sa.Column("node_type", sa.String(32), nullable=True, server_default="BUILDING")
        )
        batch.add_column(sa.Column("sort_order", sa.Integer(), nullable=True, server_default="0"))
        batch.add_column(
            sa.Column("status", sa.String(32), nullable=True, server_default="ACTIVE")
        )
        batch.add_column(sa.Column("attributes_json", sa.JSON(), nullable=True))

    bind = op.get_bind()
    building_ids = [row[0] for row in bind.execute(sa.text("SELECT id FROM buildings"))]
    for building_id in building_ids:
        bind.execute(
            sa.text(
                "UPDATE buildings SET code=:code, node_type='BUILDING', "
                "sort_order=0, status='ACTIVE' WHERE id=:id"
            ),
            {"id": building_id, "code": f"B-{building_id}"},
        )

    with op.batch_alter_table("buildings") as batch:
        batch.alter_column("code", nullable=False)
        batch.alter_column("node_type", nullable=False, server_default=None)
        batch.alter_column("sort_order", nullable=False, server_default=None)
        batch.alter_column("status", nullable=False, server_default=None)
        batch.create_foreign_key(
            "fk_buildings_parent_id_buildings", "buildings", ["parent_id"], ["id"]
        )
        batch.create_index("ix_buildings_parent_id", ["parent_id"])

    op.create_index(
        "uk_spatial_root_code",
        "buildings",
        ["tenant_id", "park_id", "code"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NULL AND is_deleted = false"),
        sqlite_where=sa.text("parent_id IS NULL AND is_deleted = 0"),
    )
    op.create_index(
        "uk_spatial_child_code",
        "buildings",
        ["tenant_id", "park_id", "parent_id", "code"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NOT NULL AND is_deleted = false"),
        sqlite_where=sa.text("parent_id IS NOT NULL AND is_deleted = 0"),
    )

    with op.batch_alter_table("units") as batch:
        batch.drop_constraint("uk_units_building_code", type_="unique")
        batch.add_column(sa.Column("logical_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("version_no", sa.Integer(), nullable=True, server_default="1"))
        batch.add_column(
            sa.Column("valid_from", sa.DateTime(), nullable=True, server_default=sa.func.now())
        )
        batch.add_column(sa.Column("valid_to", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("supersedes_id", FK_TYPE, nullable=True))
        batch.add_column(sa.Column("lock_version", sa.Integer(), nullable=True, server_default="1"))
        batch.add_column(
            sa.Column("usage_type", sa.String(32), nullable=True, server_default="FACTORY")
        )
        batch.add_column(
            sa.Column("billing_unit", sa.String(16), nullable=True, server_default="SQM")
        )
        batch.add_column(sa.Column("available_from", sa.Date(), nullable=True))

    unit_ids = [row[0] for row in bind.execute(sa.text("SELECT id FROM units"))]
    for unit_id in unit_ids:
        logical_id = str(uuid5(NAMESPACE_URL, f"kwzy-v2-unit-{unit_id}"))
        bind.execute(
            sa.text(
                "UPDATE units SET logical_id=:logical_id, version_no=1, code=UPPER(TRIM(code)), "
                "valid_from=COALESCE(created_at, CURRENT_TIMESTAMP), lock_version=1, "
                "usage_type='FACTORY', billing_unit='SQM' WHERE id=:id"
            ),
            {"id": unit_id, "logical_id": logical_id},
        )

    with op.batch_alter_table("units") as batch:
        batch.alter_column("logical_id", nullable=False)
        batch.alter_column("version_no", nullable=False, server_default=None)
        batch.alter_column("valid_from", nullable=False, server_default=None)
        batch.alter_column("lock_version", nullable=False, server_default=None)
        batch.alter_column("usage_type", nullable=False, server_default=None)
        batch.alter_column("billing_unit", nullable=False, server_default=None)
        batch.create_foreign_key(
            "fk_units_supersedes_id_units", "units", ["supersedes_id"], ["id"]
        )
        batch.create_index("ix_units_logical_id", ["logical_id"])
        batch.create_index("ix_units_supersedes_id", ["supersedes_id"])
        batch.create_index("ix_units_logical_version", ["logical_id", "version_no"])
        batch.create_unique_constraint(
            "uk_units_space_code_version", ["building_id", "code", "version_no"]
        )

    op.create_index(
        "uk_units_current_space_code",
        "units",
        ["building_id", "code"],
        unique=True,
        postgresql_where=sa.text("valid_to IS NULL AND is_deleted = false"),
        sqlite_where=sa.text("valid_to IS NULL AND is_deleted = 0"),
    )

    op.create_table(
        "unit_lineages",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("operation_id", sa.String(36), nullable=False),
        sa.Column("operation_type", sa.String(16), nullable=False),
        sa.Column("source_unit_id", FK_TYPE, nullable=False),
        sa.Column("target_unit_id", FK_TYPE, nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["source_unit_id"], ["units.id"]),
        sa.ForeignKeyConstraint(["target_unit_id"], ["units.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "operation_id",
            "source_unit_id",
            "target_unit_id",
            name="uk_unit_lineage_edge",
        ),
    )
    op.create_index("ix_unit_lineages_tenant_id", "unit_lineages", ["tenant_id"])
    op.create_index("ix_unit_lineages_park_id", "unit_lineages", ["park_id"])
    op.create_index("ix_unit_lineages_source_unit_id", "unit_lineages", ["source_unit_id"])
    op.create_index("ix_unit_lineages_target_unit_id", "unit_lineages", ["target_unit_id"])
    op.create_index(
        "ix_unit_lineages_operation",
        "unit_lineages",
        ["tenant_id", "operation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_unit_lineages_operation", table_name="unit_lineages")
    op.drop_index("ix_unit_lineages_target_unit_id", table_name="unit_lineages")
    op.drop_index("ix_unit_lineages_source_unit_id", table_name="unit_lineages")
    op.drop_index("ix_unit_lineages_park_id", table_name="unit_lineages")
    op.drop_index("ix_unit_lineages_tenant_id", table_name="unit_lineages")
    op.drop_table("unit_lineages")

    op.drop_index("uk_units_current_space_code", table_name="units")
    with op.batch_alter_table("units") as batch:
        batch.drop_constraint("uk_units_space_code_version", type_="unique")
        batch.drop_index("ix_units_logical_version")
        batch.drop_index("ix_units_supersedes_id")
        batch.drop_index("ix_units_logical_id")
        batch.drop_constraint("fk_units_supersedes_id_units", type_="foreignkey")
        batch.drop_column("available_from")
        batch.drop_column("billing_unit")
        batch.drop_column("usage_type")
        batch.drop_column("lock_version")
        batch.drop_column("supersedes_id")
        batch.drop_column("valid_to")
        batch.drop_column("valid_from")
        batch.drop_column("version_no")
        batch.drop_column("logical_id")
        batch.create_unique_constraint(
            "uk_units_building_code", ["building_id", "code"]
        )

    op.drop_index("uk_spatial_child_code", table_name="buildings")
    op.drop_index("uk_spatial_root_code", table_name="buildings")
    with op.batch_alter_table("buildings") as batch:
        batch.drop_index("ix_buildings_parent_id")
        batch.drop_constraint("fk_buildings_parent_id_buildings", type_="foreignkey")
        batch.drop_column("attributes_json")
        batch.drop_column("status")
        batch.drop_column("sort_order")
        batch.drop_column("node_type")
        batch.drop_column("code")
        batch.drop_column("parent_id")

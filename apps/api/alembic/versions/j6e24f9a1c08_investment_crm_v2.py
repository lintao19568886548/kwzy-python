"""investment crm v2

Revision ID: j6e24f9a1c08
Revises: i5d13e8f0b97
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j6e24f9a1c08"
down_revision: Union[str, None] = "i5d13e8f0b97"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
FK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _normalized_name(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _normalized_phone(value: object) -> str:
    raw = str(value or "").strip()
    return "".join(ch for ch in raw if ch.isdigit() or ch == "+")


def upgrade() -> None:
    with op.batch_alter_table("leads") as batch:
        batch.add_column(sa.Column("desired_usage", sa.String(32), nullable=True))
        batch.add_column(sa.Column("budget_unit_price", sa.Numeric(12, 2), nullable=True))
        batch.add_column(sa.Column("normalized_name", sa.String(128), nullable=True))
        batch.add_column(sa.Column("normalized_phone", sa.String(32), nullable=True))
        batch.add_column(sa.Column("source_type", sa.String(32), nullable=True, server_default="MANUAL"))
        batch.add_column(sa.Column("source_ref", sa.String(128), nullable=True))
        batch.add_column(sa.Column("duplicate_override_reason", sa.String(255), nullable=True))
        batch.add_column(sa.Column("pool_status", sa.String(16), nullable=True, server_default="PRIVATE"))
        batch.add_column(sa.Column("assigned_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("first_contact_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("last_activity_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("next_follow_up_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("recycle_due_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("merged_into_lead_id", FK_TYPE, nullable=True))
        batch.add_column(sa.Column("lock_version", sa.Integer(), nullable=True, server_default="1"))

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, name, contact_phone, status, owner_user_id, created_at "
            "FROM leads ORDER BY id"
        )
    ).mappings()
    for row in rows:
        status = "CONTACTING" if str(row["status"] or "").upper() == "FOLLOWING" else str(row["status"] or "NEW").upper()
        owner_id = row["owner_user_id"]
        bind.execute(
            sa.text(
                "UPDATE leads SET normalized_name=:normalized_name, "
                "normalized_phone=:normalized_phone, source_type='MANUAL', "
                "pool_status=:pool_status, assigned_at=:assigned_at, "
                "status=:status, lock_version=1 WHERE id=:id"
            ),
            {
                "id": row["id"],
                "normalized_name": _normalized_name(row["name"]),
                "normalized_phone": _normalized_phone(row["contact_phone"]),
                "pool_status": "PRIVATE" if owner_id is not None else "PUBLIC",
                "assigned_at": row["created_at"] if owner_id is not None else None,
                "status": status,
            },
        )

    with op.batch_alter_table("leads") as batch:
        batch.alter_column("normalized_name", nullable=False)
        batch.alter_column("normalized_phone", nullable=False)
        batch.alter_column("source_type", nullable=False, server_default=None)
        batch.alter_column("pool_status", nullable=False, server_default=None)
        batch.alter_column("lock_version", nullable=False, server_default=None)
        batch.create_foreign_key(
            "fk_leads_merged_into_lead_id_leads", "leads", ["merged_into_lead_id"], ["id"]
        )
        batch.create_index("ix_leads_merged_into_lead_id", ["merged_into_lead_id"])
        batch.create_index("ix_leads_pool_status", ["pool_status"])
        batch.create_index(
            "ix_leads_scope_owner_stage", ["tenant_id", "park_id", "owner_user_id", "status"]
        )
        batch.create_index(
            "ix_leads_scope_pool_stage", ["tenant_id", "park_id", "pool_status", "status"]
        )
        batch.create_index(
            "ix_leads_scope_source_created", ["tenant_id", "park_id", "source_type", "created_at"]
        )

    op.create_index(
        "uk_leads_source_ref",
        "leads",
        ["tenant_id", "source_type", "source_ref"],
        unique=True,
        postgresql_where=sa.text("source_ref IS NOT NULL"),
        sqlite_where=sa.text("source_ref IS NOT NULL"),
    )

    op.create_table(
        "lead_activities",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("lead_id", FK_TYPE, nullable=False),
        sa.Column("actor_user_id", FK_TYPE, nullable=True),
        sa.Column("activity_type", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("next_follow_up_at", sa.DateTime(), nullable=True),
        sa.Column("stage_from", sa.String(32), nullable=True),
        sa.Column("stage_to", sa.String(32), nullable=True),
        sa.Column("attributes_json", sa.JSON(), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_activities_tenant_id", "lead_activities", ["tenant_id"])
    op.create_index("ix_lead_activities_park_id", "lead_activities", ["park_id"])
    op.create_index("ix_lead_activities_lead_id", "lead_activities", ["lead_id"])
    op.create_index(
        "ix_lead_activities_timeline",
        "lead_activities",
        ["tenant_id", "lead_id", "occurred_at", "id"],
    )

    op.create_table(
        "lead_assignment_events",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("lead_id", FK_TYPE, nullable=False),
        sa.Column("from_owner_user_id", FK_TYPE, nullable=True),
        sa.Column("to_owner_user_id", FK_TYPE, nullable=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("actor_user_id", FK_TYPE, nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["from_owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["to_owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_assignment_events_tenant_id", "lead_assignment_events", ["tenant_id"])
    op.create_index("ix_lead_assignment_events_park_id", "lead_assignment_events", ["park_id"])
    op.create_index("ix_lead_assignment_events_lead_id", "lead_assignment_events", ["lead_id"])
    op.create_index(
        "ix_lead_assignment_timeline",
        "lead_assignment_events",
        ["tenant_id", "lead_id", "occurred_at", "id"],
    )

    op.create_table(
        "lead_merge_links",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("source_lead_id", FK_TYPE, nullable=False),
        sa.Column("target_lead_id", FK_TYPE, nullable=False),
        sa.Column("actor_user_id", FK_TYPE, nullable=True),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("merged_at", sa.DateTime(), nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["source_lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["target_lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_lead_id", name="uq_lead_merge_links_source_lead_id"),
    )
    op.create_index("ix_lead_merge_links_tenant_id", "lead_merge_links", ["tenant_id"])
    op.create_index("ix_lead_merge_links_park_id", "lead_merge_links", ["park_id"])
    op.create_index("ix_lead_merge_links_target_lead_id", "lead_merge_links", ["target_lead_id"])

    op.create_table(
        "lead_unit_locks",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("lead_id", FK_TYPE, nullable=False),
        sa.Column("unit_id", FK_TYPE, nullable=False),
        sa.Column("lease_id", FK_TYPE, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"]),
        sa.ForeignKeyConstraint(["lease_id"], ["lease_contracts.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_unit_locks_tenant_id", "lead_unit_locks", ["tenant_id"])
    op.create_index("ix_lead_unit_locks_park_id", "lead_unit_locks", ["park_id"])
    op.create_index("ix_lead_unit_locks_lead_id", "lead_unit_locks", ["lead_id"])
    op.create_index("ix_lead_unit_locks_unit_id", "lead_unit_locks", ["unit_id"])
    op.create_index("ix_lead_unit_locks_lease_id", "lead_unit_locks", ["lease_id"])
    op.create_index("ix_lead_unit_locks_status", "lead_unit_locks", ["status"])
    op.create_index("ix_lead_unit_locks_expires_at", "lead_unit_locks", ["expires_at"])
    op.create_index(
        "ix_lead_unit_locks_expiry",
        "lead_unit_locks",
        ["tenant_id", "status", "expires_at"],
    )
    op.create_index(
        "uk_lead_unit_locks_active_unit",
        "lead_unit_locks",
        ["tenant_id", "unit_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
        sqlite_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index("uk_lead_unit_locks_active_unit", table_name="lead_unit_locks")
    op.drop_index("ix_lead_unit_locks_expiry", table_name="lead_unit_locks")
    op.drop_index("ix_lead_unit_locks_expires_at", table_name="lead_unit_locks")
    op.drop_index("ix_lead_unit_locks_status", table_name="lead_unit_locks")
    op.drop_index("ix_lead_unit_locks_lease_id", table_name="lead_unit_locks")
    op.drop_index("ix_lead_unit_locks_unit_id", table_name="lead_unit_locks")
    op.drop_index("ix_lead_unit_locks_lead_id", table_name="lead_unit_locks")
    op.drop_index("ix_lead_unit_locks_park_id", table_name="lead_unit_locks")
    op.drop_index("ix_lead_unit_locks_tenant_id", table_name="lead_unit_locks")
    op.drop_table("lead_unit_locks")

    op.drop_index("ix_lead_merge_links_target_lead_id", table_name="lead_merge_links")
    op.drop_index("ix_lead_merge_links_park_id", table_name="lead_merge_links")
    op.drop_index("ix_lead_merge_links_tenant_id", table_name="lead_merge_links")
    op.drop_table("lead_merge_links")

    op.drop_index("ix_lead_assignment_timeline", table_name="lead_assignment_events")
    op.drop_index("ix_lead_assignment_events_lead_id", table_name="lead_assignment_events")
    op.drop_index("ix_lead_assignment_events_park_id", table_name="lead_assignment_events")
    op.drop_index("ix_lead_assignment_events_tenant_id", table_name="lead_assignment_events")
    op.drop_table("lead_assignment_events")

    op.drop_index("ix_lead_activities_timeline", table_name="lead_activities")
    op.drop_index("ix_lead_activities_lead_id", table_name="lead_activities")
    op.drop_index("ix_lead_activities_park_id", table_name="lead_activities")
    op.drop_index("ix_lead_activities_tenant_id", table_name="lead_activities")
    op.drop_table("lead_activities")

    op.drop_index("uk_leads_source_ref", table_name="leads")
    with op.batch_alter_table("leads") as batch:
        batch.drop_index("ix_leads_scope_source_created")
        batch.drop_index("ix_leads_scope_pool_stage")
        batch.drop_index("ix_leads_scope_owner_stage")
        batch.drop_index("ix_leads_pool_status")
        batch.drop_index("ix_leads_merged_into_lead_id")
        batch.drop_constraint("fk_leads_merged_into_lead_id_leads", type_="foreignkey")
        batch.drop_column("lock_version")
        batch.drop_column("merged_into_lead_id")
        batch.drop_column("recycle_due_at")
        batch.drop_column("next_follow_up_at")
        batch.drop_column("last_activity_at")
        batch.drop_column("first_contact_at")
        batch.drop_column("assigned_at")
        batch.drop_column("pool_status")
        batch.drop_column("duplicate_override_reason")
        batch.drop_column("source_ref")
        batch.drop_column("source_type")
        batch.drop_column("normalized_phone")
        batch.drop_column("normalized_name")
        batch.drop_column("budget_unit_price")
        batch.drop_column("desired_usage")

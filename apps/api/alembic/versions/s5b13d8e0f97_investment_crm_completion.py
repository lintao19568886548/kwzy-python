"""investment crm assignment viewing intent and channel completion

Revision ID: s5b13d8e0f97
Revises: r4a02c7d9e86
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "s5b13d8e0f97"
down_revision: Union[str, None] = "r4a02c7d9e86"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
FK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.create_unique_constraint("uk_users_tenant_id_id", ["tenant_id", "id"])
    with op.batch_alter_table("parks") as batch:
        batch.create_unique_constraint("uk_parks_tenant_id_id", ["tenant_id", "id"])
    with op.batch_alter_table("units") as batch:
        batch.create_unique_constraint("uk_units_tenant_id_id", ["tenant_id", "id"])
    with op.batch_alter_table("approval_requests") as batch:
        batch.create_unique_constraint(
            "uk_approval_requests_tenant_id_id", ["tenant_id", "id"]
        )
    with op.batch_alter_table("leads") as batch:
        batch.create_unique_constraint("uk_leads_tenant_id_id", ["tenant_id", "id"])

    op.create_table(
        "lead_assignment_rules",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("trigger", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("updated_by", FK_TYPE, nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "trigger IN ('MANUAL_CREATE', 'CHANNEL_INTAKE', 'RECYCLE')",
            name="ck_lead_assignment_rule_trigger",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'RETIRED')", name="ck_lead_assignment_rule_status"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_lead_assignment_rule_tenant_park",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uk_lead_assignment_rules_tenant_id_id"),
        sa.UniqueConstraint(
            "tenant_id", "park_id", "trigger", name="uk_lead_assignment_rule_park_trigger"
        ),
    )
    op.create_index("ix_lead_assignment_rules_tenant_id", "lead_assignment_rules", ["tenant_id"])
    op.create_index("ix_lead_assignment_rules_park_id", "lead_assignment_rules", ["park_id"])

    op.create_table(
        "lead_assignment_rule_versions",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("rule_id", FK_TYPE, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("strategy", sa.String(32), nullable=False, server_default="LEAST_LOAD"),
        sa.Column("recycle_after_hours", sa.Integer(), nullable=False, server_default="72"),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("published_by", FK_TYPE, nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'PUBLISHED', 'RETIRED')",
            name="ck_lead_assignment_rule_version_status",
        ),
        sa.CheckConstraint(
            "strategy = 'LEAST_LOAD'", name="ck_lead_assignment_rule_strategy"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "rule_id"],
            ["lead_assignment_rules.tenant_id", "lead_assignment_rules.id"],
            name="fk_lead_assignment_rule_version_tenant_rule",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_id", "version", name="uk_lead_assignment_rule_version"),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uk_lead_assignment_rule_versions_tenant_id_id"
        ),
    )
    op.create_index(
        "ix_lead_assignment_rule_versions_tenant_id",
        "lead_assignment_rule_versions",
        ["tenant_id"],
    )
    op.create_index(
        "ix_lead_assignment_rule_versions_rule_id",
        "lead_assignment_rule_versions",
        ["rule_id"],
    )
    op.create_index(
        "uk_lead_assignment_rule_one_draft",
        "lead_assignment_rule_versions",
        ["rule_id"],
        unique=True,
        postgresql_where=sa.text("status = 'DRAFT'"),
        sqlite_where=sa.text("status = 'DRAFT'"),
    )

    op.create_table(
        "lead_assignment_members",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("version_id", FK_TYPE, nullable=False),
        sa.Column("user_id", FK_TYPE, nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("member_order", sa.Integer(), nullable=False),
        sa.Column("last_assigned_at", sa.DateTime(), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "capacity > 0 AND capacity <= 10000", name="ck_lead_assignment_capacity"
        ),
        sa.CheckConstraint("weight > 0 AND weight <= 100", name="ck_lead_assignment_weight"),
        sa.CheckConstraint(
            "member_order > 0", name="ck_lead_assignment_member_order_positive"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "version_id"],
            ["lead_assignment_rule_versions.tenant_id", "lead_assignment_rule_versions.id"],
            name="fk_lead_assignment_member_tenant_version",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_lead_assignment_member_tenant_user",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id", "user_id", name="uk_lead_assignment_member_user"),
        sa.UniqueConstraint(
            "version_id", "member_order", name="uk_lead_assignment_member_order"
        ),
    )
    for column in ("tenant_id", "version_id", "user_id"):
        op.create_index(
            f"ix_lead_assignment_members_{column}", "lead_assignment_members", [column]
        )

    with op.batch_alter_table("lead_assignment_events") as batch:
        batch.add_column(sa.Column("rule_version_id", FK_TYPE, nullable=True))
        batch.add_column(sa.Column("trigger", sa.String(32), nullable=True))
        batch.add_column(sa.Column("decision_json", sa.JSON(), nullable=True))
        batch.create_index("ix_lead_assignment_events_rule_version_id", ["rule_version_id"])
        batch.create_foreign_key(
            "fk_lead_assignment_event_tenant_rule_version",
            "lead_assignment_rule_versions",
            ["tenant_id", "rule_version_id"],
            ["tenant_id", "id"],
        )

    op.create_table(
        "lead_viewings",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("lead_id", FK_TYPE, nullable=False),
        sa.Column("owner_user_id", FK_TYPE, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="SCHEDULED"),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("visitor_name", sa.String(64), nullable=True),
        sa.Column("visitor_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(1000), nullable=True),
        sa.Column("next_follow_up_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("cancellation_reason", sa.String(255), nullable=True),
        sa.Column("completion_idempotency_key", sa.String(64), nullable=True),
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("updated_by", FK_TYPE, nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        *_timestamps(),
        sa.CheckConstraint("ends_at > starts_at", name="ck_lead_viewing_time_order"),
        sa.CheckConstraint(
            "status IN ('SCHEDULED', 'CONFIRMED', 'COMPLETED', 'CANCELLED', 'NO_SHOW')",
            name="ck_lead_viewing_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_lead_viewing_tenant_park",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "lead_id"],
            ["leads.tenant_id", "leads.id"],
            name="fk_lead_viewing_tenant_lead",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "owner_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_lead_viewing_tenant_owner",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uk_lead_viewings_tenant_id_id"),
    )
    for column in ("tenant_id", "park_id", "lead_id", "owner_user_id"):
        op.create_index(f"ix_lead_viewings_{column}", "lead_viewings", [column])
    op.create_index(
        "ix_lead_viewings_owner_window",
        "lead_viewings",
        ["tenant_id", "owner_user_id", "status", "starts_at", "ends_at"],
    )
    op.create_index(
        "uk_lead_viewing_completion_key",
        "lead_viewings",
        ["tenant_id", "completion_idempotency_key"],
        unique=True,
        postgresql_where=sa.text("completion_idempotency_key IS NOT NULL"),
        sqlite_where=sa.text("completion_idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "lead_viewing_units",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("viewing_id", FK_TYPE, nullable=False),
        sa.Column("unit_id", FK_TYPE, nullable=False),
        sa.Column("unit_version", sa.Integer(), nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "viewing_id"],
            ["lead_viewings.tenant_id", "lead_viewings.id"],
            name="fk_lead_viewing_unit_tenant_viewing",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["units.tenant_id", "units.id"],
            name="fk_lead_viewing_unit_tenant_unit",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("viewing_id", "unit_id", name="uk_lead_viewing_unit"),
    )
    for column in ("tenant_id", "viewing_id", "unit_id"):
        op.create_index(f"ix_lead_viewing_units_{column}", "lead_viewing_units", [column])

    op.create_table(
        "lead_intent_applications",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("lead_id", FK_TYPE, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("approval_request_id", FK_TYPE, nullable=True),
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("updated_by", FK_TYPE, nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'PENDING', 'APPROVED', 'REJECTED', 'RETURNED', 'WITHDRAWN')",
            name="ck_lead_intent_application_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_lead_intent_application_tenant_park",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "lead_id"],
            ["leads.tenant_id", "leads.id"],
            name="fk_lead_intent_application_tenant_lead",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "approval_request_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_lead_intent_application_tenant_approval",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uk_lead_intent_applications_tenant_id_id"
        ),
        sa.UniqueConstraint("tenant_id", "lead_id", name="uk_lead_intent_application_lead"),
    )
    for column in ("tenant_id", "park_id", "lead_id", "approval_request_id"):
        op.create_index(
            f"ix_lead_intent_applications_{column}", "lead_intent_applications", [column]
        )

    op.create_table(
        "lead_intent_versions",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("application_id", FK_TYPE, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.DateTime(), nullable=False),
        sa.Column("proposed_unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="CNY"),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        *_timestamps(),
        sa.CheckConstraint("ends_on > starts_on", name="ck_lead_intent_date_order"),
        sa.CheckConstraint(
            "proposed_unit_price >= 0", name="ck_lead_intent_price_nonnegative"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "application_id"],
            ["lead_intent_applications.tenant_id", "lead_intent_applications.id"],
            name="fk_lead_intent_version_tenant_application",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", "version", name="uk_lead_intent_version"),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uk_lead_intent_versions_tenant_id_id"
        ),
    )
    for column in ("tenant_id", "application_id", "valid_until"):
        op.create_index(f"ix_lead_intent_versions_{column}", "lead_intent_versions", [column])

    op.create_table(
        "lead_intent_units",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("intent_version_id", FK_TYPE, nullable=False),
        sa.Column("unit_id", FK_TYPE, nullable=False),
        sa.Column("unit_version", sa.Integer(), nullable=False),
        sa.Column("requested_area", sa.Numeric(12, 2), nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "requested_area > 0", name="ck_lead_intent_unit_area_positive"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "intent_version_id"],
            ["lead_intent_versions.tenant_id", "lead_intent_versions.id"],
            name="fk_lead_intent_unit_tenant_version",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["units.tenant_id", "units.id"],
            name="fk_lead_intent_unit_tenant_unit",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("intent_version_id", "unit_id", name="uk_lead_intent_unit"),
    )
    for column in ("tenant_id", "intent_version_id", "unit_id"):
        op.create_index(f"ix_lead_intent_units_{column}", "lead_intent_units", [column])

    with op.batch_alter_table("lead_unit_locks") as batch:
        batch.add_column(sa.Column("intent_application_id", FK_TYPE, nullable=True))
        batch.add_column(sa.Column("intent_version_id", FK_TYPE, nullable=True))
        batch.create_index("ix_lead_unit_locks_intent_application_id", ["intent_application_id"])
        batch.create_index("ix_lead_unit_locks_intent_version_id", ["intent_version_id"])
        batch.create_foreign_key(
            "fk_lead_locks_tenant_intent_application",
            "lead_intent_applications",
            ["tenant_id", "intent_application_id"],
            ["tenant_id", "id"],
        )
        batch.create_foreign_key(
            "fk_lead_locks_tenant_intent_version",
            "lead_intent_versions",
            ["tenant_id", "intent_version_id"],
            ["tenant_id", "id"],
        )

    op.create_table(
        "lead_channels",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("secret_env_key", sa.String(128), nullable=False),
        sa.Column("previous_secret_env_key", sa.String(128), nullable=True),
        sa.Column("max_clock_skew_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("allow_auto_assign", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("mapping_json", sa.JSON(), nullable=True),
        sa.Column(
            "verification_status", sa.String(32), nullable=False, server_default="NOT_CONNECTED"
        ),
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("updated_by", FK_TYPE, nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "verification_status IN ('NOT_CONNECTED', 'LOCAL_CONTRACT_VERIFIED', 'SANDBOX_VERIFIED', 'LIVE_CONNECTED')",
            name="ck_lead_channel_verification_status",
        ),
        sa.CheckConstraint(
            "max_clock_skew_seconds >= 30 AND max_clock_skew_seconds <= 900",
            name="ck_lead_channel_clock_skew",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_lead_channel_tenant_park",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uk_lead_channels_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "code", name="uk_lead_channel_code"),
        sa.UniqueConstraint("public_id", name="uk_lead_channel_public_id"),
    )
    op.create_index("ix_lead_channels_tenant_id", "lead_channels", ["tenant_id"])
    op.create_index("ix_lead_channels_park_id", "lead_channels", ["park_id"])

    op.create_table(
        "lead_channel_inbox_events",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("channel_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("external_event_id", sa.String(128), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("payload_ciphertext", sa.Text(), nullable=True),
        sa.Column("payload_key_ref", sa.String(128), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="RECEIVED"),
        sa.Column("safe_preview_json", sa.JSON(), nullable=True),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("lead_id", FK_TYPE, nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("replay_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_replayed_at", sa.DateTime(), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('RECEIVED', 'ACCEPTED', 'QUARANTINED')",
            name="ck_lead_channel_event_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "channel_id"],
            ["lead_channels.tenant_id", "lead_channels.id"],
            name="fk_lead_channel_event_tenant_channel",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_lead_channel_event_tenant_park",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "lead_id"],
            ["leads.tenant_id", "leads.id"],
            name="fk_lead_channel_event_tenant_lead",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_id", "external_event_id", name="uk_lead_channel_event"),
    )
    for column in ("tenant_id", "channel_id", "park_id", "lead_id"):
        op.create_index(
            f"ix_lead_channel_inbox_events_{column}", "lead_channel_inbox_events", [column]
        )
    op.create_index(
        "ix_lead_channel_events_status",
        "lead_channel_inbox_events",
        ["tenant_id", "channel_id", "status", "received_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_lead_channel_events_status", table_name="lead_channel_inbox_events")
    op.drop_table("lead_channel_inbox_events")
    op.drop_table("lead_channels")

    with op.batch_alter_table("lead_unit_locks") as batch:
        batch.drop_constraint("fk_lead_locks_tenant_intent_version", type_="foreignkey")
        batch.drop_constraint("fk_lead_locks_tenant_intent_application", type_="foreignkey")
        batch.drop_index("ix_lead_unit_locks_intent_version_id")
        batch.drop_index("ix_lead_unit_locks_intent_application_id")
        batch.drop_column("intent_version_id")
        batch.drop_column("intent_application_id")

    op.drop_table("lead_intent_units")
    op.drop_table("lead_intent_versions")
    op.drop_table("lead_intent_applications")
    op.drop_table("lead_viewing_units")
    op.drop_table("lead_viewings")

    with op.batch_alter_table("lead_assignment_events") as batch:
        batch.drop_constraint(
            "fk_lead_assignment_event_tenant_rule_version", type_="foreignkey"
        )
        batch.drop_index("ix_lead_assignment_events_rule_version_id")
        batch.drop_column("decision_json")
        batch.drop_column("trigger")
        batch.drop_column("rule_version_id")

    op.drop_table("lead_assignment_members")
    op.drop_table("lead_assignment_rule_versions")
    op.drop_table("lead_assignment_rules")

    with op.batch_alter_table("leads") as batch:
        batch.drop_constraint("uk_leads_tenant_id_id", type_="unique")
    with op.batch_alter_table("approval_requests") as batch:
        batch.drop_constraint("uk_approval_requests_tenant_id_id", type_="unique")
    with op.batch_alter_table("units") as batch:
        batch.drop_constraint("uk_units_tenant_id_id", type_="unique")
    with op.batch_alter_table("parks") as batch:
        batch.drop_constraint("uk_parks_tenant_id_id", type_="unique")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("uk_users_tenant_id_id", type_="unique")

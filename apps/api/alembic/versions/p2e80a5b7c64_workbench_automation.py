"""event-driven configurable workbench automation

Revision ID: p2e80a5b7c64
Revises: o1d79e4f6a53
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "p2e80a5b7c64"
down_revision: str | None = "o1d79e4f6a53"
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
        "business_events",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=True),
        sa.Column("event_type", sa.String(96), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(96), nullable=False),
        sa.Column("idempotency_key", sa.String(192), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("payload_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        *_identity_columns(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uk_business_event_idempotency"
        ),
    )
    for column in ("tenant_id", "park_id", "event_type"):
        op.create_index(f"ix_business_events_{column}", "business_events", [column])
    op.create_index(
        "ix_business_event_dispatch", "business_events", ["tenant_id", "occurred_at", "id"]
    )

    op.create_table(
        "event_consumer_logs",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("event_id", FK_TYPE, nullable=False),
        sa.Column("consumer_name", sa.String(96), nullable=False),
        sa.Column("generation", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(16), server_default="PENDING", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("claimed_by", sa.String(96), nullable=True),
        sa.Column("claimed_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.String(1000), nullable=True),
        *_identity_columns(),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCEEDED','RETRY','DEAD')",
            name="ck_event_consumer_status",
        ),
        sa.CheckConstraint("attempt_count >= 0 AND max_attempts BETWEEN 1 AND 10", name="ck_event_consumer_attempts"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["event_id"], ["business_events.id"]),
        sa.UniqueConstraint(
            "tenant_id",
            "event_id",
            "consumer_name",
            "generation",
            name="uk_event_consumer_generation",
        ),
    )
    op.create_index("ix_event_consumer_logs_tenant_id", "event_consumer_logs", ["tenant_id"])
    op.create_index("ix_event_consumer_logs_event_id", "event_consumer_logs", ["event_id"])
    op.create_index(
        "ix_event_consumer_claim",
        "event_consumer_logs",
        ["tenant_id", "consumer_name", "status", "next_attempt_at"],
    )

    op.create_table(
        "automation_rules",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), server_default="ACTIVE", nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("updated_by", FK_TYPE, nullable=True),
        *_identity_columns(),
        sa.CheckConstraint("status IN ('ACTIVE','RETIRED')", name="ck_automation_rule_status"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.UniqueConstraint("tenant_id", "code", name="uk_automation_rule_code"),
    )
    op.create_index("ix_automation_rules_tenant_id", "automation_rules", ["tenant_id"])
    op.create_index("ix_automation_rules_park_id", "automation_rules", ["park_id"])

    op.create_table(
        "automation_rule_versions",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("rule_id", FK_TYPE, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), server_default="DRAFT", nullable=False),
        sa.Column("event_type", sa.String(96), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("conditions_json", sa.Text(), server_default="[]", nullable=False),
        sa.Column("actions_json", sa.Text(), server_default="[]", nullable=False),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("published_by", FK_TYPE, nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        *_identity_columns(),
        sa.CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','RETIRED')",
            name="ck_automation_rule_version_status",
        ),
        sa.CheckConstraint("priority BETWEEN 0 AND 1000", name="ck_automation_rule_priority"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["rule_id"], ["automation_rules.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"]),
        sa.UniqueConstraint("rule_id", "version", name="uk_automation_rule_version"),
    )
    op.create_index(
        "ix_automation_rule_versions_tenant_id", "automation_rule_versions", ["tenant_id"]
    )
    op.create_index(
        "ix_automation_rule_versions_rule_id", "automation_rule_versions", ["rule_id"]
    )
    op.create_index(
        "ix_automation_rule_match",
        "automation_rule_versions",
        ["tenant_id", "event_type", "status"],
    )
    op.create_index(
        "uk_automation_rule_one_draft",
        "automation_rule_versions",
        ["rule_id"],
        unique=True,
        postgresql_where=sa.text("status = 'DRAFT'"),
        sqlite_where=sa.text("status = 'DRAFT'"),
    )

    op.create_table(
        "automation_executions",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("event_id", FK_TYPE, nullable=False),
        sa.Column("rule_version_id", FK_TYPE, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("matched", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("action_results_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        *_identity_columns(),
        sa.CheckConstraint(
            "status IN ('MATCHED','NOT_MATCHED','SUCCEEDED','FAILED')",
            name="ck_automation_execution_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["event_id"], ["business_events.id"]),
        sa.ForeignKeyConstraint(["rule_version_id"], ["automation_rule_versions.id"]),
        sa.UniqueConstraint(
            "tenant_id", "event_id", "rule_version_id", name="uk_automation_execution"
        ),
    )
    for column in ("tenant_id", "event_id", "rule_version_id"):
        op.create_index(
            f"ix_automation_executions_{column}", "automation_executions", [column]
        )
    op.create_index(
        "ix_automation_execution_query",
        "automation_executions",
        ["tenant_id", "status", "created_at"],
    )

    op.create_table(
        "in_app_notifications",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=True),
        sa.Column("recipient_user_id", FK_TYPE, nullable=False),
        sa.Column("event_id", FK_TYPE, nullable=True),
        sa.Column("idempotency_key", sa.String(192), nullable=False),
        sa.Column("category", sa.String(64), server_default="SYSTEM", nullable=False),
        sa.Column("channel", sa.String(16), server_default="IN_APP", nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("deep_link", sa.String(512), nullable=True),
        sa.Column("status", sa.String(16), server_default="UNREAD", nullable=False),
        sa.Column("delivered_at", sa.DateTime(), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        *_identity_columns(),
        sa.CheckConstraint(
            "status IN ('UNREAD','READ','ARCHIVED')", name="ck_in_app_notification_status"
        ),
        sa.CheckConstraint("channel = 'IN_APP'", name="ck_in_app_notification_channel"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["event_id"], ["business_events.id"]),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uk_in_app_notification_idempotency"
        ),
    )
    for column in ("tenant_id", "park_id", "recipient_user_id"):
        op.create_index(
            f"ix_in_app_notifications_{column}", "in_app_notifications", [column]
        )
    op.create_index(
        "ix_in_app_notification_inbox",
        "in_app_notifications",
        ["tenant_id", "recipient_user_id", "status", "created_at"],
    )

    op.create_table(
        "scheduler_definitions",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("handler_key", sa.String(96), nullable=False),
        sa.Column("parameters_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("cadence_seconds", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("concurrency_policy", sa.String(16), server_default="FORBID", nullable=False),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), server_default="300", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("updated_by", FK_TYPE, nullable=True),
        *_identity_columns(),
        sa.CheckConstraint(
            "concurrency_policy IN ('FORBID','ALLOW')", name="ck_scheduler_concurrency_policy"
        ),
        sa.CheckConstraint(
            "cadence_seconds BETWEEN 10 AND 2678400", name="ck_scheduler_cadence"
        ),
        sa.CheckConstraint(
            "timeout_seconds BETWEEN 10 AND 86400 AND max_attempts BETWEEN 1 AND 10",
            name="ck_scheduler_limits",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.UniqueConstraint("tenant_id", "code", name="uk_scheduler_definition_code"),
    )
    op.create_index(
        "ix_scheduler_definitions_tenant_id", "scheduler_definitions", ["tenant_id"]
    )
    op.create_index(
        "ix_scheduler_due",
        "scheduler_definitions",
        ["tenant_id", "enabled", "next_run_at"],
    )

    op.create_table(
        "scheduler_runs",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("schedule_id", FK_TYPE, nullable=False),
        sa.Column("fire_at", sa.DateTime(), nullable=False),
        sa.Column("generation", sa.Integer(), server_default="1", nullable=False),
        sa.Column("idempotency_key", sa.String(192), nullable=False),
        sa.Column("status", sa.String(16), server_default="RUNNING", nullable=False),
        sa.Column("claim_token", sa.String(96), nullable=False),
        sa.Column("claimed_by", sa.String(96), nullable=False),
        sa.Column("attempt_no", sa.Integer(), server_default="1", nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.String(1000), nullable=True),
        *_identity_columns(),
        sa.CheckConstraint(
            "status IN ('RUNNING','SUCCEEDED','FAILED','TIMED_OUT')",
            name="ck_scheduler_run_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["schedule_id"], ["scheduler_definitions.id"]),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uk_scheduler_run_idempotency"
        ),
    )
    op.create_index("ix_scheduler_runs_tenant_id", "scheduler_runs", ["tenant_id"])
    op.create_index("ix_scheduler_runs_schedule_id", "scheduler_runs", ["schedule_id"])
    op.create_index(
        "ix_scheduler_run_query", "scheduler_runs", ["tenant_id", "schedule_id", "created_at"]
    )

    op.create_table(
        "workbench_layouts",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("owner_user_id", FK_TYPE, nullable=True),
        sa.Column("role_id", FK_TYPE, nullable=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("updated_by", FK_TYPE, nullable=True),
        *_identity_columns(),
        sa.CheckConstraint(
            "((owner_user_id IS NOT NULL AND role_id IS NULL) OR "
            "(owner_user_id IS NULL AND role_id IS NOT NULL))",
            name="ck_workbench_layout_owner",
        ),
        sa.CheckConstraint("priority BETWEEN 0 AND 1000", name="ck_workbench_layout_priority"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.UniqueConstraint("tenant_id", "owner_user_id", name="uk_workbench_layout_user"),
        sa.UniqueConstraint("tenant_id", "role_id", name="uk_workbench_layout_role"),
    )
    for column in ("tenant_id", "owner_user_id", "role_id"):
        op.create_index(f"ix_workbench_layouts_{column}", "workbench_layouts", [column])

    op.create_table(
        "workbench_widgets",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("layout_id", FK_TYPE, nullable=False),
        sa.Column("widget_key", sa.String(64), nullable=False),
        sa.Column("position_x", sa.Integer(), nullable=False),
        sa.Column("position_y", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("visible", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("config_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        *_identity_columns(),
        sa.CheckConstraint(
            "position_x BETWEEN 0 AND 11 AND position_y BETWEEN 0 AND 99 AND "
            "width BETWEEN 1 AND 12 AND height BETWEEN 1 AND 12 AND position_x + width <= 12",
            name="ck_workbench_widget_grid",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["layout_id"], ["workbench_layouts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("layout_id", "widget_key", name="uk_workbench_layout_widget"),
    )
    op.create_index("ix_workbench_widgets_tenant_id", "workbench_widgets", ["tenant_id"])
    op.create_index("ix_workbench_widgets_layout_id", "workbench_widgets", ["layout_id"])

    with op.batch_alter_table("work_items") as batch_op:
        batch_op.add_column(sa.Column("deep_link", sa.String(512), nullable=True))
        batch_op.add_column(
            sa.Column("escalation_level", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(sa.Column("reassigned_from_user_id", FK_TYPE, nullable=True))
        batch_op.add_column(sa.Column("last_event_id", FK_TYPE, nullable=True))
        batch_op.add_column(
            sa.Column("source_owned", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch_op.add_column(
            sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False)
        )
        batch_op.create_foreign_key(
            "fk_work_items_reassigned_from_user_id",
            "users",
            ["reassigned_from_user_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_work_items_last_event_id", "business_events", ["last_event_id"], ["id"]
        )
        batch_op.create_check_constraint(
            "ck_work_item_escalation_version", "escalation_level >= 0 AND lock_version >= 1"
        )
    op.create_index("ix_work_items_last_event_id", "work_items", ["last_event_id"])


def downgrade() -> None:
    op.drop_index("ix_work_items_last_event_id", table_name="work_items")
    with op.batch_alter_table("work_items") as batch_op:
        batch_op.drop_constraint("ck_work_item_escalation_version", type_="check")
        batch_op.drop_constraint("fk_work_items_last_event_id", type_="foreignkey")
        batch_op.drop_constraint("fk_work_items_reassigned_from_user_id", type_="foreignkey")
        batch_op.drop_column("lock_version")
        batch_op.drop_column("source_owned")
        batch_op.drop_column("last_event_id")
        batch_op.drop_column("reassigned_from_user_id")
        batch_op.drop_column("escalation_level")
        batch_op.drop_column("deep_link")

    op.drop_index("ix_workbench_widgets_layout_id", table_name="workbench_widgets")
    op.drop_index("ix_workbench_widgets_tenant_id", table_name="workbench_widgets")
    op.drop_table("workbench_widgets")
    for column in ("role_id", "owner_user_id", "tenant_id"):
        op.drop_index(f"ix_workbench_layouts_{column}", table_name="workbench_layouts")
    op.drop_table("workbench_layouts")
    op.drop_index("ix_scheduler_run_query", table_name="scheduler_runs")
    op.drop_index("ix_scheduler_runs_schedule_id", table_name="scheduler_runs")
    op.drop_index("ix_scheduler_runs_tenant_id", table_name="scheduler_runs")
    op.drop_table("scheduler_runs")
    op.drop_index("ix_scheduler_due", table_name="scheduler_definitions")
    op.drop_index("ix_scheduler_definitions_tenant_id", table_name="scheduler_definitions")
    op.drop_table("scheduler_definitions")
    op.drop_index("ix_in_app_notification_inbox", table_name="in_app_notifications")
    for column in ("recipient_user_id", "park_id", "tenant_id"):
        op.drop_index(f"ix_in_app_notifications_{column}", table_name="in_app_notifications")
    op.drop_table("in_app_notifications")
    op.drop_index("ix_automation_execution_query", table_name="automation_executions")
    for column in ("rule_version_id", "event_id", "tenant_id"):
        op.drop_index(f"ix_automation_executions_{column}", table_name="automation_executions")
    op.drop_table("automation_executions")
    op.drop_index("uk_automation_rule_one_draft", table_name="automation_rule_versions")
    op.drop_index("ix_automation_rule_match", table_name="automation_rule_versions")
    op.drop_index("ix_automation_rule_versions_rule_id", table_name="automation_rule_versions")
    op.drop_index("ix_automation_rule_versions_tenant_id", table_name="automation_rule_versions")
    op.drop_table("automation_rule_versions")
    op.drop_index("ix_automation_rules_park_id", table_name="automation_rules")
    op.drop_index("ix_automation_rules_tenant_id", table_name="automation_rules")
    op.drop_table("automation_rules")
    op.drop_index("ix_event_consumer_claim", table_name="event_consumer_logs")
    op.drop_index("ix_event_consumer_logs_event_id", table_name="event_consumer_logs")
    op.drop_index("ix_event_consumer_logs_tenant_id", table_name="event_consumer_logs")
    op.drop_table("event_consumer_logs")
    op.drop_index("ix_business_event_dispatch", table_name="business_events")
    for column in ("event_type", "park_id", "tenant_id"):
        op.drop_index(f"ix_business_events_{column}", table_name="business_events")
    op.drop_table("business_events")

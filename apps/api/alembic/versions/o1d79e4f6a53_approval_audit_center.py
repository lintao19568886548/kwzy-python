"""versioned approval orchestration and tamper-evident audit ledger

Revision ID: o1d79e4f6a53
Revises: n0c68d3e5f42
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "o1d79e4f6a53"
down_revision: str | None = "n0c68d3e5f42"
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
        "approval_definitions",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("biz_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), server_default="ACTIVE", nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lock_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("updated_by", FK_TYPE, nullable=True),
        *_identity_columns(),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'RETIRED')",
            name="ck_approval_definition_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.UniqueConstraint("tenant_id", "code", name="uk_approval_definition_code"),
    )
    for column in ("tenant_id", "park_id"):
        op.create_index(
            f"ix_approval_definitions_{column}",
            "approval_definitions",
            [column],
        )
    op.create_index(
        "ix_approval_definitions_tenant_biz",
        "approval_definitions",
        ["tenant_id", "biz_type", "status"],
    )

    op.create_table(
        "approval_definition_versions",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("definition_id", FK_TYPE, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), server_default="DRAFT", nullable=False),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("published_by", FK_TYPE, nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        *_identity_columns(),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'PUBLISHED', 'RETIRED')",
            name="ck_approval_definition_version_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["definition_id"], ["approval_definitions.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"]),
        sa.UniqueConstraint(
            "definition_id",
            "version",
            name="uk_approval_definition_version",
        ),
    )
    op.create_index(
        "ix_approval_definition_versions_tenant_id",
        "approval_definition_versions",
        ["tenant_id"],
    )
    op.create_index(
        "ix_approval_definition_versions_definition_id",
        "approval_definition_versions",
        ["definition_id"],
    )
    op.create_index(
        "uk_approval_definition_one_draft",
        "approval_definition_versions",
        ["definition_id"],
        unique=True,
        postgresql_where=sa.text("status = 'DRAFT'"),
        sqlite_where=sa.text("status = 'DRAFT'"),
    )

    op.create_table(
        "approval_definition_steps",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("version_id", FK_TYPE, nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("approval_mode", sa.String(8), server_default="ANY", nullable=False),
        sa.Column("min_approvals", sa.Integer(), server_default="1", nullable=False),
        sa.Column("sla_hours", sa.Integer(), server_default="24", nullable=False),
        *_identity_columns(),
        sa.CheckConstraint(
            "approval_mode IN ('ANY', 'ALL')",
            name="ck_approval_step_mode",
        ),
        sa.CheckConstraint("step_order > 0", name="ck_approval_step_order_positive"),
        sa.CheckConstraint("min_approvals > 0", name="ck_approval_step_min_positive"),
        sa.CheckConstraint("sla_hours > 0", name="ck_approval_step_sla_positive"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["version_id"], ["approval_definition_versions.id"]),
        sa.UniqueConstraint("version_id", "step_order", name="uk_approval_step_order"),
    )
    op.create_index(
        "ix_approval_definition_steps_tenant_id",
        "approval_definition_steps",
        ["tenant_id"],
    )
    op.create_index(
        "ix_approval_definition_steps_version_id",
        "approval_definition_steps",
        ["version_id"],
    )

    op.create_table(
        "approval_step_assignees",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("step_id", FK_TYPE, nullable=False),
        sa.Column("user_id", FK_TYPE, nullable=True),
        sa.Column("role_id", FK_TYPE, nullable=True),
        *_identity_columns(),
        sa.CheckConstraint(
            "(user_id IS NOT NULL AND role_id IS NULL) OR "
            "(user_id IS NULL AND role_id IS NOT NULL)",
            name="ck_approval_assignee_exactly_one",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["step_id"], ["approval_definition_steps.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.UniqueConstraint("step_id", "user_id", name="uk_approval_step_user"),
        sa.UniqueConstraint("step_id", "role_id", name="uk_approval_step_role"),
    )
    for column in ("tenant_id", "step_id"):
        op.create_index(
            f"ix_approval_step_assignees_{column}",
            "approval_step_assignees",
            [column],
        )

    with op.batch_alter_table("approval_requests") as batch_op:
        batch_op.add_column(sa.Column("definition_version_id", FK_TYPE, nullable=True))
        batch_op.add_column(sa.Column("request_no", sa.String(64), nullable=True))
        batch_op.add_column(
            sa.Column("priority", sa.String(16), server_default="MEDIUM", nullable=False)
        )
        batch_op.add_column(sa.Column("current_step_order", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("round_no", sa.Integer(), server_default="1", nullable=False)
        )
        batch_op.add_column(sa.Column("due_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("submitted_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("snapshot_json", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("lock_version", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(sa.Column("idempotency_key", sa.String(64), nullable=True))
        batch_op.add_column(
            sa.Column(
                "compatibility_mode",
                sa.String(32),
                server_default="NATIVE",
                nullable=False,
            )
        )
        batch_op.create_foreign_key(
            "fk_approval_requests_definition_version",
            "approval_definition_versions",
            ["definition_version_id"],
            ["id"],
        )
        batch_op.create_check_constraint(
            "ck_approval_request_status_v2",
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'RETURNED', 'WITHDRAWN')",
        )
        batch_op.create_check_constraint(
            "ck_approval_request_priority",
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')",
        )
    op.execute(
        sa.text(
            "UPDATE approval_requests SET "
            "compatibility_mode = 'LEGACY_COMPAT', submitted_at = created_at "
            "WHERE definition_version_id IS NULL"
        )
    )
    op.create_index(
        "ix_approval_requests_definition_version_id",
        "approval_requests",
        ["definition_version_id"],
    )
    op.create_index(
        "uk_approval_request_no",
        "approval_requests",
        ["tenant_id", "request_no"],
        unique=True,
        postgresql_where=sa.text("request_no IS NOT NULL"),
        sqlite_where=sa.text("request_no IS NOT NULL"),
    )
    op.create_index(
        "uk_approval_submit_idempotency",
        "approval_requests",
        ["tenant_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        sqlite_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "approval_delegations",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("grantor_user_id", FK_TYPE, nullable=False),
        sa.Column("delegate_user_id", FK_TYPE, nullable=False),
        sa.Column("biz_type", sa.String(64), nullable=True),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(16), server_default="ACTIVE", nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_by", FK_TYPE, nullable=True),
        *_identity_columns(),
        sa.CheckConstraint(
            "grantor_user_id <> delegate_user_id",
            name="ck_delegation_not_self",
        ),
        sa.CheckConstraint("ends_at > starts_at", name="ck_delegation_time_order"),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'REVOKED')",
            name="ck_delegation_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["grantor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["delegate_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["revoked_by"], ["users.id"]),
    )
    for column in ("tenant_id", "grantor_user_id", "delegate_user_id"):
        op.create_index(
            f"ix_approval_delegations_{column}",
            "approval_delegations",
            [column],
        )
    op.create_index(
        "ix_approval_delegation_effective",
        "approval_delegations",
        ["tenant_id", "grantor_user_id", "status", "starts_at", "ends_at"],
    )

    op.create_table(
        "approval_tasks",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("approval_id", FK_TYPE, nullable=False),
        sa.Column("step_id", FK_TYPE, nullable=False),
        sa.Column("round_no", sa.Integer(), server_default="1", nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("assignee_user_id", FK_TYPE, nullable=False),
        sa.Column("status", sa.String(16), server_default="PENDING", nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("decision_remark", sa.Text(), nullable=True),
        sa.Column("acted_by_user_id", FK_TYPE, nullable=True),
        sa.Column("delegation_id", FK_TYPE, nullable=True),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        sa.Column("escalated_at", sa.DateTime(), nullable=True),
        *_identity_columns(),
        sa.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'RETURNED', 'SKIPPED', 'CANCELLED')",
            name="ck_approval_task_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["approval_id"], ["approval_requests.id"]),
        sa.ForeignKeyConstraint(["step_id"], ["approval_definition_steps.id"]),
        sa.ForeignKeyConstraint(["assignee_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["acted_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["delegation_id"], ["approval_delegations.id"]),
        sa.UniqueConstraint(
            "approval_id",
            "round_no",
            "step_order",
            "assignee_user_id",
            name="uk_approval_task_candidate",
        ),
    )
    for column in ("tenant_id", "approval_id", "step_id", "assignee_user_id"):
        op.create_index(
            f"ix_approval_tasks_{column}",
            "approval_tasks",
            [column],
        )
    op.create_index(
        "uk_approval_task_decision_key",
        "approval_tasks",
        ["tenant_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        sqlite_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "ix_approval_tasks_inbox",
        "approval_tasks",
        ["tenant_id", "assignee_user_id", "status", "due_at"],
    )
    # APPROVAL_TASK is introduced by this revision.  A disposable downgrade
    # intentionally removes the task table; clean any matching projection so a
    # subsequent re-upgrade cannot reuse task ids and collide with stale work
    # items.  No pre-revision business row can legitimately own this source.
    op.execute("DELETE FROM work_items WHERE source_type = 'APPROVAL_TASK'")

    with op.batch_alter_table("approval_events") as batch_op:
        batch_op.add_column(
            sa.Column("round_no", sa.Integer(), server_default="1", nullable=False)
        )
        batch_op.add_column(sa.Column("step_order", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("task_id", FK_TYPE, nullable=True))
        batch_op.add_column(sa.Column("original_assignee_user_id", FK_TYPE, nullable=True))
        batch_op.add_column(sa.Column("idempotency_key", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("detail_json", sa.JSON(), nullable=True))
        batch_op.create_foreign_key(
            "fk_approval_events_task",
            "approval_tasks",
            ["task_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_approval_events_original_assignee",
            "users",
            ["original_assignee_user_id"],
            ["id"],
        )
    op.create_index("ix_approval_events_task_id", "approval_events", ["task_id"])
    op.create_index(
        "uk_approval_event_idempotency",
        "approval_events",
        ["tenant_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        sqlite_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "audit_chain_heads",
        sa.Column("tenant_id", FK_TYPE, primary_key=True, autoincrement=False),
        sa.Column("sequence_no", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("last_hash", sa.String(64), server_default="GENESIS", nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
    )
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.add_column(sa.Column("sequence_no", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("previous_hash", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("record_hash", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("integrity_version", sa.Integer(), nullable=True))
    op.create_index(
        "uk_audit_logs_tenant_sequence",
        "audit_logs",
        ["tenant_id", "sequence_no"],
        unique=True,
        postgresql_where=sa.text("sequence_no IS NOT NULL"),
        sqlite_where=sa.text("sequence_no IS NOT NULL"),
    )
    op.create_index(
        "ix_audit_logs_tenant_action",
        "audit_logs",
        ["tenant_id", "action", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_tenant_action", table_name="audit_logs")
    op.drop_index("uk_audit_logs_tenant_sequence", table_name="audit_logs")
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.drop_column("integrity_version")
        batch_op.drop_column("record_hash")
        batch_op.drop_column("previous_hash")
        batch_op.drop_column("sequence_no")
    op.drop_table("audit_chain_heads")

    op.drop_index("uk_approval_event_idempotency", table_name="approval_events")
    op.drop_index("ix_approval_events_task_id", table_name="approval_events")
    with op.batch_alter_table("approval_events") as batch_op:
        batch_op.drop_constraint("fk_approval_events_original_assignee", type_="foreignkey")
        batch_op.drop_constraint("fk_approval_events_task", type_="foreignkey")
        batch_op.drop_column("detail_json")
        batch_op.drop_column("idempotency_key")
        batch_op.drop_column("original_assignee_user_id")
        batch_op.drop_column("task_id")
        batch_op.drop_column("step_order")
        batch_op.drop_column("round_no")

    # Projections are owned by approval_tasks and must not survive the table
    # they reference.  Keeping them would make the documented down/up rehearsal
    # fail later through uk_work_item_source when task ids restart.
    op.execute("DELETE FROM work_items WHERE source_type = 'APPROVAL_TASK'")

    op.drop_index("ix_approval_tasks_inbox", table_name="approval_tasks")
    op.drop_index("uk_approval_task_decision_key", table_name="approval_tasks")
    for column in reversed(("tenant_id", "approval_id", "step_id", "assignee_user_id")):
        op.drop_index(f"ix_approval_tasks_{column}", table_name="approval_tasks")
    op.drop_table("approval_tasks")

    op.drop_index("ix_approval_delegation_effective", table_name="approval_delegations")
    for column in reversed(("tenant_id", "grantor_user_id", "delegate_user_id")):
        op.drop_index(f"ix_approval_delegations_{column}", table_name="approval_delegations")
    op.drop_table("approval_delegations")

    op.drop_index("uk_approval_submit_idempotency", table_name="approval_requests")
    op.drop_index("uk_approval_request_no", table_name="approval_requests")
    op.drop_index(
        "ix_approval_requests_definition_version_id",
        table_name="approval_requests",
    )
    with op.batch_alter_table("approval_requests") as batch_op:
        batch_op.drop_constraint("ck_approval_request_priority", type_="check")
        batch_op.drop_constraint("ck_approval_request_status_v2", type_="check")
        batch_op.drop_constraint(
            "fk_approval_requests_definition_version",
            type_="foreignkey",
        )
        batch_op.drop_column("compatibility_mode")
        batch_op.drop_column("idempotency_key")
        batch_op.drop_column("lock_version")
        batch_op.drop_column("snapshot_json")
        batch_op.drop_column("completed_at")
        batch_op.drop_column("submitted_at")
        batch_op.drop_column("due_at")
        batch_op.drop_column("round_no")
        batch_op.drop_column("current_step_order")
        batch_op.drop_column("priority")
        batch_op.drop_column("request_no")
        batch_op.drop_column("definition_version_id")

    for column in reversed(("tenant_id", "step_id")):
        op.drop_index(f"ix_approval_step_assignees_{column}", table_name="approval_step_assignees")
    op.drop_table("approval_step_assignees")
    op.drop_index(
        "ix_approval_definition_steps_version_id",
        table_name="approval_definition_steps",
    )
    op.drop_index(
        "ix_approval_definition_steps_tenant_id",
        table_name="approval_definition_steps",
    )
    op.drop_table("approval_definition_steps")
    op.drop_index(
        "uk_approval_definition_one_draft",
        table_name="approval_definition_versions",
    )
    op.drop_index(
        "ix_approval_definition_versions_definition_id",
        table_name="approval_definition_versions",
    )
    op.drop_index(
        "ix_approval_definition_versions_tenant_id",
        table_name="approval_definition_versions",
    )
    op.drop_table("approval_definition_versions")
    op.drop_index("ix_approval_definitions_tenant_biz", table_name="approval_definitions")
    for column in reversed(("tenant_id", "park_id")):
        op.drop_index(f"ix_approval_definitions_{column}", table_name="approval_definitions")
    op.drop_table("approval_definitions")

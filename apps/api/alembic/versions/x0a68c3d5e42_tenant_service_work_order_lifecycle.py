"""tenant service work-order quotation acceptance lifecycle

Revision ID: x0a68c3d5e42
Revises: w9f57b2c4d31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "x0a68c3d5e42"
down_revision: str | None = "w9f57b2c4d31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
FK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def upgrade() -> None:
    op.create_table(
        "tenant_service_principals",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("user_id", FK_TYPE, nullable=False),
        sa.Column("party_id", FK_TYPE, nullable=False),
        sa.Column("status", sa.String(16), server_default="ACTIVE", nullable=False),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("disabled_by", FK_TYPE, nullable=True),
        sa.Column("disabled_at", sa.DateTime(), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["party_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["disabled_by"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_tenant_service_principal_user",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_tenant_service_principal_party",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','DISABLED')", name="ck_tenant_service_principal_status"
        ),
        sa.UniqueConstraint("tenant_id", "user_id", name="uk_tenant_service_principal_user"),
        sa.UniqueConstraint("tenant_id", "id", name="uk_tenant_service_principal_tenant_id_id"),
    )
    op.create_index(
        "ix_tenant_service_principal_party",
        "tenant_service_principals",
        ["tenant_id", "party_id", "status"],
    )

    op.create_table(
        "tenant_service_principal_parks",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("principal_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["tenant_service_principals.tenant_id", "tenant_service_principals.id"],
            name="fk_tenant_service_principal_park_principal",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_tenant_service_principal_park_park",
        ),
        sa.UniqueConstraint(
            "tenant_id", "principal_id", "park_id", name="uk_tenant_service_principal_park"
        ),
    )

    op.create_table(
        "work_order_assignment_rules",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), server_default="DRAFT", nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("priority", sa.String(16), nullable=True),
        sa.Column("assignee_user_id", FK_TYPE, nullable=False),
        sa.Column("response_minutes", sa.Integer(), nullable=False),
        sa.Column("resolution_minutes", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="100", nullable=False),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("published_by", FK_TYPE, nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("retired_by", FK_TYPE, nullable=True),
        sa.Column("retired_at", sa.DateTime(), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["assignee_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["retired_by"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_work_order_rule_park",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignee_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_work_order_rule_assignee",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','RETIRED')", name="ck_work_order_rule_status"
        ),
        sa.CheckConstraint("response_minutes > 0", name="ck_work_order_rule_response_minutes"),
        sa.CheckConstraint("resolution_minutes > 0", name="ck_work_order_rule_resolution_minutes"),
        sa.CheckConstraint("sort_order >= 0", name="ck_work_order_rule_sort_order"),
        sa.UniqueConstraint("tenant_id", "code", "version_no", name="uk_work_order_rule_version"),
        sa.UniqueConstraint("tenant_id", "id", name="uk_work_order_rules_tenant_id_id"),
    )
    op.create_index(
        "uk_work_order_rule_published",
        "work_order_assignment_rules",
        ["tenant_id", "code"],
        unique=True,
        postgresql_where=sa.text("status = 'PUBLISHED'"),
        sqlite_where=sa.text("status = 'PUBLISHED'"),
    )
    op.create_index(
        "ix_work_order_rule_match",
        "work_order_assignment_rules",
        ["tenant_id", "status", "park_id", "category", "priority", "sort_order"],
    )

    with op.batch_alter_table("work_orders") as batch:
        batch.add_column(sa.Column("order_no", sa.String(64), nullable=True))
        batch.add_column(sa.Column("party_id", FK_TYPE, nullable=True))
        batch.add_column(sa.Column("contact_id", FK_TYPE, nullable=True))
        batch.add_column(sa.Column("contact_name", sa.String(64), nullable=True))
        batch.add_column(sa.Column("contact_phone_masked", sa.String(32), nullable=True))
        batch.add_column(
            sa.Column("quote_required", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch.add_column(sa.Column("assignment_rule_id", FK_TYPE, nullable=True))
        batch.add_column(sa.Column("assignment_rule_version", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("response_due_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("resolution_due_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("first_responded_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("submitted_for_acceptance_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("closed_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("resolution_summary", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column(
                "evidence_refs_json",
                sa.JSON(),
                server_default=sa.text("'[]'"),
                nullable=False,
            )
        )
        batch.add_column(sa.Column("no_evidence_reason", sa.String(512), nullable=True))
        batch.add_column(sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False))

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("UPDATE work_orders SET order_no = 'WO-MIG-' || id::text")
    else:
        op.execute("UPDATE work_orders SET order_no = 'WO-MIG-' || CAST(id AS TEXT)")
    op.execute(
        "UPDATE work_orders SET status = CASE "
        "WHEN status IN ('OPEN','NEW','PENDING') THEN 'SUBMITTED' "
        "WHEN status IN ('DONE','CLOSED') THEN 'COMPLETED' "
        "ELSE status END"
    )

    with op.batch_alter_table("work_orders") as batch:
        batch.alter_column("order_no", existing_type=sa.String(64), nullable=False)
        batch.alter_column(
            "status", existing_type=sa.String(32), server_default="SUBMITTED", nullable=False
        )
        batch.create_check_constraint(
            "ck_work_orders_status_v2",
            "status IN ('SUBMITTED','ASSIGNED','IN_PROGRESS','WAITING_QUOTE_APPROVAL',"
            "'IN_PROGRESS_AFTER_QUOTE','WAITING_ACCEPTANCE','COMPLETED','CANCELLED')",
        )
        batch.create_check_constraint(
            "ck_work_orders_priority_v2", "priority IN ('LOW','MEDIUM','HIGH','URGENT')"
        )
        batch.create_check_constraint("ck_work_orders_lock_version_v2", "lock_version > 0")
        batch.create_unique_constraint("uk_work_orders_tenant_id_id", ["tenant_id", "id"])
        batch.create_unique_constraint(
            "uk_work_orders_tenant_order_no", ["tenant_id", "order_no"]
        )
        batch.create_foreign_key("fk_work_orders_party_id_v2", "parties", ["party_id"], ["id"])
        batch.create_foreign_key(
            "fk_work_orders_contact_id_v2", "party_contacts", ["contact_id"], ["id"]
        )
        batch.create_foreign_key(
            "fk_work_orders_tenant_park_v2",
            "parks",
            ["tenant_id", "park_id"],
            ["tenant_id", "id"],
            ondelete="RESTRICT",
        )
        batch.create_foreign_key(
            "fk_work_orders_tenant_party_v2",
            "parties",
            ["tenant_id", "party_id"],
            ["tenant_id", "id"],
            ondelete="RESTRICT",
        )
        batch.create_foreign_key(
            "fk_work_orders_tenant_assignee_v2",
            "users",
            ["tenant_id", "assignee_user_id"],
            ["tenant_id", "id"],
            ondelete="RESTRICT",
        )
        batch.create_index(
            "uk_work_orders_source_v2",
            ["tenant_id", "source_type", "source_id"],
            unique=True,
            postgresql_where=sa.text("source_id <> ''"),
            sqlite_where=sa.text("source_id <> ''"),
        )
        batch.create_index(
            "ix_work_orders_service_queue_v2", ["tenant_id", "park_id", "status", "priority"]
        )
        batch.create_index("ix_work_orders_party_v2", ["tenant_id", "party_id", "created_at"])
        batch.create_index(
            "ix_work_orders_sla_v2",
            ["tenant_id", "status", "response_due_at", "resolution_due_at"],
        )

    op.create_table(
        "work_order_events",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("work_order_id", FK_TYPE, nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor_type", sa.String(16), nullable=False),
        sa.Column("actor_user_id", FK_TYPE, nullable=True),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=True),
        sa.Column("reason", sa.String(1000), nullable=True),
        sa.Column("detail_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "work_order_id"],
            ["work_orders.tenant_id", "work_orders.id"],
            name="fk_work_order_event_order",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "actor_type IN ('STAFF','TENANT','SYSTEM','MIGRATION')",
            name="ck_work_order_event_actor_type",
        ),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uk_work_order_event_key"),
    )
    op.create_index(
        "ix_work_order_event_timeline",
        "work_order_events",
        ["tenant_id", "work_order_id", "occurred_at"],
    )

    op.create_table(
        "work_order_quotes",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("work_order_id", FK_TYPE, nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), server_default="DRAFT", nullable=False),
        sa.Column("currency", sa.String(3), server_default="CNY", nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("remark", sa.String(1000), nullable=True),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("submitted_by", FK_TYPE, nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("decided_by_user_id", FK_TYPE, nullable=True),
        sa.Column("decided_by_party_id", FK_TYPE, nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("decision_remark", sa.String(1000), nullable=True),
        sa.Column("decision_key", sa.String(128), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["decided_by_party_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "work_order_id"],
            ["work_orders.tenant_id", "work_orders.id"],
            name="fk_work_order_quote_order",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','ACCEPTED','REJECTED')",
            name="ck_work_order_quote_status",
        ),
        sa.CheckConstraint("total_amount >= 0", name="ck_work_order_quote_total"),
        sa.CheckConstraint("lock_version > 0", name="ck_work_order_quote_lock_version"),
        sa.UniqueConstraint(
            "tenant_id", "work_order_id", "version_no", name="uk_work_order_quote_version"
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uk_work_order_quotes_tenant_id_id"),
        sa.UniqueConstraint(
            "tenant_id", "decision_key", name="uk_work_order_quote_decision_key"
        ),
    )
    op.create_index(
        "ix_work_order_quote_status",
        "work_order_quotes",
        ["tenant_id", "work_order_id", "status"],
    )

    op.create_table(
        "work_order_quote_lines",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("quote_id", FK_TYPE, nullable=False),
        sa.Column("line_type", sa.String(16), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "quote_id"],
            ["work_order_quotes.tenant_id", "work_order_quotes.id"],
            name="fk_work_order_quote_line_quote",
        ),
        sa.CheckConstraint(
            "line_type IN ('LABOR','MATERIAL','OUTSOURCE','OTHER')",
            name="ck_work_order_quote_line_type",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_work_order_quote_line_quantity"),
        sa.CheckConstraint("unit_price >= 0", name="ck_work_order_quote_line_price"),
        sa.CheckConstraint("amount >= 0", name="ck_work_order_quote_line_amount"),
    )
    op.create_index(
        "ix_work_order_quote_line_quote",
        "work_order_quote_lines",
        ["tenant_id", "quote_id", "id"],
    )

    op.create_table(
        "work_order_cost_entries",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("work_order_id", FK_TYPE, nullable=False),
        sa.Column("entry_type", sa.String(16), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reverses_entry_id", FK_TYPE, nullable=True),
        sa.Column("reason", sa.String(1000), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "work_order_id"],
            ["work_orders.tenant_id", "work_orders.id"],
            name="fk_work_order_cost_order",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "reverses_entry_id"],
            ["work_order_cost_entries.tenant_id", "work_order_cost_entries.id"],
            name="fk_work_order_cost_reversal",
        ),
        sa.CheckConstraint(
            "entry_type IN ('LABOR','MATERIAL','OUTSOURCE','OTHER')",
            name="ck_work_order_cost_type",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_work_order_cost_quantity"),
        sa.CheckConstraint("unit_price >= 0", name="ck_work_order_cost_price"),
        sa.CheckConstraint("amount <> 0", name="ck_work_order_cost_amount"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uk_work_order_cost_key"),
        sa.UniqueConstraint("tenant_id", "id", name="uk_work_order_cost_tenant_id_id"),
    )
    op.create_index(
        "ix_work_order_cost_order",
        "work_order_cost_entries",
        ["tenant_id", "work_order_id", "occurred_at"],
    )

    op.create_table(
        "work_order_acceptances",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("work_order_id", FK_TYPE, nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("comment", sa.String(1000), nullable=True),
        sa.Column("actor_user_id", FK_TYPE, nullable=True),
        sa.Column("actor_party_id", FK_TYPE, nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["actor_party_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "work_order_id"],
            ["work_orders.tenant_id", "work_orders.id"],
            name="fk_work_order_acceptance_order",
        ),
        sa.CheckConstraint(
            "decision IN ('ACCEPTED','REWORK')", name="ck_work_order_acceptance_decision"
        ),
        sa.UniqueConstraint(
            "tenant_id", "work_order_id", "attempt_no", name="uk_work_order_acceptance_attempt"
        ),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uk_work_order_acceptance_key"),
    )
    op.create_index(
        "ix_work_order_acceptance_order",
        "work_order_acceptances",
        ["tenant_id", "work_order_id", "attempt_no"],
    )

    op.create_table(
        "work_order_ratings",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("work_order_id", FK_TYPE, nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("tags_json", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("comment", sa.String(1000), nullable=True),
        sa.Column("actor_user_id", FK_TYPE, nullable=True),
        sa.Column("actor_party_id", FK_TYPE, nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["actor_party_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "work_order_id"],
            ["work_orders.tenant_id", "work_orders.id"],
            name="fk_work_order_rating_order",
        ),
        sa.CheckConstraint("score >= 1 AND score <= 5", name="ck_work_order_rating_score"),
        sa.UniqueConstraint("tenant_id", "work_order_id", name="uk_work_order_rating_order"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uk_work_order_rating_key"),
    )


def downgrade() -> None:
    op.drop_table("work_order_ratings")
    op.drop_index("ix_work_order_acceptance_order", table_name="work_order_acceptances")
    op.drop_table("work_order_acceptances")
    op.drop_index("ix_work_order_cost_order", table_name="work_order_cost_entries")
    op.drop_table("work_order_cost_entries")
    op.drop_index("ix_work_order_quote_line_quote", table_name="work_order_quote_lines")
    op.drop_table("work_order_quote_lines")
    op.drop_index("ix_work_order_quote_status", table_name="work_order_quotes")
    op.drop_table("work_order_quotes")
    op.drop_index("ix_work_order_event_timeline", table_name="work_order_events")
    op.drop_table("work_order_events")

    op.execute(
        "UPDATE work_orders SET status = CASE "
        "WHEN status IN ('SUBMITTED','ASSIGNED') THEN 'OPEN' "
        "WHEN status IN ('WAITING_QUOTE_APPROVAL','IN_PROGRESS_AFTER_QUOTE','WAITING_ACCEPTANCE') "
        "THEN 'IN_PROGRESS' WHEN status = 'COMPLETED' THEN 'DONE' ELSE status END"
    )
    with op.batch_alter_table("work_orders") as batch:
        batch.drop_index("ix_work_orders_sla_v2")
        batch.drop_index("ix_work_orders_party_v2")
        batch.drop_index("ix_work_orders_service_queue_v2")
        batch.drop_index("uk_work_orders_source_v2")
        batch.drop_constraint("fk_work_orders_tenant_assignee_v2", type_="foreignkey")
        batch.drop_constraint("fk_work_orders_tenant_party_v2", type_="foreignkey")
        batch.drop_constraint("fk_work_orders_tenant_park_v2", type_="foreignkey")
        batch.drop_constraint("fk_work_orders_contact_id_v2", type_="foreignkey")
        batch.drop_constraint("fk_work_orders_party_id_v2", type_="foreignkey")
        batch.drop_constraint("uk_work_orders_tenant_order_no", type_="unique")
        batch.drop_constraint("uk_work_orders_tenant_id_id", type_="unique")
        batch.drop_constraint("ck_work_orders_lock_version_v2", type_="check")
        batch.drop_constraint("ck_work_orders_priority_v2", type_="check")
        batch.drop_constraint("ck_work_orders_status_v2", type_="check")
        batch.alter_column(
            "status", existing_type=sa.String(32), server_default="OPEN", nullable=False
        )
        for column in (
            "lock_version",
            "no_evidence_reason",
            "evidence_refs_json",
            "resolution_summary",
            "closed_at",
            "submitted_for_acceptance_at",
            "first_responded_at",
            "resolution_due_at",
            "response_due_at",
            "assignment_rule_version",
            "assignment_rule_id",
            "quote_required",
            "contact_phone_masked",
            "contact_name",
            "contact_id",
            "party_id",
            "order_no",
        ):
            batch.drop_column(column)

    op.drop_index("ix_work_order_rule_match", table_name="work_order_assignment_rules")
    op.drop_index("uk_work_order_rule_published", table_name="work_order_assignment_rules")
    op.drop_table("work_order_assignment_rules")
    op.drop_table("tenant_service_principal_parks")
    op.drop_index(
        "ix_tenant_service_principal_party", table_name="tenant_service_principals"
    )
    op.drop_table("tenant_service_principals")

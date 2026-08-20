"""Park policy, enterprise service, activity, and announcement engagement.

Revision ID: e7b24f0a1c09
Revises: d6a13e9f0b98
Create Date: 2026-08-20
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "e7b24f0a1c09"
down_revision = "d6a13e9f0b98"
branch_labels = None
depends_on = None


def _install_postgresql_guards() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE FUNCTION engagement_reject_event_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'engagement evidence events are append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table_name in (
        "engagement_policy_events",
        "engagement_service_case_events",
        "engagement_activity_events",
    ):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_append_only
            BEFORE UPDATE OR DELETE ON {table_name}
            FOR EACH ROW EXECUTE FUNCTION engagement_reject_event_mutation()
            """
        )
    op.execute(
        """
        CREATE FUNCTION engagement_guard_immutable_version()
        RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.status <> 'DRAFT' THEN
                    RAISE EXCEPTION 'submitted engagement versions cannot be deleted';
                END IF;
                RETURN OLD;
            END IF;
            IF OLD.status <> 'DRAFT'
               AND (
                    to_jsonb(NEW) - ARRAY[
                        'status', 'approval_id', 'published_at', 'published_by',
                        'updated_at', 'confirmed_count', 'waitlist_count'
                    ]::text[]
                   ) IS DISTINCT FROM (
                    to_jsonb(OLD) - ARRAY[
                        'status', 'approval_id', 'published_at', 'published_by',
                        'updated_at', 'confirmed_count', 'waitlist_count'
                    ]::text[]
                   ) THEN
                RAISE EXCEPTION 'submitted engagement version content is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table_name in (
        "engagement_policy_versions",
        "engagement_service_versions",
        "engagement_activity_versions",
        "engagement_announcement_versions",
    ):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_immutable
            BEFORE UPDATE OR DELETE ON {table_name}
            FOR EACH ROW EXECUTE FUNCTION engagement_guard_immutable_version()
            """
        )


def _drop_postgresql_guards() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table_name in (
        "engagement_policy_events",
        "engagement_service_case_events",
        "engagement_activity_events",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_append_only ON {table_name}")
    for table_name in (
        "engagement_policy_versions",
        "engagement_service_versions",
        "engagement_activity_versions",
        "engagement_announcement_versions",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_immutable ON {table_name}")
    op.execute("DROP FUNCTION IF EXISTS engagement_reject_event_mutation()")
    op.execute("DROP FUNCTION IF EXISTS engagement_guard_immutable_version()")


def upgrade() -> None:
    with op.batch_alter_table("business_events", schema=None) as batch_op:
        batch_op.create_unique_constraint("uk_business_event_tenant_id", ["tenant_id", "id"])

    with op.batch_alter_table("in_app_notifications", schema=None) as batch_op:
        batch_op.create_unique_constraint("uk_in_app_notification_tenant_id", ["tenant_id", "id"])

    op.create_table(
        "engagement_migration_runs",
        sa.Column(
            "tenant_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("run_key", sa.String(length=128), nullable=False),
        sa.Column("source_system", sa.String(length=128), nullable=False),
        sa.Column("provenance", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("checkpoint", sa.String(length=255), nullable=True),
        sa.Column("report_json", sa.JSON(), nullable=True),
        sa.Column("production_contacted", sa.Boolean(), server_default="0", nullable=False),
        sa.Column(
            "created_by", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "provenance IN ('SYNTHETIC','DEIDENTIFIED','REAL')", name="ck_eng_migration_provenance"
        ),
        sa.CheckConstraint(
            "status IN ('DRY_RUN','RUNNING','SUCCEEDED','FAILED','ROLLED_BACK')",
            name="ck_eng_migration_status",
        ),
        sa.CheckConstraint("production_contacted = FALSE", name="ck_eng_migration_no_production"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_migration_creator",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "run_key", name="uk_eng_migration_run_key"),
    )
    op.create_table(
        "engagement_activities",
        sa.Column(
            "tenant_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("park_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("code", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("published_version", sa.Integer(), nullable=True),
        sa.Column(
            "approval_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_by", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('DRAFT','PENDING_APPROVAL','APPROVED','PUBLISHED','REGISTRATION_CLOSED','IN_PROGRESS','REJECTED','COMPLETED','CANCELLED')",
            name="ck_eng_activity_status",
        ),
        sa.CheckConstraint("current_version >= 1", name="ck_eng_activity_version"),
        sa.CheckConstraint("lock_version > 0", name="ck_eng_activity_lock"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "approval_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_eng_activity_approval",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_activity_creator",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "park_id"], ["parks.tenant_id", "parks.id"], name="fk_eng_activity_park"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uk_eng_activity_tenant_id"),
        sa.UniqueConstraint("tenant_id", "park_id", "code", name="uk_eng_activity_code"),
    )
    with op.batch_alter_table("engagement_activities", schema=None) as batch_op:
        batch_op.create_index(
            "ix_eng_activity_scope", ["tenant_id", "park_id", "status"], unique=False
        )

    op.create_table(
        "engagement_announcements",
        sa.Column(
            "tenant_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("park_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("code", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("published_version", sa.Integer(), nullable=True),
        sa.Column(
            "approval_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_by", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('DRAFT','PENDING_APPROVAL','APPROVED','SCHEDULED','PUBLISHED','REJECTED','EXPIRED','WITHDRAWN')",
            name="ck_eng_announcement_status",
        ),
        sa.CheckConstraint("current_version >= 1", name="ck_eng_announcement_version"),
        sa.CheckConstraint("lock_version > 0", name="ck_eng_announcement_lock"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "approval_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_eng_announcement_approval",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_announcement_creator",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_eng_announcement_park",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uk_eng_announcement_code"),
        sa.UniqueConstraint("tenant_id", "id", name="uk_eng_announcement_tenant_id"),
    )
    with op.batch_alter_table("engagement_announcements", schema=None) as batch_op:
        batch_op.create_index(
            "ix_eng_announcement_scope", ["tenant_id", "park_id", "status"], unique=False
        )

    op.create_table(
        "engagement_policies",
        sa.Column(
            "tenant_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("park_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("code", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("published_version", sa.Integer(), nullable=True),
        sa.Column(
            "approval_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_by", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('DRAFT','PENDING_APPROVAL','APPROVED','PUBLISHED','REJECTED','EXPIRED','WITHDRAWN')",
            name="ck_eng_policy_status",
        ),
        sa.CheckConstraint("current_version >= 1", name="ck_eng_policy_current_version"),
        sa.CheckConstraint("lock_version > 0", name="ck_eng_policy_lock"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "approval_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_eng_policy_approval",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_policy_creator",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "park_id"], ["parks.tenant_id", "parks.id"], name="fk_eng_policy_park"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uk_eng_policy_code"),
        sa.UniqueConstraint("tenant_id", "id", name="uk_eng_policy_tenant_id"),
    )
    with op.batch_alter_table("engagement_policies", schema=None) as batch_op:
        batch_op.create_index(
            "ix_eng_policy_scope", ["tenant_id", "park_id", "status"], unique=False
        )

    op.create_table(
        "engagement_service_catalogs",
        sa.Column(
            "tenant_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("park_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("code", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("published_version", sa.Integer(), nullable=True),
        sa.Column(
            "approval_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_by", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('DRAFT','PENDING_APPROVAL','APPROVED','PUBLISHED','REJECTED','RETIRED')",
            name="ck_eng_service_catalog_status",
        ),
        sa.CheckConstraint("current_version >= 1", name="ck_eng_service_catalog_version"),
        sa.CheckConstraint("lock_version > 0", name="ck_eng_service_catalog_lock"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "approval_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_eng_service_catalog_approval",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_service_catalog_creator",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_eng_service_catalog_park",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uk_eng_service_catalog_tenant_id"),
        sa.UniqueConstraint("tenant_id", "park_id", "code", name="uk_eng_service_catalog_code"),
    )
    with op.batch_alter_table("engagement_service_catalogs", schema=None) as batch_op:
        batch_op.create_index(
            "ix_eng_service_catalog_scope", ["tenant_id", "park_id", "status"], unique=False
        )

    op.create_table(
        "engagement_activity_versions",
        sa.Column(
            "tenant_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column(
            "activity_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("registration_opens_at", sa.DateTime(), nullable=False),
        sa.Column("registration_closes_at", sa.DateTime(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("confirmed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("waitlist_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("attendee_rules_json", sa.JSON(), nullable=False),
        sa.Column("audience_json", sa.JSON(), nullable=False),
        sa.Column("attachments_json", sa.JSON(), nullable=False),
        sa.Column("cancellation_terms", sa.String(length=1000), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column(
            "approval_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column(
            "created_by", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','APPROVED','PUBLISHED','REJECTED','RETIRED')",
            name="ck_eng_activity_version_status",
        ),
        sa.CheckConstraint("capacity > 0", name="ck_eng_activity_capacity"),
        sa.CheckConstraint(
            "confirmed_count >= 0 AND confirmed_count <= capacity", name="ck_eng_activity_confirmed"
        ),
        sa.CheckConstraint("ends_at > starts_at", name="ck_eng_activity_schedule"),
        sa.CheckConstraint(
            "registration_closes_at <= starts_at", name="ck_eng_activity_registration_close"
        ),
        sa.CheckConstraint(
            "registration_closes_at >= registration_opens_at",
            name="ck_eng_activity_registration_window",
        ),
        sa.CheckConstraint("version >= 1", name="ck_eng_activity_version_no"),
        sa.CheckConstraint("waitlist_count >= 0", name="ck_eng_activity_waitlist"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "activity_id"],
            ["engagement_activities.tenant_id", "engagement_activities.id"],
            name="fk_eng_activity_version_activity",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "approval_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_eng_activity_version_approval",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_activity_version_creator",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "activity_id", "version", name="uk_eng_activity_version"),
        sa.UniqueConstraint("tenant_id", "id", name="uk_eng_activity_version_tenant_id"),
    )
    with op.batch_alter_table("engagement_activity_versions", schema=None) as batch_op:
        batch_op.create_index(
            "ix_eng_activity_version_schedule", ["tenant_id", "status", "starts_at"], unique=False
        )

    op.create_table(
        "engagement_announcement_versions",
        sa.Column(
            "tenant_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column(
            "announcement_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("pin_from", sa.DateTime(), nullable=True),
        sa.Column("pin_to", sa.DateTime(), nullable=True),
        sa.Column("publish_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("attachments_json", sa.JSON(), nullable=False),
        sa.Column("audience_json", sa.JSON(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column(
            "approval_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column(
            "created_by", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "priority IN ('NORMAL','IMPORTANT','URGENT')", name="ck_eng_announcement_priority"
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','APPROVED','SCHEDULED','PUBLISHED','REJECTED','RETIRED')",
            name="ck_eng_announcement_version_status",
        ),
        sa.CheckConstraint(
            "expires_at IS NULL OR expires_at > publish_at", name="ck_eng_announcement_expiry"
        ),
        sa.CheckConstraint(
            "pin_to IS NULL OR pin_from IS NULL OR pin_to >= pin_from",
            name="ck_eng_announcement_pin_window",
        ),
        sa.CheckConstraint("version >= 1", name="ck_eng_announcement_version_no"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "announcement_id"],
            ["engagement_announcements.tenant_id", "engagement_announcements.id"],
            name="fk_eng_announcement_version_header",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "approval_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_eng_announcement_version_approval",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_announcement_version_creator",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "announcement_id", "version", name="uk_eng_announcement_version"
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uk_eng_announcement_version_tenant_id"),
    )
    with op.batch_alter_table("engagement_announcement_versions", schema=None) as batch_op:
        batch_op.create_index(
            "ix_eng_announcement_publish",
            ["tenant_id", "status", "publish_at", "expires_at"],
            unique=False,
        )

    op.create_table(
        "engagement_policy_consultations",
        sa.Column(
            "tenant_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("park_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column(
            "policy_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("party_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("case_no", sa.String(length=48), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_by", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('OPEN','IN_PROGRESS','CLOSED','CANCELLED')",
            name="ck_eng_policy_consult_status",
        ),
        sa.CheckConstraint("lock_version > 0", name="ck_eng_policy_consult_lock"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_policy_consult_creator",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_eng_policy_consult_park",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_eng_policy_consult_party",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "policy_id"],
            ["engagement_policies.tenant_id", "engagement_policies.id"],
            name="fk_eng_policy_consult_policy",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "case_no", name="uk_eng_policy_consult_no"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uk_eng_policy_consult_key"),
    )
    with op.batch_alter_table("engagement_policy_consultations", schema=None) as batch_op:
        batch_op.create_index(
            "ix_eng_policy_consult_scope", ["tenant_id", "park_id", "status"], unique=False
        )

    op.create_table(
        "engagement_policy_events",
        sa.Column(
            "tenant_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column(
            "policy_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column("detail_json", sa.JSON(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column(
            "actor_user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('CREATED','UPDATED','SUBMITTED','APPROVED','REJECTED','PUBLISHED','EXPIRED','WITHDRAWN','MATCH_EVALUATED')",
            name="ck_eng_policy_event_type",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "actor_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_policy_event_actor",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "policy_id"],
            ["engagement_policies.tenant_id", "engagement_policies.id"],
            name="fk_eng_policy_event_policy",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uk_eng_policy_event_key"),
    )
    with op.batch_alter_table("engagement_policy_events", schema=None) as batch_op:
        batch_op.create_index(
            "ix_eng_policy_event_timeline", ["tenant_id", "policy_id", "occurred_at"], unique=False
        )

    op.create_table(
        "engagement_policy_follows",
        sa.Column(
            "tenant_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column(
            "policy_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("party_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("park_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('ACTIVE','UNFOLLOWED')", name="ck_eng_policy_follow_status"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_eng_policy_follow_park",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_eng_policy_follow_party",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "policy_id"],
            ["engagement_policies.tenant_id", "engagement_policies.id"],
            name="fk_eng_policy_follow_policy",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_policy_follow_user",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "policy_id", "party_id", name="uk_eng_policy_follow"),
    )
    op.create_table(
        "engagement_policy_versions",
        sa.Column(
            "tenant_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column(
            "policy_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.String(length=1000), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("region_code", sa.String(length=32), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_system", sa.String(length=64), nullable=True),
        sa.Column("source_identifier", sa.String(length=128), nullable=True),
        sa.Column("source_publisher", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("source_published_at", sa.DateTime(), nullable=True),
        sa.Column("effective_on", sa.Date(), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("attachments_json", sa.JSON(), nullable=False),
        sa.Column("applicability_json", sa.JSON(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column(
            "approval_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column(
            "created_by", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column(
            "published_by", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','APPROVED','PUBLISHED','REJECTED','RETIRED')",
            name="ck_eng_policy_version_status",
        ),
        sa.CheckConstraint(
            "expires_on IS NULL OR effective_on IS NULL OR expires_on >= effective_on",
            name="ck_eng_policy_version_dates",
        ),
        sa.CheckConstraint("version >= 1", name="ck_eng_policy_version_no"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "approval_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_eng_policy_version_approval",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_policy_version_creator",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "policy_id"],
            ["engagement_policies.tenant_id", "engagement_policies.id"],
            name="fk_eng_policy_version_policy",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "published_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_policy_version_publisher",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uk_eng_policy_version_tenant_id"),
        sa.UniqueConstraint("tenant_id", "policy_id", "version", name="uk_eng_policy_version"),
    )
    with op.batch_alter_table("engagement_policy_versions", schema=None) as batch_op:
        batch_op.create_index(
            "ix_eng_policy_version_window",
            ["tenant_id", "status", "effective_on", "expires_on"],
            unique=False,
        )
    op.create_table(
        "engagement_service_versions",
        sa.Column(
            "tenant_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column(
            "catalog_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("provider_type", sa.String(length=16), nullable=False),
        sa.Column("provider_name", sa.String(length=255), nullable=False),
        sa.Column("provider_state", sa.String(length=24), nullable=False),
        sa.Column("sla_hours", sa.Integer(), nullable=False),
        sa.Column("appointment_required", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("eligibility_json", sa.JSON(), nullable=False),
        sa.Column("evidence_rules_json", sa.JSON(), nullable=False),
        sa.Column("price_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default="CNY", nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column(
            "approval_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column(
            "created_by", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "provider_state IN ('LOCAL','NOT_CONNECTED')", name="ck_eng_service_provider_state"
        ),
        sa.CheckConstraint(
            "provider_type IN ('INTERNAL','EXTERNAL')", name="ck_eng_service_provider_type"
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','APPROVED','PUBLISHED','REJECTED','RETIRED')",
            name="ck_eng_service_version_status",
        ),
        sa.CheckConstraint(
            "price_amount IS NULL OR price_amount >= 0", name="ck_eng_service_price"
        ),
        sa.CheckConstraint("sla_hours BETWEEN 1 AND 8760", name="ck_eng_service_sla"),
        sa.CheckConstraint("version >= 1", name="ck_eng_service_version_no"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "approval_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            name="fk_eng_service_version_approval",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "catalog_id"],
            ["engagement_service_catalogs.tenant_id", "engagement_service_catalogs.id"],
            name="fk_eng_service_version_catalog",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_service_version_creator",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "catalog_id", "version", name="uk_eng_service_version"),
        sa.UniqueConstraint("tenant_id", "id", name="uk_eng_service_version_tenant_id"),
    )
    op.create_table(
        "engagement_activity_registrations",
        sa.Column(
            "tenant_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("park_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column(
            "activity_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column(
            "activity_version_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column("party_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column(
            "principal_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attendee_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("waitlist_position", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("checked_in_at", sa.DateTime(), nullable=True),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('CONFIRMED','WAITLISTED','CANCELLED','CHECKED_IN')",
            name="ck_eng_activity_registration_status",
        ),
        sa.CheckConstraint("attendee_count > 0", name="ck_eng_activity_registration_count"),
        sa.CheckConstraint("lock_version > 0", name="ck_eng_activity_registration_lock"),
        sa.CheckConstraint(
            "waitlist_position IS NULL OR waitlist_position > 0",
            name="ck_eng_activity_waitlist_position",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "activity_id"],
            ["engagement_activities.tenant_id", "engagement_activities.id"],
            name="fk_eng_activity_registration_activity",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "activity_version_id"],
            ["engagement_activity_versions.tenant_id", "engagement_activity_versions.id"],
            name="fk_eng_activity_registration_version",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_eng_activity_registration_park",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_eng_activity_registration_party",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["tenant_service_principals.tenant_id", "tenant_service_principals.id"],
            name="fk_eng_activity_registration_principal",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "activity_version_id",
            "party_id",
            name="uk_eng_activity_registration_party",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uk_eng_activity_registration_tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uk_eng_activity_registration_key"
        ),
    )
    with op.batch_alter_table("engagement_activity_registrations", schema=None) as batch_op:
        batch_op.create_index(
            "ix_eng_activity_registration_queue",
            ["tenant_id", "activity_version_id", "status", "waitlist_position"],
            unique=False,
        )

    op.create_table(
        "engagement_announcement_targets",
        sa.Column(
            "tenant_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column(
            "announcement_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column(
            "announcement_version_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column("park_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("party_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column(
            "recipient_user_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=24), nullable=False),
        sa.Column("source_key", sa.String(length=128), nullable=False),
        sa.Column("audience_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('TARGETED','DELIVERED','SKIPPED','FAILED','READ')",
            name="ck_eng_announcement_target_status",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "announcement_id"],
            ["engagement_announcements.tenant_id", "engagement_announcements.id"],
            name="fk_eng_announcement_target_header",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "announcement_version_id"],
            ["engagement_announcement_versions.tenant_id", "engagement_announcement_versions.id"],
            name="fk_eng_announcement_target_version",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_eng_announcement_target_park",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_eng_announcement_target_party",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "recipient_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_announcement_target_recipient",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "announcement_version_id",
            "recipient_user_id",
            name="uk_eng_announcement_target_recipient",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uk_eng_announcement_target_tenant_id"),
    )
    with op.batch_alter_table("engagement_announcement_targets", schema=None) as batch_op:
        batch_op.create_index(
            "ix_eng_announcement_target_delivery",
            ["tenant_id", "announcement_version_id", "status"],
            unique=False,
        )

    op.create_table(
        "engagement_service_cases",
        sa.Column(
            "tenant_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("park_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column(
            "catalog_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column(
            "service_version_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column("party_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column(
            "principal_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column("case_no", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("contact_masked", sa.String(length=64), nullable=True),
        sa.Column(
            "assigned_to", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column(
            "work_order_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column("sla_due_at", sa.DateTime(), nullable=False),
        sa.Column("appointment_at", sa.DateTime(), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_by", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "priority IN ('LOW','MEDIUM','HIGH','URGENT')", name="ck_eng_service_case_priority"
        ),
        sa.CheckConstraint(
            "status IN ('SUBMITTED','ACCEPTED','ASSIGNED','APPOINTED','IN_PROGRESS','RESULT_READY','DISPUTED','CONFIRMED','CANCELLED')",
            name="ck_eng_service_case_status",
        ),
        sa.CheckConstraint("lock_version > 0", name="ck_eng_service_case_lock"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assigned_to"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_service_case_assignee",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "catalog_id"],
            ["engagement_service_catalogs.tenant_id", "engagement_service_catalogs.id"],
            name="fk_eng_service_case_catalog",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_service_case_creator",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "park_id", "work_order_id"],
            ["work_orders.tenant_id", "work_orders.park_id", "work_orders.id"],
            name="fk_eng_service_case_work_order",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_eng_service_case_park",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_eng_service_case_party",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "principal_id"],
            ["tenant_service_principals.tenant_id", "tenant_service_principals.id"],
            name="fk_eng_service_case_principal",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "service_version_id"],
            ["engagement_service_versions.tenant_id", "engagement_service_versions.id"],
            name="fk_eng_service_case_version",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "case_no", name="uk_eng_service_case_no"),
        sa.UniqueConstraint("tenant_id", "id", name="uk_eng_service_case_tenant_id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uk_eng_service_case_key"),
    )
    with op.batch_alter_table("engagement_service_cases", schema=None) as batch_op:
        batch_op.create_index(
            "ix_eng_service_case_scope",
            ["tenant_id", "park_id", "status", "sla_due_at"],
            unique=False,
        )

    op.create_table(
        "engagement_activity_events",
        sa.Column(
            "tenant_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column(
            "activity_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column(
            "registration_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("detail_json", sa.JSON(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column(
            "actor_user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('UPDATED','SUBMITTED','APPROVED','PUBLISHED','REGISTRATION_CLOSED','IN_PROGRESS','REGISTERED','WAITLISTED','PROMOTED','CANCELLED','CHECKED_IN','COMPLETED')",
            name="ck_eng_activity_event_type",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "activity_id"],
            ["engagement_activities.tenant_id", "engagement_activities.id"],
            name="fk_eng_activity_event_activity",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "actor_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_activity_event_actor",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "registration_id"],
            ["engagement_activity_registrations.tenant_id", "engagement_activity_registrations.id"],
            name="fk_eng_activity_event_registration",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uk_eng_activity_event_key"),
    )
    with op.batch_alter_table("engagement_activity_events", schema=None) as batch_op:
        batch_op.create_index(
            "ix_eng_activity_event_timeline",
            ["tenant_id", "activity_id", "occurred_at"],
            unique=False,
        )

    op.create_table(
        "engagement_activity_feedback",
        sa.Column(
            "tenant_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column(
            "registration_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("party_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(length=1000), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.CheckConstraint("score BETWEEN 1 AND 5", name="ck_eng_activity_feedback_score"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_eng_activity_feedback_party",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "registration_id"],
            ["engagement_activity_registrations.tenant_id", "engagement_activity_registrations.id"],
            name="fk_eng_activity_feedback_registration",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "registration_id", name="uk_eng_activity_feedback_registration"
        ),
    )
    op.create_table(
        "engagement_announcement_deliveries",
        sa.Column(
            "tenant_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column(
            "target_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("event_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column(
            "notification_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column("idempotency_key", sa.String(length=192), nullable=False),
        sa.Column("channel", sa.String(length=16), server_default="IN_APP", nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(length=1000), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("channel = 'IN_APP'", name="ck_eng_announcement_delivery_channel"),
        sa.CheckConstraint(
            "status IN ('PENDING','DELIVERED','SKIPPED','FAILED','READ')",
            name="ck_eng_announcement_delivery_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_eng_announcement_delivery_attempts"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["business_events.tenant_id", "business_events.id"],
            name="fk_eng_announcement_delivery_event",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "notification_id"],
            ["in_app_notifications.tenant_id", "in_app_notifications.id"],
            name="fk_eng_announcement_delivery_notification",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "target_id"],
            ["engagement_announcement_targets.tenant_id", "engagement_announcement_targets.id"],
            name="fk_eng_announcement_delivery_target",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uk_eng_announcement_delivery_key"
        ),
        sa.UniqueConstraint("tenant_id", "target_id", name="uk_eng_announcement_delivery_target"),
    )
    with op.batch_alter_table("engagement_announcement_deliveries", schema=None) as batch_op:
        batch_op.create_index(
            "ix_eng_announcement_delivery_retry",
            ["tenant_id", "status", "updated_at"],
            unique=False,
        )

    op.create_table(
        "engagement_service_case_events",
        sa.Column(
            "tenant_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("case_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column(
            "actor_user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('SUBMITTED','ACCEPTED','ASSIGNED','APPOINTED','EVIDENCE','PROGRESS','RESULT_READY','DISPUTED','CONFIRMED','CANCELLED','SLA_ESCALATED','WORK_ORDER_LINKED')",
            name="ck_eng_service_case_event_type",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "actor_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_eng_service_case_event_actor",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["engagement_service_cases.tenant_id", "engagement_service_cases.id"],
            name="fk_eng_service_case_event_case",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uk_eng_service_case_event_key"),
    )
    with op.batch_alter_table("engagement_service_case_events", schema=None) as batch_op:
        batch_op.create_index(
            "ix_eng_service_case_event_time", ["tenant_id", "case_id", "occurred_at"], unique=False
        )

    op.create_table(
        "engagement_service_feedback",
        sa.Column(
            "tenant_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("case_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("party_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(length=1000), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.CheckConstraint("score BETWEEN 1 AND 5", name="ck_eng_service_feedback_score"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["engagement_service_cases.tenant_id", "engagement_service_cases.id"],
            name="fk_eng_service_feedback_case",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_eng_service_feedback_party",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "case_id", name="uk_eng_service_feedback_case"),
    )
    _install_postgresql_guards()


def downgrade() -> None:
    _drop_postgresql_guards()
    op.drop_table("engagement_service_feedback")
    with op.batch_alter_table("engagement_service_case_events", schema=None) as batch_op:
        batch_op.drop_index("ix_eng_service_case_event_time")

    op.drop_table("engagement_service_case_events")
    with op.batch_alter_table("engagement_announcement_deliveries", schema=None) as batch_op:
        batch_op.drop_index("ix_eng_announcement_delivery_retry")

    op.drop_table("engagement_announcement_deliveries")
    op.drop_table("engagement_activity_feedback")
    with op.batch_alter_table("engagement_activity_events", schema=None) as batch_op:
        batch_op.drop_index("ix_eng_activity_event_timeline")

    op.drop_table("engagement_activity_events")
    with op.batch_alter_table("engagement_service_cases", schema=None) as batch_op:
        batch_op.drop_index("ix_eng_service_case_scope")

    op.drop_table("engagement_service_cases")
    with op.batch_alter_table("engagement_announcement_targets", schema=None) as batch_op:
        batch_op.drop_index("ix_eng_announcement_target_delivery")

    op.drop_table("engagement_announcement_targets")
    with op.batch_alter_table("engagement_activity_registrations", schema=None) as batch_op:
        batch_op.drop_index("ix_eng_activity_registration_queue")

    op.drop_table("engagement_activity_registrations")
    op.drop_table("engagement_service_versions")
    with op.batch_alter_table("engagement_policy_versions", schema=None) as batch_op:
        batch_op.drop_index("ix_eng_policy_version_window")

    op.drop_table("engagement_policy_versions")
    op.drop_table("engagement_policy_follows")
    with op.batch_alter_table("engagement_policy_events", schema=None) as batch_op:
        batch_op.drop_index("ix_eng_policy_event_timeline")

    op.drop_table("engagement_policy_events")
    with op.batch_alter_table("engagement_policy_consultations", schema=None) as batch_op:
        batch_op.drop_index("ix_eng_policy_consult_scope")

    op.drop_table("engagement_policy_consultations")
    with op.batch_alter_table("engagement_announcement_versions", schema=None) as batch_op:
        batch_op.drop_index("ix_eng_announcement_publish")

    op.drop_table("engagement_announcement_versions")
    with op.batch_alter_table("engagement_activity_versions", schema=None) as batch_op:
        batch_op.drop_index("ix_eng_activity_version_schedule")

    op.drop_table("engagement_activity_versions")
    with op.batch_alter_table("engagement_service_catalogs", schema=None) as batch_op:
        batch_op.drop_index("ix_eng_service_catalog_scope")

    op.drop_table("engagement_service_catalogs")
    with op.batch_alter_table("engagement_policies", schema=None) as batch_op:
        batch_op.drop_index("ix_eng_policy_scope")

    op.drop_table("engagement_policies")
    with op.batch_alter_table("engagement_announcements", schema=None) as batch_op:
        batch_op.drop_index("ix_eng_announcement_scope")

    op.drop_table("engagement_announcements")
    with op.batch_alter_table("engagement_activities", schema=None) as batch_op:
        batch_op.drop_index("ix_eng_activity_scope")

    op.drop_table("engagement_activities")
    op.drop_table("engagement_migration_runs")

    with op.batch_alter_table("in_app_notifications", schema=None) as batch_op:
        batch_op.drop_constraint("uk_in_app_notification_tenant_id", type_="unique")

    with op.batch_alter_table("business_events", schema=None) as batch_op:
        batch_op.drop_constraint("uk_business_event_tenant_id", type_="unique")

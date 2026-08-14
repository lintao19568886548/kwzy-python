"""governed party enterprise profile and evidence graph

Revision ID: t6c24e9f1a08
Revises: s5b13d8e0f97
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "t6c24e9f1a08"
down_revision: str | None = "s5b13d8e0f97"
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
    with op.batch_alter_table("parties") as batch:
        batch.create_unique_constraint("uk_parties_tenant_id_id", ["tenant_id", "id"])
    with op.batch_alter_table("attachments") as batch:
        batch.create_unique_constraint("uk_attachments_tenant_id_id", ["tenant_id", "id"])

    op.create_table(
        "party_enterprise_profiles",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("party_id", FK_TYPE, nullable=False),
        sa.Column("short_name", sa.String(128), nullable=True),
        sa.Column("legal_representative", sa.String(128), nullable=True),
        sa.Column("established_on", sa.Date(), nullable=True),
        sa.Column("registered_capital", sa.Numeric(18, 2), nullable=True),
        sa.Column("capital_currency", sa.String(3), nullable=True),
        sa.Column("registration_status", sa.String(16), server_default="UNKNOWN", nullable=False),
        sa.Column("registration_authority", sa.String(255), nullable=True),
        sa.Column("industry_code", sa.String(32), nullable=True),
        sa.Column("industry_name", sa.String(128), nullable=True),
        sa.Column("employee_size_band", sa.String(16), server_default="UNKNOWN", nullable=False),
        sa.Column("website", sa.String(512), nullable=True),
        sa.Column("business_scope", sa.Text(), nullable=True),
        sa.Column("provider_status", sa.String(32), server_default="NOT_CONNECTED", nullable=False),
        sa.Column("last_verified_at", sa.DateTime(), nullable=True),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("updated_by", FK_TYPE, nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "registration_status IN ('ACTIVE', 'SUSPENDED', 'REVOKED', 'CANCELLED', 'UNKNOWN')",
            name="ck_party_enterprise_profile_registration_status",
        ),
        sa.CheckConstraint(
            "employee_size_band IN ('MICRO', 'SMALL', 'MEDIUM', 'LARGE', 'UNKNOWN')",
            name="ck_party_enterprise_profile_size_band",
        ),
        sa.CheckConstraint(
            "provider_status IN ('NOT_CONNECTED', 'LOCAL_ONLY', 'SANDBOX_VERIFIED', 'LIVE_CONNECTED')",
            name="ck_party_enterprise_profile_provider_status",
        ),
        sa.CheckConstraint(
            "registered_capital IS NULL OR registered_capital >= 0",
            name="ck_party_enterprise_profile_capital_nonnegative",
        ),
        sa.CheckConstraint("lock_version > 0", name="ck_party_enterprise_profile_lock_version"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_party_enterprise_profile_tenant_party",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "party_id", name="uk_party_enterprise_profile_party"),
        sa.UniqueConstraint("tenant_id", "id", name="uk_party_enterprise_profiles_tenant_id_id"),
    )
    op.create_index(
        "ix_party_enterprise_profiles_tenant_industry",
        "party_enterprise_profiles",
        ["tenant_id", "industry_code"],
    )
    op.create_index(
        "ix_party_enterprise_profiles_tenant_registration",
        "party_enterprise_profiles",
        ["tenant_id", "registration_status"],
    )

    op.create_table(
        "party_enterprise_relationships",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("source_party_id", FK_TYPE, nullable=False),
        sa.Column("target_party_id", FK_TYPE, nullable=False),
        sa.Column("relationship_type", sa.String(32), nullable=False),
        sa.Column("ownership_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("source_type", sa.String(16), server_default="MANUAL", nullable=False),
        sa.Column("source_reference", sa.String(128), nullable=True),
        sa.Column("attachment_id", FK_TYPE, nullable=True),
        sa.Column("started_on", sa.Date(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("end_reason", sa.String(512), nullable=True),
        sa.Column("status", sa.String(16), server_default="ACTIVE", nullable=False),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("ended_by", FK_TYPE, nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "relationship_type IN ('PARENT_OF', 'INVESTED_IN', 'COMMON_CONTROL', 'BUSINESS_PARTNER')",
            name="ck_party_enterprise_relationship_type",
        ),
        sa.CheckConstraint(
            "source_party_id <> target_party_id", name="ck_party_enterprise_relationship_self"
        ),
        sa.CheckConstraint(
            "ownership_percent IS NULL OR (ownership_percent >= 0 AND ownership_percent <= 100)",
            name="ck_party_enterprise_relationship_ownership",
        ),
        sa.CheckConstraint(
            "source_type IN ('MANUAL', 'MIGRATION', 'EXTERNAL')",
            name="ck_party_enterprise_relationship_source_type",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'ENDED')", name="ck_party_enterprise_relationship_status"
        ),
        sa.CheckConstraint("lock_version > 0", name="ck_party_enterprise_relationship_lock_version"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "source_party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_party_enterprise_relationship_tenant_source",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "target_party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_party_enterprise_relationship_tenant_target",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "attachment_id"],
            ["attachments.tenant_id", "attachments.id"],
            name="fk_party_enterprise_relationship_tenant_attachment",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["ended_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uk_party_enterprise_relationships_tenant_id_id"),
    )
    op.create_index(
        "uk_party_enterprise_relationship_active",
        "party_enterprise_relationships",
        ["tenant_id", "source_party_id", "target_party_id", "relationship_type"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
        sqlite_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_index(
        "ix_party_enterprise_relationship_target",
        "party_enterprise_relationships",
        ["tenant_id", "target_party_id", "status"],
    )

    op.create_table(
        "party_enterprise_credentials",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("party_id", FK_TYPE, nullable=False),
        sa.Column("attachment_id", FK_TYPE, nullable=False),
        sa.Column("credential_type", sa.String(32), nullable=False),
        sa.Column("identifier_fingerprint", sa.String(64), nullable=True),
        sa.Column("identifier_masked", sa.String(32), nullable=True),
        sa.Column("issuer", sa.String(255), nullable=True),
        sa.Column("issued_on", sa.Date(), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(16), server_default="ACTIVE", nullable=False),
        sa.Column("verification_status", sa.String(24), server_default="UNVERIFIED", nullable=False),
        sa.Column("review_reason", sa.String(512), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by", FK_TYPE, nullable=True),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("updated_by", FK_TYPE, nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "credential_type IN ('BUSINESS_LICENSE', 'TAX_REGISTRATION', 'ORGANIZATION_CODE', 'INDUSTRY_LICENSE', 'OTHER')",
            name="ck_party_enterprise_credential_type",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'EXPIRED', 'REVOKED', 'ARCHIVED')",
            name="ck_party_enterprise_credential_status",
        ),
        sa.CheckConstraint(
            "verification_status IN ('UNVERIFIED', 'LOCALLY_REVIEWED', 'EXTERNALLY_VERIFIED', 'REJECTED')",
            name="ck_party_enterprise_credential_verification",
        ),
        sa.CheckConstraint(
            "expires_on IS NULL OR issued_on IS NULL OR expires_on >= issued_on",
            name="ck_party_enterprise_credential_dates",
        ),
        sa.CheckConstraint("lock_version > 0", name="ck_party_enterprise_credential_lock_version"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_party_enterprise_credential_tenant_party",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "attachment_id"],
            ["attachments.tenant_id", "attachments.id"],
            name="fk_party_enterprise_credential_tenant_attachment",
        ),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uk_party_enterprise_credentials_tenant_id_id"),
    )
    op.create_index(
        "uk_party_enterprise_credential_active_attachment",
        "party_enterprise_credentials",
        ["tenant_id", "party_id", "credential_type", "attachment_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
        sqlite_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_index(
        "ix_party_enterprise_credentials_expiry",
        "party_enterprise_credentials",
        ["tenant_id", "status", "expires_on"],
    )

    op.create_table(
        "party_enterprise_tags",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("party_id", FK_TYPE, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("normalized_name", sa.String(128), nullable=False),
        sa.Column("tag_type", sa.String(24), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("source_reference", sa.String(128), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), server_default="1", nullable=False),
        sa.Column("verification_status", sa.String(24), server_default="UNVERIFIED", nullable=False),
        sa.Column("status", sa.String(16), server_default="ACTIVE", nullable=False),
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("deactivated_at", sa.DateTime(), nullable=True),
        sa.Column("deactivated_by", FK_TYPE, nullable=True),
        sa.Column("deactivation_reason", sa.String(512), nullable=True),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "tag_type IN ('INDUSTRY', 'CAPABILITY', 'QUALIFICATION', 'INTENT', 'CUSTOM')",
            name="ck_party_enterprise_tag_type",
        ),
        sa.CheckConstraint(
            "source_type IN ('MANUAL', 'MIGRATION', 'EXTERNAL')",
            name="ck_party_enterprise_tag_source_type",
        ),
        sa.CheckConstraint(
            "verification_status IN ('UNVERIFIED', 'LOCALLY_REVIEWED', 'EXTERNALLY_VERIFIED', 'REJECTED')",
            name="ck_party_enterprise_tag_verification",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_party_enterprise_tag_confidence"
        ),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="ck_party_enterprise_tag_status"),
        sa.CheckConstraint("lock_version > 0", name="ck_party_enterprise_tag_lock_version"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_party_enterprise_tag_tenant_party",
        ),
        sa.ForeignKeyConstraint(["deactivated_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uk_party_enterprise_tags_tenant_id_id"),
    )
    op.create_index(
        "uk_party_enterprise_tag_active",
        "party_enterprise_tags",
        ["tenant_id", "party_id", "tag_type", "normalized_name"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
        sqlite_where=sa.text("status = 'ACTIVE'"),
    )

    op.create_table(
        "party_enterprise_risk_signals",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("party_id", FK_TYPE, nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("summary", sa.String(1000), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("source_reference", sa.String(128), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("attachment_id", FK_TYPE, nullable=True),
        sa.Column("created_by", FK_TYPE, nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "category IN ('LEGAL', 'FINANCIAL', 'COMPLIANCE', 'OPERATIONAL', 'REPUTATION', 'OTHER')",
            name="ck_party_enterprise_risk_category",
        ),
        sa.CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_party_enterprise_risk_severity",
        ),
        sa.CheckConstraint(
            "source_type IN ('MANUAL', 'MIGRATION', 'EXTERNAL')",
            name="ck_party_enterprise_risk_source_type",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_party_enterprise_risk_tenant_party",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "attachment_id"],
            ["attachments.tenant_id", "attachments.id"],
            name="fk_party_enterprise_risk_tenant_attachment",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uk_party_enterprise_risk_signals_tenant_id_id"),
    )
    op.create_index(
        "uk_party_enterprise_risk_source",
        "party_enterprise_risk_signals",
        ["tenant_id", "party_id", "source_type", "source_reference"],
        unique=True,
        postgresql_where=sa.text("source_reference IS NOT NULL"),
        sqlite_where=sa.text("source_reference IS NOT NULL"),
    )
    op.create_index(
        "ix_party_enterprise_risk_open",
        "party_enterprise_risk_signals",
        ["tenant_id", "party_id", "severity", "occurred_at"],
    )

    op.create_table(
        "party_enterprise_risk_resolutions",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("party_id", FK_TYPE, nullable=False),
        sa.Column("signal_id", FK_TYPE, nullable=False),
        sa.Column("resolution_type", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("resolved_by", FK_TYPE, nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "resolution_type IN ('MITIGATED', 'DISMISSED', 'ACCEPTED')",
            name="ck_party_enterprise_risk_resolution_type",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_party_enterprise_resolution_tenant_party",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "signal_id"],
            ["party_enterprise_risk_signals.tenant_id", "party_enterprise_risk_signals.id"],
            name="fk_party_enterprise_resolution_tenant_signal",
        ),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "signal_id", name="uk_party_enterprise_risk_resolution_signal"
        ),
    )


def downgrade() -> None:
    op.drop_table("party_enterprise_risk_resolutions")
    op.drop_table("party_enterprise_risk_signals")
    op.drop_table("party_enterprise_tags")
    op.drop_table("party_enterprise_credentials")
    op.drop_table("party_enterprise_relationships")
    op.drop_table("party_enterprise_profiles")
    with op.batch_alter_table("attachments") as batch:
        batch.drop_constraint("uk_attachments_tenant_id_id", type_="unique")
    with op.batch_alter_table("parties") as batch:
        batch.drop_constraint("uk_parties_tenant_id_id", type_="unique")

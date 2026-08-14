"""Tenant-safe enterprise-profile persistence owned by the Party context."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import (
    FK_TYPE,
    Base,
    PrimaryKeyMixin,
    TimestampMixin,
    utc_now,
)


class PartyEnterpriseProfile(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "party_enterprise_profiles"
    __table_args__ = (
        CheckConstraint(
            "registration_status IN ('ACTIVE', 'SUSPENDED', 'REVOKED', 'CANCELLED', 'UNKNOWN')",
            name="ck_party_enterprise_profile_registration_status",
        ),
        CheckConstraint(
            "employee_size_band IN ('MICRO', 'SMALL', 'MEDIUM', 'LARGE', 'UNKNOWN')",
            name="ck_party_enterprise_profile_size_band",
        ),
        CheckConstraint(
            "provider_status IN ('NOT_CONNECTED', 'LOCAL_ONLY', 'SANDBOX_VERIFIED', 'LIVE_CONNECTED')",
            name="ck_party_enterprise_profile_provider_status",
        ),
        CheckConstraint(
            "registered_capital IS NULL OR registered_capital >= 0",
            name="ck_party_enterprise_profile_capital_nonnegative",
        ),
        CheckConstraint("lock_version > 0", name="ck_party_enterprise_profile_lock_version"),
        ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_party_enterprise_profile_tenant_party",
        ),
        UniqueConstraint("tenant_id", "party_id", name="uk_party_enterprise_profile_party"),
        UniqueConstraint("tenant_id", "id", name="uk_party_enterprise_profiles_tenant_id_id"),
        Index("ix_party_enterprise_profiles_tenant_industry", "tenant_id", "industry_code"),
        Index(
            "ix_party_enterprise_profiles_tenant_registration",
            "tenant_id",
            "registration_status",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    party_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    legal_representative: Mapped[str | None] = mapped_column(String(128), nullable=True)
    established_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    registered_capital: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    capital_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    registration_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="UNKNOWN", server_default="UNKNOWN"
    )
    registration_authority: Mapped[str | None] = mapped_column(String(255), nullable=True)
    industry_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    industry_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    employee_size_band: Mapped[str] = mapped_column(
        String(16), nullable=False, default="UNKNOWN", server_default="UNKNOWN"
    )
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    business_scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="NOT_CONNECTED", server_default="NOT_CONNECTED"
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)


class PartyEnterpriseRelationship(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "party_enterprise_relationships"
    __table_args__ = (
        CheckConstraint(
            "relationship_type IN ('PARENT_OF', 'INVESTED_IN', 'COMMON_CONTROL', 'BUSINESS_PARTNER')",
            name="ck_party_enterprise_relationship_type",
        ),
        CheckConstraint("source_party_id <> target_party_id", name="ck_party_enterprise_relationship_self"),
        CheckConstraint(
            "ownership_percent IS NULL OR (ownership_percent >= 0 AND ownership_percent <= 100)",
            name="ck_party_enterprise_relationship_ownership",
        ),
        CheckConstraint(
            "source_type IN ('MANUAL', 'MIGRATION', 'EXTERNAL')",
            name="ck_party_enterprise_relationship_source_type",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'ENDED')", name="ck_party_enterprise_relationship_status"
        ),
        CheckConstraint("lock_version > 0", name="ck_party_enterprise_relationship_lock_version"),
        ForeignKeyConstraint(
            ["tenant_id", "source_party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_party_enterprise_relationship_tenant_source",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "target_party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_party_enterprise_relationship_tenant_target",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "attachment_id"],
            ["attachments.tenant_id", "attachments.id"],
            name="fk_party_enterprise_relationship_tenant_attachment",
        ),
        UniqueConstraint("tenant_id", "id", name="uk_party_enterprise_relationships_tenant_id_id"),
        Index(
            "uk_party_enterprise_relationship_active",
            "tenant_id",
            "source_party_id",
            "target_party_id",
            "relationship_type",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
        Index(
            "ix_party_enterprise_relationship_target",
            "tenant_id",
            "target_party_id",
            "status",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    source_party_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    target_party_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(32), nullable=False)
    ownership_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    source_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="MANUAL", server_default="MANUAL"
    )
    source_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    attachment_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    started_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    ended_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)


class PartyEnterpriseCredential(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "party_enterprise_credentials"
    __table_args__ = (
        CheckConstraint(
            "credential_type IN ('BUSINESS_LICENSE', 'TAX_REGISTRATION', 'ORGANIZATION_CODE', 'INDUSTRY_LICENSE', 'OTHER')",
            name="ck_party_enterprise_credential_type",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'EXPIRED', 'REVOKED', 'ARCHIVED')",
            name="ck_party_enterprise_credential_status",
        ),
        CheckConstraint(
            "verification_status IN ('UNVERIFIED', 'LOCALLY_REVIEWED', 'EXTERNALLY_VERIFIED', 'REJECTED')",
            name="ck_party_enterprise_credential_verification",
        ),
        CheckConstraint(
            "expires_on IS NULL OR issued_on IS NULL OR expires_on >= issued_on",
            name="ck_party_enterprise_credential_dates",
        ),
        CheckConstraint("lock_version > 0", name="ck_party_enterprise_credential_lock_version"),
        ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_party_enterprise_credential_tenant_party",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "attachment_id"],
            ["attachments.tenant_id", "attachments.id"],
            name="fk_party_enterprise_credential_tenant_attachment",
        ),
        UniqueConstraint("tenant_id", "id", name="uk_party_enterprise_credentials_tenant_id_id"),
        Index(
            "uk_party_enterprise_credential_active_attachment",
            "tenant_id",
            "party_id",
            "credential_type",
            "attachment_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
        Index(
            "ix_party_enterprise_credentials_expiry",
            "tenant_id",
            "status",
            "expires_on",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    party_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    attachment_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    credential_type: Mapped[str] = mapped_column(String(32), nullable=False)
    identifier_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    identifier_masked: Mapped[str | None] = mapped_column(String(32), nullable=True)
    issuer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issued_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    verification_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="UNVERIFIED", server_default="UNVERIFIED"
    )
    review_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)


class PartyEnterpriseTag(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "party_enterprise_tags"
    __table_args__ = (
        CheckConstraint(
            "tag_type IN ('INDUSTRY', 'CAPABILITY', 'QUALIFICATION', 'INTENT', 'CUSTOM')",
            name="ck_party_enterprise_tag_type",
        ),
        CheckConstraint(
            "source_type IN ('MANUAL', 'MIGRATION', 'EXTERNAL')",
            name="ck_party_enterprise_tag_source_type",
        ),
        CheckConstraint(
            "verification_status IN ('UNVERIFIED', 'LOCALLY_REVIEWED', 'EXTERNALLY_VERIFIED', 'REJECTED')",
            name="ck_party_enterprise_tag_verification",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_party_enterprise_tag_confidence"),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="ck_party_enterprise_tag_status"),
        CheckConstraint("lock_version > 0", name="ck_party_enterprise_tag_lock_version"),
        ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_party_enterprise_tag_tenant_party",
        ),
        UniqueConstraint("tenant_id", "id", name="uk_party_enterprise_tags_tenant_id_id"),
        Index(
            "uk_party_enterprise_tag_active",
            "tenant_id",
            "party_id",
            "tag_type",
            "normalized_name",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    party_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(128), nullable=False)
    tag_type: Mapped[str] = mapped_column(String(24), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal(1), server_default="1"
    )
    verification_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="UNVERIFIED", server_default="UNVERIFIED"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    deactivated_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    deactivation_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)


class PartyEnterpriseRiskSignal(Base, PrimaryKeyMixin):
    __tablename__ = "party_enterprise_risk_signals"
    __table_args__ = (
        CheckConstraint(
            "category IN ('LEGAL', 'FINANCIAL', 'COMPLIANCE', 'OPERATIONAL', 'REPUTATION', 'OTHER')",
            name="ck_party_enterprise_risk_category",
        ),
        CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_party_enterprise_risk_severity",
        ),
        CheckConstraint(
            "source_type IN ('MANUAL', 'MIGRATION', 'EXTERNAL')",
            name="ck_party_enterprise_risk_source_type",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_party_enterprise_risk_tenant_party",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "attachment_id"],
            ["attachments.tenant_id", "attachments.id"],
            name="fk_party_enterprise_risk_tenant_attachment",
        ),
        UniqueConstraint("tenant_id", "id", name="uk_party_enterprise_risk_signals_tenant_id_id"),
        Index(
            "uk_party_enterprise_risk_source",
            "tenant_id",
            "party_id",
            "source_type",
            "source_reference",
            unique=True,
            postgresql_where=text("source_reference IS NOT NULL"),
            sqlite_where=text("source_reference IS NOT NULL"),
        ),
        Index(
            "ix_party_enterprise_risk_open",
            "tenant_id",
            "party_id",
            "severity",
            "occurred_at",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    party_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    attachment_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )


class PartyEnterpriseRiskResolution(Base, PrimaryKeyMixin):
    __tablename__ = "party_enterprise_risk_resolutions"
    __table_args__ = (
        CheckConstraint(
            "resolution_type IN ('MITIGATED', 'DISMISSED', 'ACCEPTED')",
            name="ck_party_enterprise_risk_resolution_type",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["parties.tenant_id", "parties.id"],
            name="fk_party_enterprise_resolution_tenant_party",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "signal_id"],
            ["party_enterprise_risk_signals.tenant_id", "party_enterprise_risk_signals.id"],
            name="fk_party_enterprise_resolution_tenant_signal",
        ),
        UniqueConstraint("tenant_id", "signal_id", name="uk_party_enterprise_risk_resolution_signal"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    party_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    signal_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    resolution_type: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    resolved_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )

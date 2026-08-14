"""Records, seal custody/use and electronic-signature evidence models."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import FK_TYPE, Base, PrimaryKeyMixin, TimestampMixin


class RecordCategory(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "record_categories"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','RETIRED')", name="ck_record_category_status"),
        CheckConstraint(
            "retention_mode IN ('YEARS','PERMANENT')", name="ck_record_category_retention"
        ),
        CheckConstraint(
            "(retention_mode = 'PERMANENT' AND retention_years IS NULL) OR "
            "(retention_mode = 'YEARS' AND retention_years > 0)",
            name="ck_record_category_years",
        ),
        CheckConstraint(
            "confidentiality_max IN ('PUBLIC','INTERNAL','CONFIDENTIAL','RESTRICTED')",
            name="ck_record_category_confidentiality",
        ),
        CheckConstraint("lock_version > 0", name="ck_record_category_lock"),
        UniqueConstraint("tenant_id", "code", name="uk_record_category_code"),
        UniqueConstraint("tenant_id", "id", name="uk_record_category_tenant_id"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    retention_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    retention_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidentiality_max: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)


class RecordFile(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "record_files"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','FILED','ON_HOLD','DISPOSITION_PENDING','DISPOSED')",
            name="ck_record_file_status",
        ),
        CheckConstraint(
            "confidentiality IN ('PUBLIC','INTERNAL','CONFIDENTIAL','RESTRICTED')",
            name="ck_record_file_confidentiality",
        ),
        CheckConstraint("retention_mode IN ('YEARS','PERMANENT')", name="ck_record_file_retention"),
        CheckConstraint(
            "(retention_mode = 'PERMANENT' AND retention_years IS NULL AND retention_until IS NULL) OR "
            "(retention_mode = 'YEARS' AND retention_years > 0 AND retention_until IS NOT NULL)",
            name="ck_record_file_retention_value",
        ),
        CheckConstraint("lock_version > 0", name="ck_record_file_lock"),
        UniqueConstraint("tenant_id", "record_no", name="uk_record_file_no"),
        UniqueConstraint("tenant_id", "id", name="uk_record_file_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "category_id"],
            ["record_categories.tenant_id", "record_categories.id"],
            name="fk_record_file_category",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_record_file_park",
        ),
        Index("ix_record_file_catalog", "tenant_id", "park_id", "status", "category_id"),
        Index("ix_record_file_retention", "tenant_id", "retention_until", "status"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    category_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    record_no: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidentiality: Mapped[str] = mapped_column(String(16), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    retention_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    retention_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retention_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    filed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    filed_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    disposed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    disposed_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)


class RecordRevision(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "record_revisions"
    __table_args__ = (
        CheckConstraint("version_no > 0", name="ck_record_revision_version"),
        CheckConstraint("status IN ('ACTIVE','DISPOSED')", name="ck_record_revision_status"),
        CheckConstraint("size_bytes > 0", name="ck_record_revision_size"),
        UniqueConstraint("tenant_id", "record_id", "version_no", name="uk_record_revision_version"),
        UniqueConstraint("tenant_id", "id", name="uk_record_revision_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "record_id"],
            ["record_files.tenant_id", "record_files.id"],
            name="fk_record_revision_record",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "attachment_id"],
            ["attachments.tenant_id", "attachments.id"],
            name="fk_record_revision_attachment",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "supersedes_revision_id"],
            ["record_revisions.tenant_id", "record_revisions.id"],
            name="fk_record_revision_supersedes",
        ),
        Index("ix_record_revision_record", "tenant_id", "record_id", "version_no"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    record_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    attachment_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    supersedes_revision_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)


class RecordIntegrityEvent(Base, PrimaryKeyMixin):
    __tablename__ = "record_integrity_events"
    __table_args__ = (
        CheckConstraint(
            "result IN ('MATCH','MISMATCH','UNAVAILABLE')", name="ck_record_integrity_result"
        ),
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_record_integrity_key"),
        ForeignKeyConstraint(
            ["tenant_id", "record_id"],
            ["record_files.tenant_id", "record_files.id"],
            name="fk_record_integrity_record",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "revision_id"],
            ["record_revisions.tenant_id", "record_revisions.id"],
            name="fk_record_integrity_revision",
        ),
        Index("ix_record_integrity_timeline", "tenant_id", "record_id", "verified_at"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    record_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    revision_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    expected_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    actual_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    verified_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class RecordHold(Base, PrimaryKeyMixin):
    __tablename__ = "record_holds"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','RELEASED')", name="ck_record_hold_status"),
        ForeignKeyConstraint(
            ["tenant_id", "record_id"],
            ["record_files.tenant_id", "record_files.id"],
            name="fk_record_hold_record",
        ),
        Index(
            "uk_record_hold_active",
            "tenant_id",
            "record_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    record_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    placed_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    placed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    released_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    release_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class RecordAccessRequest(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "record_access_requests"
    __table_args__ = (
        CheckConstraint("mode IN ('VIEW','BORROW')", name="ck_record_access_mode"),
        CheckConstraint(
            "status IN ('PENDING_APPROVAL','APPROVED','APPROVAL_RETURNED','REJECTED','CHECKED_OUT','RETURNED','EXPIRED','WITHDRAWN')",
            name="ck_record_access_status",
        ),
        CheckConstraint("lock_version > 0", name="ck_record_access_lock"),
        UniqueConstraint("tenant_id", "request_key", name="uk_record_access_key"),
        ForeignKeyConstraint(
            ["tenant_id", "record_id"],
            ["record_files.tenant_id", "record_files.id"],
            name="fk_record_access_record",
        ),
        Index("ix_record_access_queue", "tenant_id", "park_id", "status", "requested_until"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    record_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    purpose: Mapped[str] = mapped_column(String(1000), nullable=False)
    requested_until: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    requester_user_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=False)
    approval_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("approval_requests.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING_APPROVAL")
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )


class RecordDisposition(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "record_dispositions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING_APPROVAL','APPROVED','APPROVAL_RETURNED','CONFIRMING','DISPOSED','REJECTED','WITHDRAWN')",
            name="ck_record_disposition_status",
        ),
        CheckConstraint("lock_version > 0", name="ck_record_disposition_lock"),
        UniqueConstraint("tenant_id", "request_key", name="uk_record_disposition_key"),
        UniqueConstraint("tenant_id", "id", name="uk_record_disposition_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "record_id"],
            ["record_files.tenant_id", "record_files.id"],
            name="fk_record_disposition_record",
        ),
        Index(
            "uk_record_disposition_open",
            "tenant_id",
            "record_id",
            unique=True,
            postgresql_where=text("status IN ('PENDING_APPROVAL','APPROVED','CONFIRMING')"),
            sqlite_where=text("status IN ('PENDING_APPROVAL','APPROVED','CONFIRMING')"),
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    record_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    requested_by: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=False)
    approval_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("approval_requests.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING_APPROVAL")
    request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    manifest_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_deletion_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="NOT_EXECUTED"
    )
    disposed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )


class RecordDispositionConfirmation(Base, PrimaryKeyMixin):
    __tablename__ = "record_disposition_confirmations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "disposition_id", "confirmer_user_id", name="uk_disposition_confirmer"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "disposition_id"],
            ["record_dispositions.tenant_id", "record_dispositions.id"],
            name="fk_disposition_confirmation",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    disposition_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    confirmer_user_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SealAsset(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "seal_assets"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('OFFICIAL','CONTRACT','FINANCE','LEGAL_REPRESENTATIVE','ELECTRONIC','OTHER')",
            name="ck_seal_asset_kind",
        ),
        CheckConstraint(
            "status IN ('ACTIVE','TRANSFER_PENDING','SUSPENDED','LOST','RETIRED')",
            name="ck_seal_asset_status",
        ),
        CheckConstraint("lock_version > 0", name="ck_seal_asset_lock"),
        UniqueConstraint("tenant_id", "seal_code", name="uk_seal_asset_code"),
        UniqueConstraint("tenant_id", "id", name="uk_seal_asset_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "park_id"],
            ["parks.tenant_id", "parks.id"],
            name="fk_seal_asset_park",
        ),
        Index("ix_seal_asset_catalog", "tenant_id", "park_id", "status", "kind"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    seal_code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    custodian_user_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)


class SealCustodyEvent(Base, PrimaryKeyMixin):
    __tablename__ = "seal_custody_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('CREATED','TRANSFER_REQUESTED','TRANSFER_ACCEPTED','SUSPENDED','LOST','RECOVERED','RETIRED')",
            name="ck_seal_custody_event_type",
        ),
        CheckConstraint(
            "status IN ('PENDING','COMPLETED','CANCELLED')", name="ck_seal_custody_event_status"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "seal_id"],
            ["seal_assets.tenant_id", "seal_assets.id"],
            name="fk_seal_custody_event_seal",
        ),
        Index(
            "uk_seal_pending_transfer",
            "tenant_id",
            "seal_id",
            unique=True,
            postgresql_where=text("event_type = 'TRANSFER_REQUESTED' AND status = 'PENDING'"),
            sqlite_where=text("event_type = 'TRANSFER_REQUESTED' AND status = 'PENDING'"),
        ),
        Index("ix_seal_custody_timeline", "tenant_id", "seal_id", "occurred_at"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    seal_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="COMPLETED")
    from_custodian_user_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True
    )
    to_custodian_user_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("users.id"), nullable=True
    )
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SealUseApplication(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "seal_use_applications"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING_APPROVAL','APPROVED','APPROVAL_RETURNED','EXECUTED','REJECTED','WITHDRAWN','CANCELLED')",
            name="ck_seal_use_status",
        ),
        CheckConstraint("copy_count > 0", name="ck_seal_use_copy_count"),
        CheckConstraint("lock_version > 0", name="ck_seal_use_lock"),
        UniqueConstraint("tenant_id", "application_key", name="uk_seal_use_key"),
        UniqueConstraint("tenant_id", "id", name="uk_seal_use_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "seal_id"],
            ["seal_assets.tenant_id", "seal_assets.id"],
            name="fk_seal_use_seal",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "record_id"],
            ["record_files.tenant_id", "record_files.id"],
            name="fk_seal_use_record",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "revision_id"],
            ["record_revisions.tenant_id", "record_revisions.id"],
            name="fk_seal_use_revision",
        ),
        Index("ix_seal_use_queue", "tenant_id", "park_id", "status", "requested_for"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    seal_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    record_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    revision_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    revision_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(1000), nullable=False)
    copy_count: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_for: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    applicant_user_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=False)
    approval_id: Mapped[int | None] = mapped_column(
        FK_TYPE, ForeignKey("approval_requests.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING_APPROVAL")
    application_key: Mapped[str] = mapped_column(String(128), nullable=False)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )


class SealUseReceipt(Base, PrimaryKeyMixin):
    __tablename__ = "seal_use_receipts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "application_id", name="uk_seal_use_receipt_application"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uk_seal_use_receipt_key"),
        ForeignKeyConstraint(
            ["tenant_id", "application_id"],
            ["seal_use_applications.tenant_id", "seal_use_applications.id"],
            name="fk_seal_use_receipt_application",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "evidence_attachment_id"],
            ["attachments.tenant_id", "attachments.id"],
            name="fk_seal_use_receipt_attachment",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    application_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    revision_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    copy_count: Mapped[int] = mapped_column(Integer, nullable=False)
    executor_user_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=False)
    evidence_attachment_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    command_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SignatureProvider(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "signature_providers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('NOT_CONNECTED','SANDBOX','CONNECTED','DEGRADED')",
            name="ck_signature_provider_status",
        ),
        CheckConstraint(
            "(status = 'CONNECTED' AND live_verified) OR "
            "(status <> 'CONNECTED' AND NOT live_verified)",
            name="ck_signature_provider_truth",
        ),
        CheckConstraint("lock_version > 0", name="ck_signature_provider_lock"),
        UniqueConstraint("tenant_id", "code", name="uk_signature_provider_code"),
        UniqueConstraint("tenant_id", "id", name="uk_signature_provider_tenant_id"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    adapter_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_CONNECTED")
    credential_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    health_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    live_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )


class SignatureEnvelope(Base, PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "signature_envelopes"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','PENDING','SANDBOX_COMPLETED','COMPLETED','DECLINED','VOID','FAILED')",
            name="ck_signature_envelope_status",
        ),
        CheckConstraint(
            "(status = 'COMPLETED' AND live_verified) OR "
            "(status <> 'COMPLETED' AND NOT live_verified)",
            name="ck_signature_envelope_truth",
        ),
        CheckConstraint("lock_version > 0", name="ck_signature_envelope_lock"),
        UniqueConstraint("tenant_id", "envelope_no", name="uk_signature_envelope_no"),
        UniqueConstraint(
            "tenant_id", "provider_id", "provider_ref", name="uk_signature_provider_ref"
        ),
        UniqueConstraint(
            "tenant_id",
            "source_type",
            "source_id",
            "revision_id",
            name="uk_signature_source_revision",
        ),
        UniqueConstraint("tenant_id", "id", name="uk_signature_envelope_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "provider_id"],
            ["signature_providers.tenant_id", "signature_providers.id"],
            name="fk_signature_envelope_provider",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "record_id"],
            ["record_files.tenant_id", "record_files.id"],
            name="fk_signature_envelope_record",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "revision_id"],
            ["record_revisions.tenant_id", "record_revisions.id"],
            name="fk_signature_envelope_revision",
        ),
        Index("ix_signature_envelope_queue", "tenant_id", "park_id", "status", "created_at"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    park_id: Mapped[int | None] = mapped_column(FK_TYPE, nullable=True)
    provider_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    record_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    revision_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    revision_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    envelope_no: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    provider_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    live_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    created_by: Mapped[int | None] = mapped_column(FK_TYPE, ForeignKey("users.id"), nullable=True)


class SignatureParticipant(Base, PrimaryKeyMixin):
    __tablename__ = "signature_participants"
    __table_args__ = (
        CheckConstraint("role IN ('SIGNER','CC','APPROVER')", name="ck_signature_participant_role"),
        CheckConstraint(
            "status IN ('PENDING','COMPLETED','DECLINED')", name="ck_signature_participant_status"
        ),
        CheckConstraint("position > 0", name="ck_signature_participant_position"),
        UniqueConstraint(
            "tenant_id", "envelope_id", "position", name="uk_signature_participant_position"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "envelope_id"],
            ["signature_envelopes.tenant_id", "signature_envelopes.id"],
            name="fk_signature_participant_envelope",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    envelope_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    contact_masked: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SignatureEvent(Base, PrimaryKeyMixin):
    __tablename__ = "signature_events"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "provider_id", "source_event_id", name="uk_signature_event_source"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "provider_id"],
            ["signature_providers.tenant_id", "signature_providers.id"],
            name="fk_signature_event_provider",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "envelope_id"],
            ["signature_envelopes.tenant_id", "signature_envelopes.id"],
            name="fk_signature_event_envelope",
        ),
        Index("ix_signature_event_timeline", "tenant_id", "envelope_id", "occurred_at"),
    )

    tenant_id: Mapped[int] = mapped_column(FK_TYPE, ForeignKey("tenants.id"), nullable=False)
    provider_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    envelope_id: Mapped[int] = mapped_column(FK_TYPE, nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    detail_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

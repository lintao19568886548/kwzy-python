"""Strict request contracts for records, signature and seal governance."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CategoryCreate(StrictBody):
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=128)
    retention_mode: Literal["YEARS", "PERMANENT"]
    retention_years: int | None = Field(default=None, ge=1, le=100)
    confidentiality_max: Literal["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]


class CategoryUpdate(StrictBody):
    expected_version: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1000)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    retention_mode: Literal["YEARS", "PERMANENT"] | None = None
    retention_years: int | None = Field(default=None, ge=1, le=100)
    confidentiality_max: Literal["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"] | None = None


class ExpectedReason(StrictBody):
    expected_version: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1000)


class RecordCreate(StrictBody):
    park_id: int | None = Field(default=None, gt=0)
    category_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    confidentiality: Literal["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]
    source_type: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    source_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")


class RevisionCreate(StrictBody):
    expected_version: int = Field(gt=0)
    attachment_id: int = Field(gt=0)


class IntegrityVerify(StrictBody):
    revision_id: int | None = Field(default=None, gt=0)


class AccessRequestCreate(StrictBody):
    mode: Literal["VIEW", "BORROW"]
    purpose: str = Field(min_length=1, max_length=1000)
    requested_until: datetime
    definition_code: str = Field(min_length=1, max_length=64)


class DispositionCreate(ExpectedReason):
    definition_code: str = Field(min_length=1, max_length=64)


class SealCreate(StrictBody):
    park_id: int | None = Field(default=None, gt=0)
    seal_code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=128)
    kind: Literal["OFFICIAL", "CONTRACT", "FINANCE", "LEGAL_REPRESENTATIVE", "ELECTRONIC", "OTHER"]
    custodian_user_id: int = Field(gt=0)
    description: str | None = Field(default=None, max_length=1000)


class SealTransfer(ExpectedReason):
    to_custodian_user_id: int = Field(gt=0)


class SealUseCreate(StrictBody):
    seal_id: int = Field(gt=0)
    record_id: int = Field(gt=0)
    revision_id: int = Field(gt=0)
    purpose: str = Field(min_length=1, max_length=1000)
    copy_count: int = Field(gt=0, le=1000)
    requested_for: datetime
    definition_code: str = Field(min_length=1, max_length=64)


class SealUseExecute(StrictBody):
    expected_version: int = Field(gt=0)
    evidence_attachment_id: int | None = Field(default=None, gt=0)
    emergency_override_reason: str | None = Field(default=None, min_length=1, max_length=1000)


class SignatureProviderCreate(StrictBody):
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=128)
    adapter_kind: Literal["LOCAL_SANDBOX", "EXTERNAL"]
    credential_ref: str | None = Field(default=None, max_length=128)


class SignatureParticipantBody(StrictBody):
    role: Literal["SIGNER", "CC", "APPROVER"]
    display_name: str = Field(min_length=1, max_length=128)
    contact_masked: str | None = Field(default=None, max_length=128)


class SignatureEnvelopeCreate(StrictBody):
    provider_id: int = Field(gt=0)
    record_id: int = Field(gt=0)
    revision_id: int = Field(gt=0)
    source_type: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    source_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    purpose: str = Field(min_length=1, max_length=500)
    participants: list[SignatureParticipantBody] = Field(min_length=1, max_length=50)

"""Strict transport schemas for enterprise Party subresources."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EnterpriseProfileSave(StrictBody):
    expected_lock_version: int | None = Field(default=None, ge=0)
    short_name: str | None = Field(default=None, max_length=128)
    legal_representative: str | None = Field(default=None, max_length=128)
    established_on: date | None = None
    registered_capital: Decimal | None = Field(default=None, ge=0)
    capital_currency: str | None = Field(default=None, min_length=3, max_length=3)
    registration_status: Literal["ACTIVE", "SUSPENDED", "REVOKED", "CANCELLED", "UNKNOWN"] | None = None
    registration_authority: str | None = Field(default=None, max_length=255)
    industry_code: str | None = Field(default=None, max_length=32)
    industry_name: str | None = Field(default=None, max_length=128)
    employee_size_band: Literal["MICRO", "SMALL", "MEDIUM", "LARGE", "UNKNOWN"] | None = None
    website: str | None = Field(default=None, max_length=512)
    business_scope: str | None = Field(default=None, max_length=4000)


class EnterpriseRelationshipCreate(StrictBody):
    target_party_id: int = Field(gt=0)
    relationship_type: Literal["PARENT_OF", "INVESTED_IN", "COMMON_CONTROL", "BUSINESS_PARTNER"]
    ownership_percent: Decimal | None = Field(default=None, ge=0, le=100)
    source_type: Literal["MANUAL", "MIGRATION", "EXTERNAL"] = "MANUAL"
    source_reference: str | None = Field(default=None, max_length=128)
    attachment_id: int | None = Field(default=None, gt=0)
    started_on: date | None = None


class VersionReason(StrictBody):
    expected_lock_version: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=512)


class EnterpriseCredentialCreate(StrictBody):
    attachment_id: int = Field(gt=0)
    credential_type: Literal[
        "BUSINESS_LICENSE",
        "TAX_REGISTRATION",
        "ORGANIZATION_CODE",
        "INDUSTRY_LICENSE",
        "OTHER",
    ]
    identifier: str | None = Field(default=None, min_length=4, max_length=128)
    issuer: str | None = Field(default=None, max_length=255)
    issued_on: date | None = None
    expires_on: date | None = None


class EnterpriseCredentialReview(VersionReason):
    verification_status: Literal["LOCALLY_REVIEWED", "REJECTED", "EXTERNALLY_VERIFIED"]


class EnterpriseCredentialTransition(VersionReason):
    status: Literal["EXPIRED", "REVOKED", "ARCHIVED"]


class EnterpriseTagCreate(StrictBody):
    name: str = Field(min_length=1, max_length=128)
    tag_type: Literal["INDUSTRY", "CAPABILITY", "QUALIFICATION", "INTENT", "CUSTOM"]
    source_type: Literal["MANUAL", "MIGRATION", "EXTERNAL"] = "MANUAL"
    source_reference: str | None = Field(default=None, max_length=128)
    confidence: Decimal = Field(default=Decimal(1), ge=0, le=1)


class EnterpriseRiskSignalCreate(StrictBody):
    category: Literal["LEGAL", "FINANCIAL", "COMPLIANCE", "OPERATIONAL", "REPUTATION", "OTHER"]
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    summary: str = Field(min_length=1, max_length=1000)
    source_type: Literal["MANUAL", "MIGRATION", "EXTERNAL"] = "MANUAL"
    source_reference: str | None = Field(default=None, max_length=128)
    occurred_at: datetime | None = None
    attachment_id: int | None = Field(default=None, gt=0)


class EnterpriseRiskResolve(StrictBody):
    resolution_type: Literal["MITIGATED", "DISMISSED", "ACCEPTED"]
    reason: str = Field(min_length=1, max_length=1000)

"""Pure rule tests for governed enterprise profiles."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.errors import AppError
from app.modules.party.domain.enterprise_rules import (
    canonical_relationship,
    effective_credential_status,
    enterprise_completeness,
    enterprise_risk_summary,
    ownership_value,
    reduce_organization_identifier,
    website_value,
)


def test_relationship_canonicalization_and_ownership_rules() -> None:
    assert canonical_relationship(8, 3, "business_partner") == (3, 8, "BUSINESS_PARTNER")
    assert canonical_relationship(8, 3, "PARENT_OF") == (8, 3, "PARENT_OF")
    assert str(ownership_value("35.126", "INVESTED_IN")) == "35.13"

    with pytest.raises(AppError) as same_party:
        canonical_relationship(3, 3, "PARENT_OF")
    assert same_party.value.code == "ENTERPRISE_RELATIONSHIP_INVALID"

    with pytest.raises(AppError) as unsupported:
        ownership_value("1", "COMMON_CONTROL")
    assert unsupported.value.code == "ENTERPRISE_RELATIONSHIP_OWNERSHIP_INVALID"


def test_identifier_is_reduced_and_never_returned_verbatim() -> None:
    raw = "9131-0000-MA1F-L1Y37B"
    fingerprint, masked = reduce_organization_identifier(raw)

    assert fingerprint is not None and len(fingerprint) == 64
    assert masked is not None and masked.endswith("Y37B")
    assert raw not in fingerprint
    assert "91310000MA1FL1Y37B" not in masked
    assert reduce_organization_identifier(None) == (None, None)


def test_completeness_and_local_risk_are_deterministic() -> None:
    result = enterprise_completeness(
        {
            "CREDIT_CODE": True,
            "LEGAL_REPRESENTATIVE": True,
            "ESTABLISHED_ON": True,
            "REGISTERED_CAPITAL": True,
            "REGISTRATION_STATUS": True,
            "INDUSTRY": True,
            "BUSINESS_SCOPE": True,
            "REGISTERED_ADDRESS": True,
            "PRIMARY_CONTACT": True,
            "BUSINESS_LICENSE": True,
        }
    )
    assert result.score == 100
    assert result.missing == ()

    risk = enterprise_risk_summary(
        [("LOW", "LEGAL"), ("CRITICAL", "COMPLIANCE"), ("HIGH", "LEGAL")]
    )
    assert risk["overall_level"] == "CRITICAL"
    assert risk["unresolved_count"] == 3
    assert risk["category_counts"] == {"LEGAL": 2, "COMPLIANCE": 1}


def test_credential_expiry_and_website_validation() -> None:
    today = datetime.now(timezone.utc).date()
    assert (
        effective_credential_status("ACTIVE", today - timedelta(days=1), today=today) == "EXPIRED"
    )
    assert effective_credential_status("ACTIVE", today, today=today) == "ACTIVE"
    assert website_value("https://example.cn/profile") == "https://example.cn/profile"

    for invalid in ("javascript:alert(1)", "https://user:pass@example.cn", "//example.cn"):
        with pytest.raises(AppError):
            website_value(invalid)

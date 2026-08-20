"""Pure engagement transition, matching, checksum, and URL-safety tests."""

from __future__ import annotations

import pytest

from app.core.errors import AppError
from app.modules.engagement.domain.rules import (
    activity_transition,
    announcement_transition,
    canonical_hash,
    evaluate_applicability,
    idempotency_fingerprint,
    normalize_code,
    normalize_external_url,
    normalize_rule_set,
    policy_transition,
    require_version,
    service_case_transition,
)


def test_engagement_lifecycle_transitions_are_explicit_and_fail_closed() -> None:
    assert policy_transition("DRAFT", "PENDING_APPROVAL") == "PENDING_APPROVAL"
    assert announcement_transition("APPROVED", "SCHEDULED") == "SCHEDULED"
    assert service_case_transition("RESULT_READY", "CONFIRMED") == "CONFIRMED"
    assert activity_transition("PUBLISHED", "REGISTRATION_CLOSED") == "REGISTRATION_CLOSED"
    with pytest.raises(AppError) as error:
        policy_transition("PUBLISHED", "DRAFT")
    assert error.value.code == "INVALID_STATE_TRANSITION"


def test_expected_version_reports_the_persisted_version() -> None:
    require_version(7, "7")
    with pytest.raises(AppError) as error:
        require_version(7, 6)
    assert error.value.code == "VERSION_CONFLICT"
    assert error.value.data == {"current_version": 7}


def test_codes_hashes_and_idempotency_fingerprints_are_canonical() -> None:
    assert normalize_code(" park_service ") == "PARK_SERVICE"
    assert canonical_hash({"b": 2, "a": 1}) == canonical_hash({"a": 1, "b": 2})
    first = idempotency_fingerprint(
        command="create_case", actor_id=9, payload={"subject": "照明", "park_id": 2}
    )
    second = idempotency_fingerprint(
        command="CREATE_CASE", actor_id=9, payload={"park_id": 2, "subject": "照明"}
    )
    assert first == second
    with pytest.raises(AppError):
        normalize_code("../unsafe")


def test_external_links_require_https_safe_host_and_optional_allowlist() -> None:
    assert (
        normalize_external_url(
            "https://Policy.Example.COM/path?q=1#fragment",
            allowed_hosts={"policy.example.com"},
        )
        == "https://policy.example.com/path?q=1"
    )
    for value in (
        "http://policy.example.com",
        "https://localhost/internal",
        "https://127.0.0.1/internal",
        "https://user:secret@policy.example.com",
        "https://policy.example.com:8443/path",
    ):
        with pytest.raises(AppError):
            normalize_external_url(value)
    with pytest.raises(AppError):
        normalize_external_url(
            "https://unapproved.example.net/path", allowed_hosts={"policy.example.com"}
        )


def test_applicability_rules_are_bounded_normalized_and_explainable() -> None:
    rules = normalize_rule_set(
        [
            {"field": "tag_code", "operator": "contains_any", "values": ["HIGH_TECH"]},
            {"field": "park_id", "operator": "eq", "values": ["12"]},
        ]
    )
    eligible, matched, unmet = evaluate_applicability(
        rules, {"park_id": 12, "tag_code": ["HIGH_TECH", "EXPORT"]}
    )
    assert eligible is True
    assert len(matched) == 2
    assert unmet == []

    eligible, matched, unmet = evaluate_applicability(
        rules, {"park_id": 12, "tag_code": ["MANUFACTURING"]}
    )
    assert eligible is False
    assert matched == ["park_id:EQ:12"]
    assert unmet == ["tag_code:CONTAINS_ANY:HIGH_TECH"]


@pytest.mark.parametrize(
    "rules",
    [
        [{"field": "credit_code", "operator": "EQ", "values": ["secret"]}],
        [{"field": "park_id", "operator": "EQ", "values": ["1", "2"]}],
        [{"field": "park_id", "operator": "REGEX", "values": [".*"]}],
        [{"field": "park_id", "operator": "EQ", "values": ["1"], "extra": True}],
    ],
)
def test_applicability_rules_reject_unbounded_or_sensitive_shapes(rules: object) -> None:
    with pytest.raises(AppError):
        normalize_rule_set(rules)

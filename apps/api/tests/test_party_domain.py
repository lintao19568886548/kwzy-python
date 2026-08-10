"""Party domain rules unit tests."""

from __future__ import annotations

import pytest

from app.modules.party.domain.rules import (
    assert_party_type,
    assert_status_transition,
    is_person_address_forbidden,
    normalize_credit_code,
    validate_credit_code_format,
)


def test_normalize_credit_code() -> None:
    assert normalize_credit_code("  ab123  ") == "AB123"
    assert normalize_credit_code("   ") is None
    assert normalize_credit_code(None) is None


def test_credit_code_format() -> None:
    validate_credit_code_format("91310000MA1FL1Y37B")
    with pytest.raises(ValueError):
        validate_credit_code_format("SHORT")


def test_party_type() -> None:
    assert assert_party_type("organization") == "ORGANIZATION"
    with pytest.raises(ValueError):
        assert_party_type("OWNER")


def test_status_transition() -> None:
    assert assert_status_transition("ACTIVE", "ARCHIVED") == "ARCHIVED"
    with pytest.raises(ValueError):
        assert_status_transition("ACTIVE", "BAD")


def test_person_address_forbidden_rule() -> None:
    assert is_person_address_forbidden("PERSON") is True
    assert is_person_address_forbidden("person") is True
    assert is_person_address_forbidden("ORGANIZATION") is False

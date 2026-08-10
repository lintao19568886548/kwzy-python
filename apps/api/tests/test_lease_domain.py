"""Lease domain unit tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.lease.domain.rules import (
    assert_capacity,
    assert_status_transition,
    assert_term_type,
    is_editable_status,
    is_occupying_status,
)


def test_status_transitions() -> None:
    assert assert_status_transition("DRAFT", "PENDING_ACTIVE") == "PENDING_ACTIVE"
    assert assert_status_transition("PENDING_ACTIVE", "ACTIVE") == "ACTIVE"
    assert assert_status_transition("ACTIVE", "TERMINATED") == "TERMINATED"
    with pytest.raises(ValueError):
        assert_status_transition("TERMINATED", "ACTIVE")


def test_occupying_and_editable() -> None:
    assert is_occupying_status("ACTIVE") is True
    assert is_occupying_status("EXPIRING") is True
    assert is_occupying_status("DRAFT") is False
    assert is_editable_status("DRAFT") is True
    assert is_editable_status("ACTIVE") is False


def test_term_type_and_capacity() -> None:
    assert assert_term_type("increase") == "INCREASE"
    assert_capacity(Decimal("100"), Decimal("40"), Decimal("50"))
    with pytest.raises(ValueError):
        assert_capacity(Decimal("100"), Decimal("60"), Decimal("50"))

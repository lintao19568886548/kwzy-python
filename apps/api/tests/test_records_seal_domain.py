"""Pure rule tests for records, seal custody and signature truth."""

from __future__ import annotations

from datetime import date

import pytest

from app.core.errors import AppError
from app.modules.records_seal.domain.rules import (
    assert_category_confidentiality,
    canonical_payload_hash,
    retention_values,
    transition_seal,
)


def test_retention_handles_permanent_and_leap_day() -> None:
    assert retention_values(mode="PERMANENT", years=None, filed_on=date(2024, 2, 29)) == (
        "PERMANENT",
        None,
        None,
    )
    assert retention_values(mode="YEARS", years=1, filed_on=date(2024, 2, 29)) == (
        "YEARS",
        1,
        date(2025, 2, 28),
    )


def test_confidentiality_and_seal_transitions_fail_closed() -> None:
    with pytest.raises(AppError) as confidentiality_error:
        assert_category_confidentiality(category_max="INTERNAL", requested="RESTRICTED")
    assert confidentiality_error.value.code == "RECORD_CONFIDENTIALITY_EXCEEDED"
    assert transition_seal("ACTIVE", "TRANSFER_PENDING") == "TRANSFER_PENDING"
    with pytest.raises(AppError) as transition_error:
        transition_seal("RETIRED", "ACTIVE")
    assert transition_error.value.code == "SEAL_STATE_INVALID"


def test_payload_hash_is_canonical() -> None:
    assert canonical_payload_hash({"b": 2, "a": 1}) == canonical_payload_hash({"a": 1, "b": 2})

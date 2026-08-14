"""Pure workforce rules and privacy gates."""

from __future__ import annotations

from datetime import date, time

import pytest

from app.core.errors import AppError
from app.modules.workforce.domain.rules import (
    employment_dates,
    fingerprint,
    payload_hash,
    shift_times,
)


def test_fingerprint_is_masked_stable_and_peppered() -> None:
    masked, first = fingerprint("13800138000", pepper="test-pepper-a")
    _, replay = fingerprint("13800138000", pepper="test-pepper-a")
    _, rotated = fingerprint("13800138000", pepper="test-pepper-b")
    assert masked == "***8000"
    assert first == replay
    assert first != rotated
    assert "13800138000" not in str((masked, first))


def test_employment_and_shift_dates_fail_closed() -> None:
    with pytest.raises(AppError) as employment:
        employment_dates(date(2026, 8, 15), date(2026, 8, 14))
    assert employment.value.code == "EMPLOYMENT_DATE_INVALID"
    with pytest.raises(AppError) as shift:
        shift_times(time(9), time(8), False, 60)
    assert shift.value.code == "SHIFT_TIME_INVALID"


def test_command_hash_is_canonical() -> None:
    assert payload_hash({"b": 2, "a": 1}) == payload_hash({"a": 1, "b": 2})

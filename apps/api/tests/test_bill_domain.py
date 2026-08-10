from datetime import date
from decimal import Decimal

import pytest

from app.modules.billing.domain.rules import (
    assert_transition,
    is_overdue,
    line_amount,
    status_from_paid,
)


def test_bill_transitions_and_overdue() -> None:
    assert assert_transition("DRAFT", "ISSUED") == "ISSUED"
    with pytest.raises(ValueError):
        assert_transition("PAID", "ISSUED")
    assert is_overdue(
        status="ISSUED",
        due_date=date(2020, 1, 1),
        total_amount=Decimal("100"),
        paid_amount=Decimal("0"),
        today=date(2020, 2, 1),
    )
    assert status_from_paid(Decimal("100"), Decimal("40"), "ISSUED") == "PARTIALLY_PAID"
    assert line_amount(Decimal("2"), Decimal("3.333"), None) == Decimal("6.67")

"""Pure-domain regression tests for tenant service work orders."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.errors import AppError
from app.modules.facility_ops.domain.work_order import (
    calculate_lines,
    mask_phone,
    sla_status,
    transition,
)


def test_quote_calculation_uses_decimal_and_rejects_claimed_mismatch() -> None:
    lines, total = calculate_lines(
        [
            {
                "line_type": "MATERIAL",
                "description": "零件",
                "quantity": "1.2345",
                "unit": "件",
                "unit_price": "8.88",
                "amount": "10.96",
            }
        ]
    )
    assert total == Decimal("10.96")
    assert lines[0]["quantity"] == Decimal("1.2345")

    with pytest.raises(AppError, match="报价行金额"):
        calculate_lines(
            [
                {
                    "line_type": "LABOR",
                    "description": "人工",
                    "quantity": "2",
                    "unit": "小时",
                    "unit_price": "50",
                    "amount": "99",
                }
            ]
        )


def test_state_machine_requires_quote_and_tenant_acceptance() -> None:
    assert transition("SUBMITTED", "DISPATCH") == "ASSIGNED"
    assert transition("ASSIGNED", "ACCEPT") == "IN_PROGRESS"
    assert transition("IN_PROGRESS", "REQUEST_QUOTE") == "WAITING_QUOTE_APPROVAL"
    assert (
        transition("WAITING_QUOTE_APPROVAL", "QUOTE_ACCEPT")
        == "IN_PROGRESS_AFTER_QUOTE"
    )
    assert (
        transition("IN_PROGRESS_AFTER_QUOTE", "SUBMIT_COMPLETION")
        == "WAITING_ACCEPTANCE"
    )
    assert transition("WAITING_ACCEPTANCE", "ACCEPT_WORK") == "COMPLETED"
    assert (
        transition("WAITING_ACCEPTANCE", "REWORK", has_accepted_quote=True)
        == "IN_PROGRESS_AFTER_QUOTE"
    )
    with pytest.raises(AppError, match="不允许"):
        transition("SUBMITTED", "SUBMIT_COMPLETION")


def test_sla_and_phone_masking_are_truthful() -> None:
    now = datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc).replace(tzinfo=None)
    assert (
        sla_status(
            now=now,
            status="ASSIGNED",
            response_due_at=now - timedelta(minutes=1),
            resolution_due_at=now + timedelta(hours=1),
            first_responded_at=None,
            completed_at=None,
        )
        == "RESPONSE_BREACHED"
    )
    assert mask_phone("+86 138-0013-8000") == "861****8000"
    assert mask_phone("1234567") == "*******"

"""Deterministic exit meter and financial-clearance calculations."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable, Mapping

from app.modules.lease.domain.errors import LeaseDomainError
from app.modules.lease.domain.versioning import snapshot_checksum

EXIT_ITEM_TYPES = frozenset({"RECEIVABLE", "DEDUCTION", "REFUND"})
EXIT_STATUSES = frozenset({"DRAFT", "SUBMITTED", "APPROVED", "CLOSED", "REJECTED", "WITHDRAWN"})
OPEN_EXIT_STATUSES = frozenset({"DRAFT", "SUBMITTED", "APPROVED"})
MONEY = Decimal("0.01")

_EXIT_TRANSITIONS = {
    "DRAFT": frozenset({"SUBMITTED"}),
    "SUBMITTED": frozenset({"APPROVED", "REJECTED", "WITHDRAWN"}),
    "APPROVED": frozenset({"CLOSED"}),
    "CLOSED": frozenset(),
    "REJECTED": frozenset(),
    "WITHDRAWN": frozenset(),
}


def _money(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise LeaseDomainError("LEASE_EXIT_ITEM_INVALID", f"{field} must be decimal") from exc
    if not result.is_finite() or result < 0:
        raise LeaseDomainError("LEASE_EXIT_ITEM_INVALID", f"{field} must be non-negative")
    return result.quantize(MONEY, rounding=ROUND_HALF_UP)


def assert_exit_status_transition(current: str, new: str) -> str:
    current_status = (current or "").strip().upper()
    next_status = (new or "").strip().upper()
    if current_status not in EXIT_STATUSES or next_status not in EXIT_STATUSES:
        raise LeaseDomainError("LEASE_EXIT_STATUS_INVALID", "exit status is invalid")
    if current_status == next_status:
        return next_status
    if next_status not in _EXIT_TRANSITIONS[current_status]:
        raise LeaseDomainError(
            "LEASE_EXIT_STATUS_INVALID", f"illegal exit transition {current_status} -> {next_status}"
        )
    return next_status


def validate_meter_readings(readings: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Reject unexplained regressions and normalize readings for a checksum."""

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in readings:
        meter_code = str(raw.get("meter_code") or "").strip()
        if not meter_code or meter_code in seen:
            raise LeaseDomainError("LEASE_EXIT_ITEM_INVALID", "meter_code must be unique")
        seen.add(meter_code)
        previous = _money(raw.get("previous_reading", 0), "previous_reading")
        current = _money(raw.get("current_reading", 0), "current_reading")
        reason = str(raw.get("regression_reason") or "").strip() or None
        if current < previous and not reason:
            raise LeaseDomainError(
                "LEASE_EXIT_ITEM_INVALID", "regressed meter reading requires a reason"
            )
        result.append(
            {
                "meter_code": meter_code,
                "previous_reading": previous,
                "current_reading": current,
                "regression_reason": reason,
            }
        )
    return sorted(result, key=lambda row: row["meter_code"])


def calculate_exit_totals(
    *,
    held_deposit_amount: Any,
    outstanding_amount: Any,
    items: Iterable[Any],
    meter_readings: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Return explicit two-direction totals and a stable evidence checksum."""

    deposit = _money(held_deposit_amount, "held_deposit_amount")
    outstanding = _money(outstanding_amount, "outstanding_amount")
    receivable = outstanding
    deduction = Decimal("0.00")
    refund = Decimal("0.00")
    normalized_items: list[dict[str, Any]] = []
    for index, value in enumerate(items):
        raw = asdict(value) if is_dataclass(value) else dict(value)
        item_type = str(raw.get("item_type") or "").strip().upper()
        if item_type not in EXIT_ITEM_TYPES:
            raise LeaseDomainError("LEASE_EXIT_ITEM_INVALID", "unsupported exit item type")
        amount = _money(raw.get("amount"), "item amount")
        description = str(raw.get("description") or "").strip()
        if not description:
            raise LeaseDomainError("LEASE_EXIT_ITEM_INVALID", "item description is required")
        approved = bool(raw.get("approved", True))
        if approved:
            if item_type == "RECEIVABLE":
                receivable += amount
            elif item_type == "DEDUCTION":
                deduction += amount
            else:
                refund += amount
        normalized_items.append(
            {
                "item_type": item_type,
                "amount": amount,
                "description": description,
                "evidence_ref": raw.get("evidence_ref"),
                "approved": approved,
                "sort_order": int(raw.get("sort_order", index)),
            }
        )
    receivable = receivable.quantize(MONEY, rounding=ROUND_HALF_UP)
    deduction = deduction.quantize(MONEY, rounding=ROUND_HALF_UP)
    refund = refund.quantize(MONEY, rounding=ROUND_HALF_UP)
    balance = deposit + refund - receivable - deduction
    due_to_party = max(balance, Decimal("0")).quantize(MONEY, rounding=ROUND_HALF_UP)
    due_from_party = max(-balance, Decimal("0")).quantize(MONEY, rounding=ROUND_HALF_UP)
    normalized_items.sort(key=lambda row: (row["sort_order"], row["item_type"], row["description"]))
    meters = validate_meter_readings(meter_readings)
    calculation = {
        "held_deposit_amount": deposit,
        "outstanding_amount": outstanding,
        "receivable_total": receivable,
        "deduction_total": deduction,
        "refund_adjustment_total": refund,
        "net_due_from_party": due_from_party,
        "net_due_to_party": due_to_party,
        "items": normalized_items,
        "meter_readings": meters,
    }
    calculation["checksum"] = snapshot_checksum(calculation)
    return calculation


def assert_financial_clearance(
    *,
    net_due_from_party: Any,
    net_due_to_party: Any,
    status: str,
    evidence_ref: str | None,
    reason: str | None,
) -> None:
    """A non-zero external balance needs a confirmed, reasoned evidence fact."""

    non_zero = _money(net_due_from_party, "net_due_from_party") > 0 or _money(
        net_due_to_party, "net_due_to_party"
    ) > 0
    if non_zero and (
        (status or "").strip().upper() != "CONFIRMED"
        or not (evidence_ref or "").strip()
        or not (reason or "").strip()
    ):
        raise LeaseDomainError(
            "LEASE_FINANCIAL_CLEARANCE_REQUIRED",
            "non-zero settlement needs confirmed external evidence and reason",
        )

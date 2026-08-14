"""Pure work-order lifecycle, money and SLA rules."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from app.core.errors import AppError

PRIORITIES = frozenset({"LOW", "MEDIUM", "HIGH", "URGENT"})
LINE_TYPES = frozenset({"LABOR", "MATERIAL", "OUTSOURCE", "OTHER"})
ACTIVE_STATES = frozenset(
    {
        "SUBMITTED",
        "ASSIGNED",
        "IN_PROGRESS",
        "WAITING_QUOTE_APPROVAL",
        "IN_PROGRESS_AFTER_QUOTE",
        "WAITING_ACCEPTANCE",
    }
)
TERMINAL_STATES = frozenset({"COMPLETED", "CANCELLED"})


def bounded_text(value: object, *, field: str, maximum: int, required: bool = False) -> str:
    result = str(value or "").strip()
    if required and not result:
        raise AppError(f"{field} 必填", code="VALIDATION_ERROR", status_code=400)
    if len(result) > maximum:
        raise AppError(f"{field} 过长", code="VALIDATION_ERROR", status_code=400)
    return result


def money(value: object, *, field: str, allow_zero: bool = True) -> Decimal:
    try:
        result = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise AppError(f"{field} 无效", code="VALIDATION_ERROR", status_code=400) from exc
    if result < 0 or (not allow_zero and result == 0):
        raise AppError(f"{field} 无效", code="VALIDATION_ERROR", status_code=400)
    return result


def quantity(value: object) -> Decimal:
    try:
        result = Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise AppError("quantity 无效", code="VALIDATION_ERROR", status_code=400) from exc
    if result <= 0:
        raise AppError("quantity 必须大于 0", code="VALIDATION_ERROR", status_code=400)
    return result


def calculate_lines(lines: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], Decimal]:
    normalized: list[dict[str, Any]] = []
    total = Decimal("0.00")
    for raw in lines:
        line_type = str(raw.get("line_type") or "").upper()
        if line_type not in LINE_TYPES:
            raise AppError("line_type 无效", code="VALIDATION_ERROR", status_code=400)
        qty = quantity(raw.get("quantity"))
        unit_price = money(raw.get("unit_price"), field="unit_price")
        amount = (qty * unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        claimed = raw.get("amount")
        if claimed is not None and money(claimed, field="amount") != amount:
            raise AppError("报价行金额与数量单价不一致", code="QUOTE_TOTAL_MISMATCH", status_code=400)
        normalized.append(
            {
                "line_type": line_type,
                "description": bounded_text(
                    raw.get("description"), field="description", maximum=255, required=True
                ),
                "quantity": qty,
                "unit": bounded_text(raw.get("unit"), field="unit", maximum=32, required=True),
                "unit_price": unit_price,
                "amount": amount,
            }
        )
        total += amount
    if not normalized:
        raise AppError("报价至少需要一行", code="VALIDATION_ERROR", status_code=400)
    return normalized, total.quantize(Decimal("0.01"))


def assert_version(current: int, expected: int) -> None:
    if int(current) != int(expected):
        raise AppError("工单版本冲突", code="WORK_ORDER_VERSION_CONFLICT", status_code=409)


def transition(status: str, action: str, *, has_accepted_quote: bool = False) -> str:
    current = str(status)
    operation = str(action).upper()
    allowed: dict[tuple[str, str], str] = {
        ("SUBMITTED", "DISPATCH"): "ASSIGNED",
        ("ASSIGNED", "DISPATCH"): "ASSIGNED",
        ("ASSIGNED", "ACCEPT"): "IN_PROGRESS",
        ("IN_PROGRESS", "REQUEST_QUOTE"): "WAITING_QUOTE_APPROVAL",
        ("WAITING_QUOTE_APPROVAL", "QUOTE_ACCEPT"): "IN_PROGRESS_AFTER_QUOTE",
        ("WAITING_QUOTE_APPROVAL", "QUOTE_REJECT"): "WAITING_QUOTE_APPROVAL",
        ("IN_PROGRESS", "SUBMIT_COMPLETION"): "WAITING_ACCEPTANCE",
        ("IN_PROGRESS_AFTER_QUOTE", "SUBMIT_COMPLETION"): "WAITING_ACCEPTANCE",
        ("WAITING_ACCEPTANCE", "ACCEPT_WORK"): "COMPLETED",
        ("WAITING_ACCEPTANCE", "REWORK"): (
            "IN_PROGRESS_AFTER_QUOTE" if has_accepted_quote else "IN_PROGRESS"
        ),
    }
    if operation == "CANCEL" and current in ACTIVE_STATES:
        return "CANCELLED"
    result = allowed.get((current, operation))
    if result is None:
        raise AppError(
            f"状态 {current} 不允许 {operation}",
            code="WORK_ORDER_STATUS_INVALID",
            status_code=409,
        )
    return result


def sla_status(
    *,
    now: datetime,
    status: str,
    response_due_at: datetime | None,
    resolution_due_at: datetime | None,
    first_responded_at: datetime | None,
    completed_at: datetime | None,
) -> str:
    response_late = bool(
        response_due_at
        and ((first_responded_at and first_responded_at > response_due_at) or (not first_responded_at and now > response_due_at))
    )
    resolution_late = bool(
        resolution_due_at
        and ((completed_at and completed_at > resolution_due_at) or (not completed_at and now > resolution_due_at))
    )
    if status == "COMPLETED":
        return "COMPLETED_LATE" if response_late or resolution_late else "COMPLETED_ON_TIME"
    if resolution_late:
        return "RESOLUTION_BREACHED"
    if response_late:
        return "RESPONSE_BREACHED"
    return "ON_TRACK"


def mask_phone(value: object) -> str | None:
    raw = "".join(ch for ch in str(value or "") if ch.isdigit())
    if not raw:
        return None
    if len(raw) <= 7:
        return "*" * len(raw)
    return f"{raw[:3]}****{raw[-4:]}"

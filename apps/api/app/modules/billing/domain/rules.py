"""功能说明：Bill 状态机与金额/逾期规则（纯 Domain）。"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

BILL_STATUSES = frozenset(
    {"DRAFT", "ISSUED", "PARTIALLY_PAID", "PAID", "VOID", "DISCARDED"}
)
FORBIDDEN_STATUSES = frozenset({"OVERDUE"})
EDITABLE = frozenset({"DRAFT"})
FEE_CODES = frozenset(
    {"RENT", "WATER", "ELECTRIC", "MANAGEMENT", "SERVICE", "TAX", "OTHER"}
)

_TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"ISSUED", "DISCARDED"}),
    "ISSUED": frozenset({"PARTIALLY_PAID", "PAID", "VOID"}),
    "PARTIALLY_PAID": frozenset({"PAID", "ISSUED"}),
    "PAID": frozenset(),
    "VOID": frozenset(),
    "DISCARDED": frozenset(),
}


def money(value: Decimal | float | int | str) -> Decimal:
    """功能说明：金额两位小数 HALF_UP。"""

    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def assert_bill_status(status: str) -> str:
    """功能说明：校验账单状态；禁止 OVERDUE。"""

    s = (status or "").strip().upper()
    if s in FORBIDDEN_STATUSES or s not in BILL_STATUSES:
        raise ValueError(f"invalid bill status: {status}")
    return s


def assert_transition(current: str, new: str) -> str:
    """功能说明：校验账单状态迁移。"""

    cur = assert_bill_status(current)
    nxt = assert_bill_status(new)
    if cur == nxt:
        return nxt
    if nxt not in _TRANSITIONS.get(cur, frozenset()):
        raise ValueError(f"illegal bill transition {cur} -> {nxt}")
    return nxt


def assert_fee_code(code: str) -> str:
    """功能说明：校验费项码。"""

    c = (code or "").strip().upper()
    if c not in FEE_CODES:
        raise ValueError(f"invalid fee_code: {code}")
    return c


def line_amount(quantity: Decimal, unit_price: Decimal, amount: Decimal | None) -> Decimal:
    """功能说明：行金额；显式 amount 优先，否则 quantity*unit_price。"""

    if amount is not None:
        return money(amount)
    return money(Decimal(str(quantity)) * Decimal(str(unit_price)))


def open_amount(total: Decimal, paid: Decimal) -> Decimal:
    """功能说明：未结清金额。"""

    return money(Decimal(str(total)) - Decimal(str(paid)))


def status_from_paid(total: Decimal, paid: Decimal, current: str) -> str:
    """功能说明：按核销回写主状态（ISSUED/PARTIALLY_PAID/PAID）。"""

    if current in {"VOID", "DISCARDED", "DRAFT"}:
        return current
    total_m, paid_m = money(total), money(paid)
    if paid_m <= 0:
        return "ISSUED"
    if paid_m >= total_m and total_m > 0:
        return "PAID"
    return "PARTIALLY_PAID"


def is_overdue(
    *,
    status: str,
    due_date: date | None,
    total_amount: Decimal,
    paid_amount: Decimal,
    today: date | None = None,
) -> bool:
    """功能说明：衍生逾期；不使用 status=OVERDUE。"""

    day = today or date.today()
    if status not in {"ISSUED", "PARTIALLY_PAID"}:
        return False
    if due_date is None:
        return False
    return due_date < day and open_amount(total_amount, paid_amount) > 0

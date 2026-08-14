"""功能说明：收款登记领域规则。"""

from __future__ import annotations

from decimal import Decimal

from app.modules.billing.domain.rules import money

PAYMENT_METHODS = frozenset({"CASH", "TRANSFER", "POS", "WECHAT", "ALIPAY", "AGGREGATE", "OTHER"})
PAYMENT_STATUSES = frozenset({"CONFIRMED", "REVERSED"})


def assert_method(method: str) -> str:
    """功能说明：校验收款方式。"""

    m = (method or "").strip().upper()
    if m not in PAYMENT_METHODS:
        raise ValueError(f"invalid payment method: {method}")
    return m


def assert_payment_status(status: str) -> str:
    """功能说明：校验收款状态。"""

    s = (status or "").strip().upper()
    if s not in PAYMENT_STATUSES:
        raise ValueError(f"invalid payment status: {status}")
    return s


def assert_allocations_within_payment(payment_amount: Decimal, allocation_sum: Decimal) -> None:
    """功能说明：分摊合计不超过收款金额。"""

    if money(allocation_sum) > money(payment_amount):
        raise ValueError("allocations exceed payment amount")


def unapplied_amount(
    payment_amount: Decimal, allocation_sum: Decimal, *, payment_status: str = "CONFIRMED"
) -> Decimal:
    """Available balance for a live Payment; reversed money is never reusable."""

    if assert_payment_status(payment_status) == "REVERSED":
        return Decimal("0.00")
    value = money(Decimal(str(payment_amount)) - Decimal(str(allocation_sum)))
    if value < 0:
        raise ValueError("allocations exceed payment amount")
    return value


def mask_account(value: str | None) -> str | None:
    """Keep only a bounded masked account representation."""

    normalized = "".join(ch for ch in (value or "") if ch.isalnum())
    if not normalized:
        return None
    if len(normalized) <= 4:
        return "****"
    return f"****{normalized[-4:]}"

"""功能说明：收款登记领域规则。"""

from __future__ import annotations

from decimal import Decimal

from app.modules.billing.domain.rules import money

PAYMENT_METHODS = frozenset({"CASH", "TRANSFER", "WECHAT", "ALIPAY", "OTHER"})
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

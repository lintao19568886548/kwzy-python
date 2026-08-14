"""Read-only Billing boundary used by Lease exit settlement snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class BillingOutstandingSnapshot:
    amount: Decimal
    currency: str
    source: str
    as_of: datetime


class BillingOutstandingReadPort(Protocol):
    def for_contract(self, contract_id: int) -> BillingOutstandingSnapshot: ...

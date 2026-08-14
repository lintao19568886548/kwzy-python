"""Deterministic Lease charge validation and performance schedule generation."""

from __future__ import annotations

import calendar
from dataclasses import asdict, is_dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable, Mapping

from app.modules.lease.domain.entities import LeasePerformanceScheduleEntity
from app.modules.lease.domain.errors import LeaseDomainError
from app.modules.lease.domain.versioning import snapshot_checksum

CALCULATION_METHODS = frozenset({"FIXED", "PER_AREA"})
BILLING_CYCLES = frozenset({"MONTHLY", "QUARTERLY", "SEMI_ANNUAL", "ANNUAL", "ONE_TIME"})
CHARGE_TYPES = frozenset({"RENT", "PROPERTY_FEE", "SERVICE_FEE", "UTILITIES", "DEPOSIT", "OTHER"})
SUPPORTED_CURRENCIES = frozenset({"CNY"})
RULE_TYPES = frozenset({"RENT_FREE", "ESCALATION"})
MONEY = Decimal("0.01")

_CYCLE_MONTHS = {
    "MONTHLY": 1,
    "QUARTERLY": 3,
    "SEMI_ANNUAL": 6,
    "ANNUAL": 12,
}


def money(value: Decimal | str | int | float) -> Decimal:
    value = Decimal(str(value))
    if not value.is_finite():
        raise LeaseDomainError("LEASE_CHARGE_INVALID", "money value must be finite")
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _data(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    raise LeaseDomainError("LEASE_CHARGE_INVALID", "charge must be an object")


def _as_date(value: Any, field: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise LeaseDomainError("LEASE_CHARGE_INVALID", f"{field} must be an ISO date") from exc


def _as_decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise LeaseDomainError("LEASE_CHARGE_INVALID", f"{field} must be decimal") from exc
    if not result.is_finite():
        raise LeaseDomainError("LEASE_CHARGE_INVALID", f"{field} must be finite")
    return result


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _due_date(period_start: date, due_day: int) -> date:
    day = min(due_day, calendar.monthrange(period_start.year, period_start.month)[1])
    return date(period_start.year, period_start.month, day)


def validate_charge_items(
    charges: Iterable[Any],
    *,
    contract_start: date,
    contract_end: date,
    contract_currency: str = "CNY",
) -> list[dict[str, Any]]:
    """Validate and normalize structured charges in deterministic order."""

    if contract_end < contract_start:
        raise LeaseDomainError("LEASE_CHARGE_INVALID", "contract period is invalid")
    currency = (contract_currency or "").strip().upper()
    if currency not in SUPPORTED_CURRENCIES:
        raise LeaseDomainError("LEASE_CHARGE_INVALID", f"unsupported currency: {currency}")

    result: list[dict[str, Any]] = []
    codes: set[str] = set()
    for index, raw_value in enumerate(charges):
        raw = _data(raw_value)
        code = str(raw.get("charge_code") or "").strip().upper()
        charge_type = str(raw.get("charge_type") or "").strip().upper()
        method = str(raw.get("calculation_method") or "").strip().upper()
        cycle = str(raw.get("billing_cycle") or "").strip().upper()
        item_currency = str(raw.get("currency") or currency).strip().upper()
        start = _as_date(raw.get("start_date"), "start_date")
        end = _as_date(raw.get("end_date"), "end_date")
        if not code or code in codes:
            raise LeaseDomainError("LEASE_CHARGE_INVALID", "charge_code must be tenant-unique")
        codes.add(code)
        if charge_type not in CHARGE_TYPES:
            raise LeaseDomainError("LEASE_CHARGE_INVALID", f"unsupported charge type: {charge_type}")
        if method not in CALCULATION_METHODS or cycle not in BILLING_CYCLES:
            raise LeaseDomainError("LEASE_CHARGE_INVALID", "unsupported calculation method or cycle")
        if item_currency != currency or item_currency not in SUPPORTED_CURRENCIES:
            raise LeaseDomainError("LEASE_CHARGE_INVALID", "charge currency must match contract")
        if start < contract_start or end > contract_end or end < start:
            raise LeaseDomainError("LEASE_CHARGE_INVALID", "charge dates must be within contract")
        due_day = int(raw.get("due_day") or 1)
        if not 1 <= due_day <= 31:
            raise LeaseDomainError("LEASE_CHARGE_INVALID", "due_day must be between 1 and 31")
        tax_rate = _as_decimal(raw.get("tax_rate") or 0, "tax_rate")
        if tax_rate < 0 or tax_rate > 1:
            raise LeaseDomainError("LEASE_CHARGE_INVALID", "tax_rate must be between 0 and 1")
        amount = None
        unit_price = None
        if method == "FIXED":
            amount = _as_decimal(raw.get("amount"), "amount")
            if amount <= 0:
                raise LeaseDomainError("LEASE_CHARGE_INVALID", "fixed amount must be positive")
        else:
            unit_price = _as_decimal(raw.get("unit_price"), "unit_price")
            if unit_price <= 0:
                raise LeaseDomainError("LEASE_CHARGE_INVALID", "unit price must be positive")
        result.append(
            {
                "id": raw.get("id"),
                "charge_code": code,
                "charge_type": charge_type,
                "calculation_method": method,
                "billing_cycle": cycle,
                "currency": item_currency,
                "start_date": start,
                "end_date": end,
                "due_day": due_day,
                "amount": amount,
                "unit_price": unit_price,
                "tax_rate": tax_rate,
                "sort_order": int(raw.get("sort_order", index)),
            }
        )
    return sorted(result, key=lambda row: (row["sort_order"], row["charge_code"]))


def _periods(charge: Mapping[str, Any]) -> list[tuple[date, date]]:
    start = charge["start_date"]
    end = charge["end_date"]
    if charge["billing_cycle"] == "ONE_TIME":
        return [(start, start)]
    months = _CYCLE_MONTHS[charge["billing_cycle"]]
    rows: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        next_start = _add_months(cursor, months)
        rows.append((cursor, min(end, next_start - timedelta(days=1))))
        cursor = next_start
    return rows


def _normalize_rules(
    rules: Iterable[Mapping[str, Any]],
    charge_periods: dict[str, list[tuple[date, date]]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(rules):
        rule_type = str(raw.get("rule_type") or raw.get("type") or "").strip().upper()
        charge_code = str(raw.get("charge_code") or "").strip().upper()
        if rule_type not in RULE_TYPES or charge_code not in charge_periods:
            raise LeaseDomainError("LEASE_CHARGE_INVALID", "pricing rule type or charge is invalid")
        effective = _as_date(raw.get("effective_date"), "effective_date")
        periods = charge_periods[charge_code]
        starts = {period_start for period_start, _ in periods}
        if effective not in starts:
            raise LeaseDomainError(
                "LEASE_PRORATION_UNSUPPORTED", "pricing rule must start at a cycle boundary"
            )
        end = _as_date(raw.get("end_date"), "end_date") if raw.get("end_date") else None
        rate = None
        replacement = None
        if rule_type == "RENT_FREE":
            if end is None:
                raise LeaseDomainError("LEASE_CHARGE_INVALID", "rent-free rule needs end_date")
            matching_ends = {period_end for _, period_end in periods}
            if end not in matching_ends or end < effective:
                raise LeaseDomainError(
                    "LEASE_PRORATION_UNSUPPORTED", "rent-free rule must cover complete cycles"
                )
        else:
            if raw.get("rate") is not None:
                rate = _as_decimal(raw.get("rate"), "rate")
                if rate <= Decimal("-1"):
                    raise LeaseDomainError("LEASE_CHARGE_INVALID", "escalation rate is invalid")
            if raw.get("replacement_amount") is not None:
                replacement = _as_decimal(raw.get("replacement_amount"), "replacement_amount")
                if replacement <= 0:
                    raise LeaseDomainError("LEASE_CHARGE_INVALID", "replacement amount is invalid")
            if (rate is None) == (replacement is None):
                raise LeaseDomainError(
                    "LEASE_CHARGE_INVALID", "escalation needs exactly one rate or replacement"
                )
        normalized.append(
            {
                "rule_type": rule_type,
                "charge_code": charge_code,
                "effective_date": effective,
                "end_date": end,
                "rate": rate,
                "replacement_amount": replacement,
                "rule_ref": str(raw.get("rule_ref") or f"RULE-{index + 1}"),
            }
        )
    normalized.sort(key=lambda row: (row["charge_code"], row["effective_date"], row["rule_ref"]))
    seen_escalations: set[tuple[str, date]] = set()
    for rule in normalized:
        if rule["rule_type"] == "ESCALATION":
            key = (rule["charge_code"], rule["effective_date"])
            if key in seen_escalations:
                raise LeaseDomainError("LEASE_CHARGE_INVALID", "ambiguous escalation rules")
            seen_escalations.add(key)
    return normalized


def generate_performance_schedule(
    *,
    tenant_id: int,
    contract_id: int,
    contract_version_no: int,
    contract_start: date,
    contract_end: date,
    charges: Iterable[Any],
    units: Iterable[Mapping[str, Any]],
    rules: Iterable[Mapping[str, Any]] = (),
    contract_currency: str = "CNY",
) -> list[LeasePerformanceScheduleEntity]:
    """Generate stable schedule rows without creating downstream Billing records."""

    normalized_charges = validate_charge_items(
        charges,
        contract_start=contract_start,
        contract_end=contract_end,
        contract_currency=contract_currency,
    )
    try:
        total_area = sum(
            (_as_decimal(unit.get("occupied_area"), "occupied_area") for unit in units),
            Decimal("0"),
        )
    except AttributeError as exc:
        raise LeaseDomainError("LEASE_CHARGE_AREA_REQUIRED", "unit area is invalid") from exc
    if total_area < 0:
        raise LeaseDomainError("LEASE_CHARGE_AREA_REQUIRED", "occupied area cannot be negative")

    charge_periods = {charge["charge_code"]: _periods(charge) for charge in normalized_charges}
    normalized_rules = _normalize_rules(rules, charge_periods)
    rows: list[LeasePerformanceScheduleEntity] = []
    for charge in normalized_charges:
        if charge["calculation_method"] == "PER_AREA" and total_area <= 0:
            raise LeaseDomainError(
                "LEASE_CHARGE_AREA_REQUIRED", "positive proposed occupied area is required"
            )
        base_amount = (
            charge["amount"]
            if charge["calculation_method"] == "FIXED"
            else total_area * charge["unit_price"]
        )
        active_amount = base_amount
        charge_rules = [r for r in normalized_rules if r["charge_code"] == charge["charge_code"]]
        for period_start, period_end in charge_periods[charge["charge_code"]]:
            refs: list[str] = []
            for rule in charge_rules:
                if rule["rule_type"] == "ESCALATION" and rule["effective_date"] == period_start:
                    active_amount = (
                        rule["replacement_amount"]
                        if rule["replacement_amount"] is not None
                        else active_amount * (Decimal("1") + rule["rate"])
                    )
                    refs.append(rule["rule_ref"])
            net = money(active_amount)
            for rule in charge_rules:
                if rule["rule_type"] != "RENT_FREE":
                    continue
                overlaps = rule["effective_date"] <= period_end and rule["end_date"] >= period_start
                fully_covers = rule["effective_date"] <= period_start and rule["end_date"] >= period_end
                if overlaps and not fully_covers:
                    raise LeaseDomainError(
                        "LEASE_PRORATION_UNSUPPORTED", "rent-free rule intersects a partial cycle"
                    )
                if fully_covers:
                    net = Decimal("0.00")
                    refs.append(rule["rule_ref"])
            tax = money(net * charge["tax_rate"])
            gross = money(net + tax)
            schedule_key = (
                f"LEASE-{int(tenant_id)}-{int(contract_id)}-{int(contract_version_no)}-"
                f"{charge['charge_code']}-{period_start.isoformat()}"
            )
            rows.append(
                LeasePerformanceScheduleEntity(
                    tenant_id=int(tenant_id),
                    contract_id=int(contract_id),
                    contract_version_no=int(contract_version_no),
                    charge_item_id=charge.get("id"),
                    charge_code=charge["charge_code"],
                    schedule_key=schedule_key,
                    period_start=period_start,
                    period_end=period_end,
                    due_date=_due_date(period_start, charge["due_day"]),
                    currency=charge["currency"],
                    area=total_area,
                    unit_price=charge["unit_price"],
                    net_amount=net,
                    tax_amount=tax,
                    gross_amount=gross,
                    rule_refs=tuple(sorted(refs)),
                )
            )
    return rows


def schedule_checksum(rows: Iterable[LeasePerformanceScheduleEntity]) -> str:
    return snapshot_checksum({"schedule": [asdict(row) for row in rows]})

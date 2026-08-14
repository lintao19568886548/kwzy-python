"""Typed contract change-order invariants and lifecycle rules."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Mapping

from app.modules.lease.domain.errors import LeaseDomainError

CHANGE_TYPES = frozenset(
    {
        "RENEWAL",
        "EXPANSION",
        "REDUCTION",
        "UNIT_TRANSFER",
        "PRICE_ADJUSTMENT",
        "PARTY_TRANSFER",
        "EARLY_TERMINATION",
    }
)
CHANGE_STATUSES = frozenset(
    {"DRAFT", "SUBMITTED", "APPROVED", "APPLIED", "REJECTED", "WITHDRAWN", "CANCELLED"}
)
IN_FLIGHT_CHANGE_STATUSES = frozenset({"SUBMITTED", "APPROVED"})

_CHANGE_TRANSITIONS = {
    "DRAFT": frozenset({"SUBMITTED", "CANCELLED"}),
    "SUBMITTED": frozenset({"APPROVED", "REJECTED", "WITHDRAWN"}),
    "APPROVED": frozenset({"APPLIED", "CANCELLED"}),
    "APPLIED": frozenset(),
    "REJECTED": frozenset(),
    "WITHDRAWN": frozenset(),
    "CANCELLED": frozenset(),
}


def _as_date(value: Any, field: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise LeaseDomainError("LEASE_CHANGE_INVALID", f"{field} must be an ISO date") from exc


def _contract(snapshot: Mapping[str, Any]) -> Mapping[str, Any]:
    contract = snapshot.get("contract")
    if not isinstance(contract, Mapping):
        raise LeaseDomainError("LEASE_CHANGE_INVALID", "complete contract snapshot is required")
    return contract


def _units(snapshot: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    units = snapshot.get("units")
    if not isinstance(units, list):
        raise LeaseDomainError("LEASE_CHANGE_INVALID", "complete unit snapshot is required")
    result: list[Mapping[str, Any]] = []
    seen: set[int] = set()
    for unit in units:
        if not isinstance(unit, Mapping):
            raise LeaseDomainError("LEASE_CHANGE_INVALID", "unit snapshot is invalid")
        try:
            unit_id = int(unit["unit_id"])
            area = Decimal(str(unit["occupied_area"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise LeaseDomainError("LEASE_CHANGE_INVALID", "unit id or area is invalid") from exc
        if unit_id in seen or area <= 0:
            raise LeaseDomainError("LEASE_CHANGE_INVALID", "units must be unique with positive area")
        seen.add(unit_id)
        result.append(unit)
    return result


def _unit_areas(snapshot: Mapping[str, Any]) -> dict[int, Decimal]:
    return {int(unit["unit_id"]): Decimal(str(unit["occupied_area"])) for unit in _units(snapshot)}


def _changed_contract_fields(before: Mapping[str, Any], after: Mapping[str, Any]) -> set[str]:
    keys = set(before) | set(after)
    return {key for key in keys if before.get(key) != after.get(key)}


def assert_change_status_transition(current: str, new: str) -> str:
    current_status = (current or "").strip().upper()
    next_status = (new or "").strip().upper()
    if current_status not in CHANGE_STATUSES or next_status not in CHANGE_STATUSES:
        raise LeaseDomainError("LEASE_CHANGE_STATUS_INVALID", "change status is invalid")
    if current_status == next_status:
        return next_status
    if next_status not in _CHANGE_TRANSITIONS[current_status]:
        raise LeaseDomainError(
            "LEASE_CHANGE_STATUS_INVALID",
            f"illegal change transition {current_status} -> {next_status}",
        )
    return next_status


def validate_change_proposal(
    change_type: str,
    *,
    current_snapshot: Mapping[str, Any],
    proposed_snapshot: Mapping[str, Any],
    effective_date: date,
    reason: str,
    today: date | None = None,
    cycle_boundaries: set[date] | None = None,
    target_party_eligible: bool | None = None,
) -> dict[str, Any]:
    """Validate all seven change types over a complete proposed future state."""

    normalized_type = (change_type or "").strip().upper()
    if normalized_type not in CHANGE_TYPES or not (reason or "").strip():
        raise LeaseDomainError("LEASE_CHANGE_INVALID", "change type and reason are required")
    if not isinstance(current_snapshot, Mapping) or not isinstance(proposed_snapshot, Mapping):
        raise LeaseDomainError("LEASE_CHANGE_INVALID", "complete snapshots are required")
    before = _contract(current_snapshot)
    after = _contract(proposed_snapshot)
    before_units = _unit_areas(current_snapshot)
    after_units = _unit_areas(proposed_snapshot)
    changed_contract = _changed_contract_fields(before, after)
    current_day = today or date.today()
    effective = _as_date(effective_date, "effective_date")

    if int(before.get("park_id") or 0) != int(after.get("park_id") or 0):
        raise LeaseDomainError("LEASE_CHANGE_INVALID", "a change cannot move contracts across parks")

    if normalized_type == "RENEWAL":
        old_end = _as_date(before.get("end_date"), "current end_date")
        new_end = _as_date(after.get("end_date"), "proposed end_date")
        allowed = {"start_date", "end_date"}
        if new_end <= old_end or changed_contract - allowed or before_units != after_units:
            raise LeaseDomainError("LEASE_CHANGE_INVALID", "renewal must extend only the contract period")
    elif normalized_type == "EXPANSION":
        for unit_id, area in before_units.items():
            if after_units.get(unit_id, Decimal("0")) < area:
                raise LeaseDomainError("LEASE_CHANGE_INVALID", "expansion cannot reduce existing capacity")
        if sum(after_units.values()) <= sum(before_units.values()) or changed_contract:
            raise LeaseDomainError("LEASE_CHANGE_INVALID", "expansion must add occupied capacity")
    elif normalized_type == "REDUCTION":
        if any(unit_id not in before_units for unit_id in after_units):
            raise LeaseDomainError("LEASE_CHANGE_INVALID", "reduction cannot add a unit")
        if sum(after_units.values()) >= sum(before_units.values()) or changed_contract:
            raise LeaseDomainError("LEASE_CHANGE_INVALID", "reduction must decrease occupied capacity")
    elif normalized_type == "UNIT_TRANSFER":
        if (
            set(before_units) == set(after_units)
            or sum(before_units.values()) != sum(after_units.values())
            or changed_contract
        ):
            raise LeaseDomainError(
                "LEASE_CHANGE_INVALID", "unit transfer must replace units at the same total area"
            )
    elif normalized_type == "PRICE_ADJUSTMENT":
        if changed_contract or before_units != after_units:
            raise LeaseDomainError("LEASE_CHANGE_INVALID", "price adjustment can change pricing only")
        if current_snapshot.get("charges") == proposed_snapshot.get("charges"):
            raise LeaseDomainError("LEASE_CHANGE_INVALID", "price adjustment must change charges")
        if effective < current_day or cycle_boundaries is None or effective not in cycle_boundaries:
            raise LeaseDomainError(
                "LEASE_CHANGE_EFFECTIVE_DATE_INVALID",
                "price adjustment must use a future cycle boundary",
            )
    elif normalized_type == "PARTY_TRANSFER":
        if changed_contract != {"party_id"} or before_units != after_units:
            raise LeaseDomainError("LEASE_CHANGE_INVALID", "party transfer may change Party only")
        if int(before.get("party_id") or 0) == int(after.get("party_id") or 0):
            raise LeaseDomainError("LEASE_CHANGE_INVALID", "target Party must differ")
        if target_party_eligible is not True:
            raise LeaseDomainError("LEASE_PARTY_INELIGIBLE", "target Party is not eligible")
    else:
        start = _as_date(before.get("start_date"), "start_date")
        end = _as_date(before.get("end_date"), "end_date")
        if effective < max(start, current_day) or effective > end:
            raise LeaseDomainError(
                "LEASE_CHANGE_EFFECTIVE_DATE_INVALID", "early termination date is invalid"
            )
        if before_units != after_units:
            raise LeaseDomainError(
                "LEASE_CHANGE_INVALID", "early termination retains occupancy until settlement close"
            )

    return {
        "change_type": normalized_type,
        "effective_date": effective,
        "reason": reason.strip(),
        "proposed_snapshot": dict(proposed_snapshot),
    }


def assert_base_version(current_version_no: int, base_version_no: int) -> int:
    if int(current_version_no) != int(base_version_no):
        raise LeaseDomainError(
            "LEASE_CHANGE_BASE_VERSION_CONFLICT",
            f"change base {base_version_no} differs from current {current_version_no}",
        )
    return int(current_version_no)

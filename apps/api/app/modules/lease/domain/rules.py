"""Lease V2 lifecycle, value-object and occupancy rules."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.modules.lease.domain.errors import LeaseDomainError

LEASE_STATUSES = frozenset(
    {
        "DRAFT",
        "PENDING_APPROVAL",
        "PENDING_ACTIVE",
        "ACTIVE",
        "EXPIRING",
        "EXIT_PENDING",
        "TERMINATED",
        "BREACHED",
        "CANCELLED",
        "RENEWED",  # legacy read compatibility only
    }
)
WRITABLE_LEASE_STATUSES = LEASE_STATUSES - {"RENEWED"}
OCCUPYING_STATUSES = frozenset({"ACTIVE", "EXPIRING", "EXIT_PENDING"})
TERM_TYPES = frozenset({"INCREASE", "RENT_FREE", "OTHER"})
EDITABLE_STATUSES = frozenset({"DRAFT"})
UNIT_RENTABLE_STATUSES = frozenset({"VACANT", "RESERVED", "OCCUPIED"})
DEFAULT_EXPIRING_DAYS = 30

_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"PENDING_APPROVAL", "CANCELLED"}),
    "PENDING_APPROVAL": frozenset({"PENDING_ACTIVE", "DRAFT", "CANCELLED"}),
    "PENDING_ACTIVE": frozenset({"ACTIVE", "DRAFT", "CANCELLED"}),
    "ACTIVE": frozenset({"EXPIRING", "EXIT_PENDING"}),
    "EXPIRING": frozenset({"ACTIVE", "EXIT_PENDING"}),
    # Rejected/withdrawn exit governance restores the pre-exit occupying state.
    "EXIT_PENDING": frozenset({"ACTIVE", "EXPIRING", "TERMINATED", "BREACHED"}),
    "TERMINATED": frozenset(),
    "BREACHED": frozenset(),
    "CANCELLED": frozenset(),
    "RENEWED": frozenset(),
}

# The existing /api/v1/leases compatibility surface keeps its historical direct
# submit/terminate transitions until callers migrate to governed V2 commands.
_LEGACY_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"PENDING_ACTIVE", "CANCELLED"}),
    "PENDING_ACTIVE": frozenset({"ACTIVE", "DRAFT", "CANCELLED"}),
    "ACTIVE": frozenset({"EXPIRING", "RENEWED", "TERMINATED", "BREACHED"}),
    "EXPIRING": frozenset({"ACTIVE", "RENEWED", "TERMINATED", "BREACHED"}),
    "RENEWED": frozenset(),
    "TERMINATED": frozenset(),
    "BREACHED": frozenset(),
    "CANCELLED": frozenset(),
}


def assert_lease_status(status: str, *, for_write: bool = False) -> str:
    normalized = (status or "").strip().upper()
    allowed = WRITABLE_LEASE_STATUSES if for_write else LEASE_STATUSES
    if normalized not in allowed:
        code = "LEASE_LEGACY_STATUS_READ_ONLY" if normalized == "RENEWED" else "LEASE_STATUS_INVALID"
        raise LeaseDomainError(code, f"invalid lease status: {status}")
    return normalized


def assert_status_transition(current: str, new: str) -> str:
    """Validate the frozen V1 lifecycle used only by compatibility endpoints."""

    current_status = assert_lease_status(current)
    next_status = assert_lease_status(new)
    if current_status == next_status:
        return next_status
    if next_status not in _LEGACY_STATUS_TRANSITIONS.get(current_status, frozenset()):
        raise LeaseDomainError(
            "LEASE_STATUS_INVALID",
            f"illegal lease transition {current_status} -> {next_status}",
        )
    return next_status


def assert_v2_status_transition(current: str, new: str) -> str:
    """Validate governed V2 transitions; new commands must call this function."""

    current_status = assert_lease_status(current)
    next_status = assert_lease_status(new, for_write=True)
    if current_status == next_status:
        return next_status
    if next_status not in _STATUS_TRANSITIONS.get(current_status, frozenset()):
        raise LeaseDomainError(
            "LEASE_STATUS_INVALID",
            f"illegal lease V2 transition {current_status} -> {next_status}",
        )
    return next_status


def assert_direct_edit_allowed(status: str) -> None:
    if assert_lease_status(status) != "DRAFT":
        raise LeaseDomainError(
            "LEASE_CHANGE_ORDER_REQUIRED",
            "effective contract business fields require a governed change order",
        )


def assert_term_type(term_type: str) -> str:
    normalized = (term_type or "").strip().upper()
    if normalized not in TERM_TYPES:
        raise LeaseDomainError("LEASE_TERM_INVALID", f"invalid term_type: {term_type}")
    return normalized


def is_occupying_status(status: str) -> bool:
    try:
        return assert_lease_status(status) in OCCUPYING_STATUSES
    except ValueError:
        return False


def is_editable_status(status: str) -> bool:
    try:
        return assert_lease_status(status) in EDITABLE_STATUSES
    except ValueError:
        return False


def decimal_value(value: Decimal | float | int | str, *, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise LeaseDomainError("LEASE_VALUE_INVALID", f"{field} must be a decimal") from exc
    if not result.is_finite():
        raise LeaseDomainError("LEASE_VALUE_INVALID", f"{field} must be finite")
    return result


def assert_positive_area(area: Decimal | float | int | str) -> Decimal:
    value = decimal_value(area, field="occupied_area")
    if value < 0:
        raise LeaseDomainError("LEASE_UNIT_AREA_INVALID", "occupied_area must be >= 0")
    return value


def assert_capacity(
    rentable_area: Decimal | None,
    current_used: Decimal,
    additional: Decimal,
) -> None:
    if rentable_area is None:
        return
    capacity = decimal_value(rentable_area, field="rentable_area")
    if capacity <= 0:
        return
    used = decimal_value(current_used, field="current_used")
    added = decimal_value(additional, field="additional")
    if used + added > capacity:
        raise LeaseDomainError(
            "OCCUPANCY_CONFLICT",
            f"occupancy exceeds rentable_area: used={used} + add={added} > {capacity}",
        )

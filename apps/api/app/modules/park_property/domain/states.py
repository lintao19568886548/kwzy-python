"""Unit / Park status rules (pure domain)."""

from __future__ import annotations

PARK_STATUSES = frozenset({"ACTIVE", "INACTIVE"})

UNIT_STATUSES = frozenset(
    {"DRAFT", "VACANT", "RESERVED", "OCCUPIED", "MAINTENANCE", "RETIRED"}
)

# Allowed transitions for unit status (step1 simplified)
UNIT_TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"VACANT", "RETIRED"}),
    "VACANT": frozenset({"RESERVED", "OCCUPIED", "MAINTENANCE", "RETIRED"}),
    "RESERVED": frozenset({"VACANT", "OCCUPIED", "RETIRED"}),
    "OCCUPIED": frozenset({"VACANT", "MAINTENANCE", "RETIRED"}),
    "MAINTENANCE": frozenset({"VACANT", "OCCUPIED", "RETIRED"}),
    "RETIRED": frozenset(),
}


def assert_park_status(status: str) -> str:
    value = (status or "").upper()
    if value not in PARK_STATUSES:
        raise ValueError(f"非法园区状态: {status}")
    return value


def assert_unit_status(status: str) -> str:
    value = (status or "").upper()
    if value not in UNIT_STATUSES:
        raise ValueError(f"非法单元状态: {status}")
    return value


def can_transition_unit(current: str, target: str) -> bool:
    current_u = assert_unit_status(current)
    target_u = assert_unit_status(target)
    if current_u == target_u:
        return True
    return target_u in UNIT_TRANSITIONS.get(current_u, frozenset())


def transition_unit_status(current: str, target: str) -> str:
    target_u = assert_unit_status(target)
    if not can_transition_unit(current, target_u):
        raise ValueError(f"单元状态不可从 {current} 迁移到 {target_u}")
    return target_u

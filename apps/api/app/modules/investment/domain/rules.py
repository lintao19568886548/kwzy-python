"""功能说明：招商线索状态与字段规则。"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Iterable

from app.modules.investment.domain.entities import AssignmentMemberSpec, IntentSnapshot, ViewingWindow

VALID_STATUSES = frozenset(
    {
        "NEW",
        "CONTACTING",
        "VISITING",
        "QUOTING",
        "NEGOTIATING",
        "WON",
        "LOST",
        "CANCELLED",
        "MERGED",
    }
)
CONVERTIBLE = frozenset({"NEW", "CONTACTING", "VISITING", "QUOTING", "NEGOTIATING"})
OPEN_STATUSES = CONVERTIBLE
VALID_INTENT = frozenset({"A", "B", "C", "HIGH", "MEDIUM", "LOW", ""})
VALID_ACTIVITY_TYPES = frozenset({"CALL", "NOTE", "VISIT", "QUOTE", "NEGOTIATION", "SYSTEM"})
ASSIGNMENT_TRIGGERS = frozenset({"MANUAL_CREATE", "CHANNEL_INTAKE", "RECYCLE"})
VIEWING_STATUSES = frozenset({"SCHEDULED", "CONFIRMED", "COMPLETED", "CANCELLED", "NO_SHOW"})
INTENT_STATUSES = frozenset({"DRAFT", "PENDING", "APPROVED", "REJECTED", "RETURNED", "WITHDRAWN"})


def normalize_status(raw: str | None) -> str:
    value = str(raw or "").strip().upper()
    if value == "FOLLOWING":
        value = "CONTACTING"
    if value not in VALID_STATUSES:
        raise ValueError("线索状态无效")
    return value


def assert_status_transition(
    current: str,
    target: str,
    *,
    allow_regression: bool = False,
) -> str:
    current = normalize_status(current)
    target = normalize_status(target)
    if current == target:
        return target
    ordered_open = ["NEW", "CONTACTING", "VISITING", "QUOTING", "NEGOTIATING"]
    if (
        allow_regression
        and current in ordered_open
        and target in ordered_open
        and ordered_open.index(target) < ordered_open.index(current)
    ):
        return target
    allowed: dict[str, set[str]] = {
        "NEW": {"CONTACTING", "LOST", "CANCELLED"},
        "CONTACTING": {"VISITING", "LOST", "CANCELLED"},
        "VISITING": {"QUOTING", "LOST", "CANCELLED"},
        "QUOTING": {"NEGOTIATING", "LOST", "CANCELLED"},
        "NEGOTIATING": {"WON", "LOST", "CANCELLED"},
        "WON": set(),
        "LOST": set(),
        "CANCELLED": set(),
        "MERGED": set(),
    }
    if target not in allowed.get(current, set()):
        raise ValueError(f"线索状态不可从 {current} 转为 {target}")
    return target


def normalize_intent_level(raw: str | None) -> str | None:
    if raw is None or str(raw).strip() == "":
        return None
    v = str(raw).strip().upper()
    if v not in VALID_INTENT - {""}:
        raise ValueError("intent_level 无效")
    return v


def normalize_phone(phone: str) -> str:
    p = (phone or "").strip()
    if len(p) < 5 or len(p) > 32:
        raise ValueError("contact_phone 长度无效")
    return p


def normalize_phone_key(phone: str) -> str:
    normalize_phone(phone)
    return "".join(ch for ch in phone.strip() if ch.isdigit() or ch == "+")


def normalize_name_key(name: str) -> str:
    return " ".join(str(name or "").strip().lower().split())


def mask_phone(phone: str | None) -> str | None:
    if not phone or len(phone) < 7:
        return phone
    return phone[:3] + "****" + phone[-4:]


def assert_activity_type(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in VALID_ACTIVITY_TYPES:
        raise ValueError("activity_type 无效")
    return normalized


def normalize_assignment_trigger(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in ASSIGNMENT_TRIGGERS:
        raise ValueError("assignment trigger 无效")
    return normalized


def validate_assignment_members(
    members: Iterable[AssignmentMemberSpec],
) -> tuple[AssignmentMemberSpec, ...]:
    normalized = tuple(members)
    if not normalized or len(normalized) > 100:
        raise ValueError("assignment members 数量须为 1-100")
    user_ids: set[int] = set()
    orders: set[int] = set()
    for member in normalized:
        if member.user_id <= 0 or member.capacity <= 0 or member.capacity > 10000:
            raise ValueError("assignment member 用户或容量无效")
        if member.weight <= 0 or member.weight > 100 or member.member_order <= 0:
            raise ValueError("assignment member 权重或顺序无效")
        if member.user_id in user_ids or member.member_order in orders:
            raise ValueError("assignment member 用户和顺序不得重复")
        user_ids.add(member.user_id)
        orders.add(member.member_order)
    return normalized


def assignment_rank(member: AssignmentMemberSpec) -> tuple[Decimal, datetime, int, int]:
    workload = Decimal(member.open_count) / Decimal(member.capacity)
    never_assigned = datetime.min
    return (
        workload,
        member.last_assigned_at or never_assigned,
        member.member_order,
        member.user_id,
    )


def choose_assignment_member(
    members: Iterable[AssignmentMemberSpec],
) -> AssignmentMemberSpec | None:
    validated = validate_assignment_members(members)
    eligible = [
        member
        for member in validated
        if member.eligible and member.open_count < member.capacity
    ]
    return min(eligible, key=assignment_rank) if eligible else None


def validate_viewing_window(window: ViewingWindow) -> ViewingWindow:
    if window.ends_at <= window.starts_at:
        raise ValueError("viewing end 必须晚于 start")
    if window.ends_at - window.starts_at > timedelta(hours=24):
        raise ValueError("viewing 时长不得超过 24 小时")
    if not window.unit_ids or len(window.unit_ids) > 20:
        raise ValueError("viewing units 数量须为 1-20")
    if any(unit_id <= 0 for unit_id in window.unit_ids):
        raise ValueError("viewing unit id 无效")
    if len(set(window.unit_ids)) != len(window.unit_ids):
        raise ValueError("viewing units 不得重复")
    return window


def assert_viewing_transition(current: str, target: str) -> str:
    current = str(current or "").strip().upper()
    target = str(target or "").strip().upper()
    if current not in VIEWING_STATUSES or target not in VIEWING_STATUSES:
        raise ValueError("viewing status 无效")
    if current == target:
        return target
    allowed = {
        "SCHEDULED": {"CONFIRMED", "CANCELLED", "NO_SHOW"},
        "CONFIRMED": {"COMPLETED", "CANCELLED", "NO_SHOW"},
        "COMPLETED": set(),
        "CANCELLED": set(),
        "NO_SHOW": set(),
    }
    if target not in allowed[current]:
        raise ValueError(f"带看状态不可从 {current} 转为 {target}")
    return target


def validate_intent_snapshot(snapshot: IntentSnapshot) -> IntentSnapshot:
    if snapshot.ends_on <= snapshot.starts_on:
        raise ValueError("intent end date 必须晚于 start date")
    if snapshot.valid_until <= datetime.utcnow():
        raise ValueError("intent valid_until 必须在未来")
    if snapshot.valid_until > datetime.utcnow() + timedelta(days=365):
        raise ValueError("intent 有效期不得超过 365 天")
    if snapshot.proposed_unit_price < Decimal("0"):
        raise ValueError("intent proposed_unit_price 不得为负数")
    currency = snapshot.currency.strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError("intent currency 无效")
    if not snapshot.units or len(snapshot.units) > 20:
        raise ValueError("intent units 数量须为 1-20")
    ids: set[int] = set()
    for unit in snapshot.units:
        if unit.unit_id <= 0 or unit.unit_version <= 0 or unit.requested_area <= Decimal("0"):
            raise ValueError("intent unit snapshot 无效")
        if unit.unit_id in ids:
            raise ValueError("intent unit 不得重复")
        ids.add(unit.unit_id)
    if snapshot.remark is not None and len(snapshot.remark.strip()) > 2000:
        raise ValueError("intent remark 过长")
    return snapshot

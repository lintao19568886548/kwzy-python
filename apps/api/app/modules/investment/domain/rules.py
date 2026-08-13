"""功能说明：招商线索状态与字段规则。"""

from __future__ import annotations

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

"""功能说明：招商线索状态与字段规则。"""

from __future__ import annotations

VALID_STATUSES = frozenset({"NEW", "FOLLOWING", "WON", "LOST", "CANCELLED"})
CONVERTIBLE = frozenset({"NEW", "FOLLOWING"})
OPEN_STATUSES = frozenset({"NEW", "FOLLOWING"})
VALID_INTENT = frozenset({"A", "B", "C", "HIGH", "MEDIUM", "LOW", ""})


def assert_status_transition(current: str, target: str) -> str:
    current = (current or "").upper()
    target = (target or "").upper()
    if current == target:
        return target
    allowed: dict[str, set[str]] = {
        "NEW": {"FOLLOWING", "WON", "LOST", "CANCELLED"},
        "FOLLOWING": {"WON", "LOST", "CANCELLED", "NEW"},
        "WON": set(),
        "LOST": {"FOLLOWING"},  # 可复活跟进
        "CANCELLED": set(),
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

"""Pure transition, matching, checksum, and link-safety rules for engagement."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit

from app.core.errors import AppError

CODE_RE = re.compile(r"^[A-Z][A-Z0-9_-]{1,47}$")
SAFE_HOST_RE = re.compile(
    r"^(?=.{1,253}\.?$)(?!-)(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,63}\.?$",
    re.IGNORECASE,
)
ALLOWED_RULE_FIELDS = frozenset(
    {
        "park_id",
        "region_code",
        "party_role",
        "industry_code",
        "enterprise_scale",
        "tag_code",
    }
)
ALLOWED_RULE_OPERATORS = frozenset({"EQ", "IN", "CONTAINS_ANY"})

POLICY_TRANSITIONS = {
    "DRAFT": frozenset({"PENDING_APPROVAL", "WITHDRAWN"}),
    "PENDING_APPROVAL": frozenset({"APPROVED", "REJECTED", "DRAFT", "WITHDRAWN"}),
    "APPROVED": frozenset({"PUBLISHED", "WITHDRAWN"}),
    "PUBLISHED": frozenset({"EXPIRED", "WITHDRAWN"}),
    "REJECTED": frozenset({"DRAFT", "WITHDRAWN"}),
    "EXPIRED": frozenset(),
    "WITHDRAWN": frozenset(),
}
ANNOUNCEMENT_TRANSITIONS = {
    "DRAFT": frozenset({"PENDING_APPROVAL", "WITHDRAWN"}),
    "PENDING_APPROVAL": frozenset({"APPROVED", "REJECTED", "DRAFT", "WITHDRAWN"}),
    "APPROVED": frozenset({"SCHEDULED", "PUBLISHED", "WITHDRAWN"}),
    "SCHEDULED": frozenset({"PUBLISHED", "WITHDRAWN"}),
    "PUBLISHED": frozenset({"EXPIRED", "WITHDRAWN"}),
    "REJECTED": frozenset({"DRAFT", "WITHDRAWN"}),
    "EXPIRED": frozenset(),
    "WITHDRAWN": frozenset(),
}
SERVICE_CASE_TRANSITIONS = {
    "SUBMITTED": frozenset({"ACCEPTED", "CANCELLED"}),
    "ACCEPTED": frozenset({"ASSIGNED", "CANCELLED"}),
    "ASSIGNED": frozenset({"APPOINTED", "IN_PROGRESS", "CANCELLED"}),
    "APPOINTED": frozenset({"IN_PROGRESS", "CANCELLED"}),
    "IN_PROGRESS": frozenset({"RESULT_READY", "DISPUTED", "CANCELLED"}),
    "RESULT_READY": frozenset({"CONFIRMED", "DISPUTED"}),
    "DISPUTED": frozenset({"IN_PROGRESS", "RESULT_READY", "CONFIRMED", "CANCELLED"}),
    "CONFIRMED": frozenset(),
    "CANCELLED": frozenset(),
}
ACTIVITY_TRANSITIONS = {
    "DRAFT": frozenset({"PENDING_APPROVAL", "CANCELLED"}),
    "PENDING_APPROVAL": frozenset({"APPROVED", "REJECTED", "DRAFT", "CANCELLED"}),
    "APPROVED": frozenset({"PUBLISHED", "CANCELLED"}),
    "PUBLISHED": frozenset({"REGISTRATION_CLOSED", "IN_PROGRESS", "CANCELLED"}),
    "REGISTRATION_CLOSED": frozenset({"IN_PROGRESS", "CANCELLED"}),
    "IN_PROGRESS": frozenset({"COMPLETED", "CANCELLED"}),
    "REJECTED": frozenset({"DRAFT", "CANCELLED"}),
    "COMPLETED": frozenset(),
    "CANCELLED": frozenset(),
}


def _validation_error(message: str) -> AppError:
    return AppError(message, code="VALIDATION_ERROR", status_code=400)


def clean_text(value: Any, *, field: str, maximum: int, required: bool = True) -> str:
    text = " ".join(str(value or "").split())
    if required and not text:
        raise _validation_error(f"{field} 必填")
    if len(text) > maximum:
        raise _validation_error(f"{field} 过长")
    lowered = text.lower()
    if "\x00" in text or "<script" in lowered or "javascript:" in lowered:
        raise _validation_error(f"{field} 含不安全内容")
    return text


def normalize_code(value: Any, *, field: str = "code") -> str:
    code = clean_text(value, field=field, maximum=48).upper()
    if not CODE_RE.fullmatch(code):
        raise _validation_error(f"{field} 格式不正确")
    return code


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def idempotency_fingerprint(*, command: str, actor_id: int, payload: Any) -> str:
    return canonical_hash(
        {
            "command": normalize_code(command, field="command"),
            "actor_id": int(actor_id),
            "payload": payload,
        }
    )


def require_version(current: int, expected: Any) -> None:
    try:
        matched = int(current) == int(expected)
    except (TypeError, ValueError):
        matched = False
    if not matched:
        raise AppError(
            "数据已被其他操作更新",
            code="VERSION_CONFLICT",
            status_code=409,
            data={"current_version": int(current)},
        )


def _transition(current: str, target: str, allowed: Mapping[str, frozenset[str]]) -> str:
    normalized_current = str(current).upper()
    normalized_target = str(target).upper()
    if normalized_current not in allowed or normalized_target not in allowed[normalized_current]:
        raise AppError(
            f"不允许从 {normalized_current} 变更为 {normalized_target}",
            code="INVALID_STATE_TRANSITION",
            status_code=409,
            data={"current": normalized_current, "target": normalized_target},
        )
    return normalized_target


def policy_transition(current: str, target: str) -> str:
    return _transition(current, target, POLICY_TRANSITIONS)


def announcement_transition(current: str, target: str) -> str:
    return _transition(current, target, ANNOUNCEMENT_TRANSITIONS)


def service_case_transition(current: str, target: str) -> str:
    return _transition(current, target, SERVICE_CASE_TRANSITIONS)


def activity_transition(current: str, target: str) -> str:
    return _transition(current, target, ACTIVITY_TRANSITIONS)


def normalize_external_url(value: Any, *, allowed_hosts: set[str] | None = None) -> str:
    raw = clean_text(value, field="external_url", maximum=2048)
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise _validation_error("external_url 格式不正确") from exc
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise _validation_error("external_url 仅允许完整 HTTPS 地址")
    if parsed.username or parsed.password or port not in (None, 443):
        raise _validation_error("external_url 不允许凭据或非标准端口")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
        raise _validation_error("external_url 主机不安全")
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        if not SAFE_HOST_RE.fullmatch(hostname):
            raise _validation_error("external_url 主机格式不正确")
    else:
        if not ip.is_global:
            raise _validation_error("external_url 不允许非公网地址")
    normalized_allowed = {host.rstrip(".").lower() for host in (allowed_hosts or set())}
    if normalized_allowed and hostname not in normalized_allowed:
        raise _validation_error("external_url 主机不在允许清单")
    normalized = SplitResult(
        "https",
        hostname,
        parsed.path or "/",
        parsed.query,
        "",
    )
    return urlunsplit(normalized)


def normalize_rule_set(value: Any) -> list[dict[str, Any]]:
    if value in (None, []):
        return []
    if not isinstance(value, list) or len(value) > 32:
        raise _validation_error("applicability_rules 必须是最多 32 条规则的数组")
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, dict) or set(raw) != {"field", "operator", "values"}:
            raise _validation_error(f"applicability_rules[{index}] 字段不正确")
        field = str(raw["field"]).lower()
        operator = str(raw["operator"]).upper()
        values = raw["values"]
        if field not in ALLOWED_RULE_FIELDS or operator not in ALLOWED_RULE_OPERATORS:
            raise _validation_error(f"applicability_rules[{index}] 规则不受支持")
        if not isinstance(values, list) or not values or len(values) > 64:
            raise _validation_error(f"applicability_rules[{index}].values 不正确")
        cleaned_values = sorted(
            {
                clean_text(item, field=f"applicability_rules[{index}].values", maximum=96)
                for item in values
            }
        )
        if operator == "EQ" and len(cleaned_values) != 1:
            raise _validation_error(f"applicability_rules[{index}] EQ 只允许一个值")
        key = (field, operator, canonical_hash(cleaned_values))
        if key in seen:
            raise _validation_error(f"applicability_rules[{index}] 重复")
        seen.add(key)
        normalized.append({"field": field, "operator": operator, "values": cleaned_values})
    return sorted(normalized, key=lambda item: (item["field"], item["operator"], item["values"]))


def evaluate_applicability(
    rules: Sequence[Mapping[str, Any]], projection: Mapping[str, Any]
) -> tuple[bool, list[str], list[str]]:
    matched: list[str] = []
    unmet: list[str] = []
    for rule in normalize_rule_set([dict(item) for item in rules]):
        field = rule["field"]
        expected = set(rule["values"])
        actual_raw = projection.get(field)
        if isinstance(actual_raw, (list, tuple, set, frozenset)):
            actual = {str(item) for item in actual_raw}
        elif actual_raw is None:
            actual = set()
        else:
            actual = {str(actual_raw)}
        operator = rule["operator"]
        satisfied = actual == expected if operator == "EQ" else bool(actual & expected)
        reason = f"{field}:{operator}:{','.join(rule['values'])}"
        (matched if satisfied else unmet).append(reason)
    return not unmet, matched, unmet

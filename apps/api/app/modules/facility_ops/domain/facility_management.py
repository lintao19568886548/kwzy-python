"""Pure business rules for facility devices, inspections and IoT alarms."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.errors import AppError

DEVICE_TYPES = {
    "FIRE",
    "ELEVATOR",
    "TRANSFORMER",
    "ELECTRICAL",
    "HVAC",
    "WATER",
    "SECURITY",
    "CUSTOM",
}
DEVICE_STATUSES = {"ACTIVE", "MAINTENANCE", "RETIRED"}
CRITICALITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
RESULT_TYPES = {"BOOLEAN", "NUMBER", "TEXT", "SELECT"}
TASK_STATUSES = {
    "PENDING",
    "IN_PROGRESS",
    "PASSED",
    "FAILED",
    "MISSED",
    "CANCELLED",
}
ALARM_SEVERITIES = {"INFO", "WARNING", "HIGH", "CRITICAL"}
ALARM_STATUSES = {"OPEN", "ACKNOWLEDGED", "RESOLVED", "CLOSED"}

_DEVICE_TRANSITIONS = {
    "ACTIVE": {"MAINTENANCE", "RETIRED"},
    "MAINTENANCE": {"ACTIVE", "RETIRED"},
    "RETIRED": set(),
}
_TASK_TRANSITIONS = {
    "PENDING": {"IN_PROGRESS", "MISSED", "CANCELLED"},
    "IN_PROGRESS": {"PASSED", "FAILED", "MISSED", "CANCELLED"},
    "PASSED": set(),
    "FAILED": set(),
    "MISSED": set(),
    "CANCELLED": set(),
}
_ALARM_TRANSITIONS = {
    "OPEN": {"ACKNOWLEDGED", "RESOLVED"},
    "ACKNOWLEDGED": {"RESOLVED"},
    "RESOLVED": {"CLOSED", "OPEN"},
    "CLOSED": set(),
}


def _enum(value: Any, *, field: str, allowed: set[str]) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in allowed:
        raise AppError(f"{field} 无效", code="VALIDATION_ERROR", status_code=400)
    return normalized


def device_type(value: Any) -> str:
    return _enum(value, field="device_type", allowed=DEVICE_TYPES)


def criticality(value: Any) -> str:
    return _enum(value, field="criticality", allowed=CRITICALITIES)


def transition_device(current: str, target: str) -> str:
    current = _enum(current, field="device status", allowed=DEVICE_STATUSES)
    target = _enum(target, field="device status", allowed=DEVICE_STATUSES)
    if target not in _DEVICE_TRANSITIONS[current]:
        raise AppError("设备状态迁移无效", code="DEVICE_STATE_INVALID", status_code=409)
    return target


def transition_task(current: str, target: str) -> str:
    current = _enum(current, field="inspection status", allowed=TASK_STATUSES)
    target = _enum(target, field="inspection status", allowed=TASK_STATUSES)
    if target not in _TASK_TRANSITIONS[current]:
        raise AppError("巡检任务状态迁移无效", code="INSPECTION_STATE_INVALID", status_code=409)
    return target


def transition_alarm(current: str, target: str) -> str:
    current = _enum(current, field="alarm status", allowed=ALARM_STATUSES)
    target = _enum(target, field="alarm status", allowed=ALARM_STATUSES)
    if target not in _ALARM_TRANSITIONS[current]:
        raise AppError("告警状态迁移无效", code="ALARM_STATE_INVALID", status_code=409)
    return target


def validate_device_properties(value: Any) -> dict[str, str | int | float | bool | None]:
    if value in (None, {}):
        return {}
    if not isinstance(value, dict) or len(value) > 30:
        raise AppError("properties 必须为最多 30 项对象", code="VALIDATION_ERROR", status_code=400)
    blocked = {"id", "tenant_id", "park_id", "unit_id", "status", "lock_version", "created_at", "updated_at"}
    result: dict[str, str | int | float | bool | None] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip()
        if not key or len(key) > 64 or key.lower() in blocked:
            raise AppError("properties 含非法字段", code="VALIDATION_ERROR", status_code=400)
        if isinstance(raw_value, (dict, list)):
            raise AppError("properties 不允许嵌套对象", code="VALIDATION_ERROR", status_code=400)
        if isinstance(raw_value, str) and len(raw_value) > 255:
            raise AppError("properties 值过长", code="VALIDATION_ERROR", status_code=400)
        if raw_value is not None and not isinstance(raw_value, (str, int, float, bool)):
            raise AppError("properties 值类型无效", code="VALIDATION_ERROR", status_code=400)
        result[key] = raw_value
    return result


def validate_template_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not items or len(items) > 100:
        raise AppError("检查项数量必须为 1-100", code="VALIDATION_ERROR", status_code=400)
    codes: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for position, item in enumerate(items, start=1):
        code = str(item.get("item_code") or "").strip().upper()
        label = str(item.get("label") or "").strip()
        result_type = _enum(item.get("result_type"), field="result_type", allowed=RESULT_TYPES)
        if not code or len(code) > 64 or code in codes or not label or len(label) > 255:
            raise AppError("检查项编码或名称无效", code="VALIDATION_ERROR", status_code=400)
        codes.add(code)
        minimum = item.get("minimum")
        maximum = item.get("maximum")
        options = [str(value).strip() for value in (item.get("options") or [])]
        if result_type == "NUMBER":
            try:
                min_value = Decimal(str(minimum)) if minimum is not None else None
                max_value = Decimal(str(maximum)) if maximum is not None else None
            except InvalidOperation as exc:
                raise AppError("数值检查项边界无效", code="VALIDATION_ERROR", status_code=400) from exc
            if min_value is not None and max_value is not None and min_value > max_value:
                raise AppError("数值检查项最小值大于最大值", code="VALIDATION_ERROR", status_code=400)
        elif minimum is not None or maximum is not None:
            raise AppError("仅 NUMBER 支持数值边界", code="VALIDATION_ERROR", status_code=400)
        if result_type == "SELECT":
            if not options or len(options) > 30 or any(not value or len(value) > 128 for value in options):
                raise AppError("选择项 options 无效", code="VALIDATION_ERROR", status_code=400)
            if len(set(options)) != len(options):
                raise AppError("选择项 options 重复", code="VALIDATION_ERROR", status_code=400)
        elif options:
            raise AppError("仅 SELECT 支持 options", code="VALIDATION_ERROR", status_code=400)
        normalized.append(
            {
                "item_code": code,
                "label": label,
                "position": position,
                "result_type": result_type,
                "required": bool(item.get("required", True)),
                "critical": bool(item.get("critical", False)),
                "minimum": str(minimum) if minimum is not None else None,
                "maximum": str(maximum) if maximum is not None else None,
                "options": options,
            }
        )
    return normalized


def validate_result(item: dict[str, Any], value: Any) -> tuple[str | None, Decimal | None, bool]:
    result_type = str(item["result_type"])
    passed = True
    if result_type == "BOOLEAN":
        if not isinstance(value, bool):
            raise AppError("BOOLEAN 检查项结果类型无效", code="VALIDATION_ERROR", status_code=400)
        return str(value).lower(), None, value
    if result_type == "NUMBER":
        try:
            number = Decimal(str(value))
        except InvalidOperation as exc:
            raise AppError("NUMBER 检查项结果类型无效", code="VALIDATION_ERROR", status_code=400) from exc
        minimum = Decimal(str(item["minimum"])) if item.get("minimum") is not None else None
        maximum = Decimal(str(item["maximum"])) if item.get("maximum") is not None else None
        if minimum is not None and number < minimum:
            passed = False
        if maximum is not None and number > maximum:
            passed = False
        return None, number, passed
    text = str(value or "").strip()
    if len(text) > 1000 or (bool(item.get("required")) and not text):
        raise AppError("检查项文本结果无效", code="VALIDATION_ERROR", status_code=400)
    if result_type == "SELECT" and text not in set(item.get("options") or []):
        raise AppError("SELECT 检查项结果无效", code="VALIDATION_ERROR", status_code=400)
    return text, None, True


def weekly_window(
    *,
    reference: datetime,
    weekday: int,
    local_due_time: str,
    timezone_name: str,
    completion_window_minutes: int,
) -> tuple[datetime, datetime]:
    if weekday < 1 or weekday > 7 or completion_window_minutes < 1 or completion_window_minutes > 10080:
        raise AppError("巡检周期配置无效", code="VALIDATION_ERROR", status_code=400)
    try:
        zone = ZoneInfo(timezone_name)
        hour_text, minute_text = local_due_time.split(":", maxsplit=1)
        due_clock = time(hour=int(hour_text), minute=int(minute_text))
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise AppError("巡检时区或时间无效", code="VALIDATION_ERROR", status_code=400) from exc
    aware_reference = reference.replace(tzinfo=timezone.utc).astimezone(zone)
    week_start = (aware_reference - timedelta(days=aware_reference.isoweekday() - 1)).date()
    due_date = week_start + timedelta(days=weekday - 1)
    local_due = datetime.combine(due_date, due_clock, tzinfo=zone)
    due_utc = local_due.astimezone(timezone.utc).replace(tzinfo=None)
    start_utc = due_utc - timedelta(minutes=completion_window_minutes)
    return start_utc, due_utc


def normalize_severity(value: Any, mapping: dict[str, str] | None = None) -> str:
    raw = str(value or "").strip().upper()
    canonical = str((mapping or {}).get(raw, raw)).upper()
    return _enum(canonical, field="severity", allowed=ALARM_SEVERITIES)


def severity_rank(value: str) -> int:
    return {"INFO": 0, "WARNING": 1, "HIGH": 2, "CRITICAL": 3}[
        _enum(value, field="severity", allowed=ALARM_SEVERITIES)
    ]

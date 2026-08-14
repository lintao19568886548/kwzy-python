"""Pure workforce invariants without ORM or HTTP dependencies."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import date, datetime, time
from typing import Any

from app.core.errors import AppError


def clean_text(value: Any, *, field: str, maximum: int, required: bool = True) -> str | None:
    text = str(value or "").strip()
    if required and not text:
        raise AppError(f"{field} 不能为空", code="VALIDATION_ERROR", status_code=400)
    if not text:
        return None
    if len(text) > maximum:
        raise AppError(f"{field} 超长", code="VALIDATION_ERROR", status_code=400)
    return text


def normalize_code(value: Any, *, field: str, maximum: int = 32) -> str:
    code = str(value or "").strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9_-]{0," + str(maximum - 1) + r"}", code):
        raise AppError(f"{field} 格式无效", code="VALIDATION_ERROR", status_code=400)
    return code


def enum_value(value: Any, *, field: str, allowed: set[str]) -> str:
    result = str(value or "").strip().upper()
    if result not in allowed:
        raise AppError(f"{field} 无效", code="VALIDATION_ERROR", status_code=400)
    return result


def fingerprint(value: Any, *, pepper: str) -> tuple[str | None, str | None]:
    raw = re.sub(r"\s+", "", str(value or ""))
    if not raw:
        return None, None
    digest = hmac.new(pepper.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
    visible = raw[-4:] if len(raw) >= 4 else raw[-1:]
    return f"***{visible}", digest


def payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def employment_dates(start: date, end: date | None) -> None:
    if end is not None and end < start:
        raise AppError("离职日期不能早于入职日期", code="EMPLOYMENT_DATE_INVALID", status_code=400)


def shift_times(start: time, end: time, cross_day: bool, break_minutes: int) -> None:
    if start == end:
        raise AppError("班次起止时间不能相同", code="SHIFT_TIME_INVALID", status_code=400)
    if not cross_day and end <= start:
        raise AppError(
            "非跨日班次结束时间必须晚于开始时间", code="SHIFT_TIME_INVALID", status_code=400
        )
    if break_minutes < 0 or break_minutes > 480:
        raise AppError("休息时长无效", code="SHIFT_BREAK_INVALID", status_code=400)


def cycle_dates(start: date, end: date) -> None:
    if end < start:
        raise AppError(
            "周期结束日期不能早于开始日期", code="PERFORMANCE_CYCLE_DATE_INVALID", status_code=400
        )


def qualification_dates(effective: date, expires: date | None) -> None:
    if expires is not None and expires < effective:
        raise AppError(
            "资质到期日不能早于生效日", code="QUALIFICATION_DATE_INVALID", status_code=400
        )


def naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    from datetime import timezone

    return value.astimezone(timezone.utc).replace(tzinfo=None)

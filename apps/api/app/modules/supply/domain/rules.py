"""Pure supply invariants without ORM or HTTP dependencies."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.errors import AppError

CODE_RE = re.compile(r"^[A-Z][A-Z0-9_-]{1,31}$")
IDENTIFIER_RE = re.compile(r"^[A-Z][A-Z0-9_-]{1,63}$")


def clean_text(value: Any, *, field: str, maximum: int, required: bool = True) -> str:
    text = " ".join(str(value or "").split())
    if required and not text:
        raise AppError(f"{field} 必填", code="VALIDATION_ERROR", status_code=400)
    if len(text) > maximum:
        raise AppError(f"{field} 过长", code="VALIDATION_ERROR", status_code=400)
    return text


def normalize_code(value: Any, *, field: str = "code") -> str:
    code = clean_text(value, field=field, maximum=32).upper()
    if not CODE_RE.fullmatch(code):
        raise AppError(f"{field} 格式不正确", code="VALIDATION_ERROR", status_code=400)
    return code


def normalize_identifier(value: Any, *, field: str) -> str:
    identifier = clean_text(value, field=field, maximum=64).upper()
    if not IDENTIFIER_RE.fullmatch(identifier):
        raise AppError(f"{field} 格式不正确", code="VALIDATION_ERROR", status_code=400)
    return identifier


def positive_decimal(value: Any, *, field: str, scale: str = "0.0001") -> Decimal:
    try:
        result = Decimal(str(value)).quantize(Decimal(scale))
    except (InvalidOperation, ValueError) as exc:
        raise AppError(f"{field} 必须为数字", code="VALIDATION_ERROR", status_code=400) from exc
    if result <= 0:
        raise AppError(f"{field} 必须大于 0", code="VALIDATION_ERROR", status_code=400)
    return result


def nonnegative_decimal(value: Any, *, field: str, scale: str = "0.0001") -> Decimal:
    try:
        result = Decimal(str(value)).quantize(Decimal(scale))
    except (InvalidOperation, ValueError) as exc:
        raise AppError(f"{field} 必须为数字", code="VALIDATION_ERROR", status_code=400) from exc
    if result < 0:
        raise AppError(f"{field} 不得小于 0", code="VALIDATION_ERROR", status_code=400)
    return result


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def credential_projection(raw: Any, *, secret: str) -> tuple[str, str]:
    value = clean_text(raw, field="credential_number", maximum=128)
    visible = value[-4:] if len(value) > 4 else value[-1:]
    masked = f"{'*' * max(4, len(value) - len(visible))}{visible}"
    fingerprint = hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()
    return masked, fingerprint


def naive_utc(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is not None:
        current = current.astimezone(timezone.utc).replace(tzinfo=None)
    return current


def qualification_active(
    *, status: str, effective_on: date, expires_on: date | None, today: date
) -> bool:
    return (
        status == "ACTIVE" and effective_on <= today and (expires_on is None or expires_on >= today)
    )


def require_version(current: int, expected: Any) -> None:
    if int(current) != int(expected):
        raise AppError(
            "数据已被其他操作更新",
            code="VERSION_CONFLICT",
            status_code=409,
            data={"current_version": int(current)},
        )


def approval_state(value: str) -> str:
    return {
        "PENDING": "PENDING_APPROVAL",
        "APPROVED": "APPROVED",
        "REJECTED": "REJECTED",
        "RETURNED": "DRAFT",
        "WITHDRAWN": "CANCELLED",
    }.get(value, "PENDING_APPROVAL")

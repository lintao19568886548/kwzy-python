"""Pure business rules for records, seal custody/use and signature truth."""

from __future__ import annotations

import json
import re
from calendar import monthrange
from datetime import date
from hashlib import sha256
from typing import Any

from app.core.errors import AppError

CONFIDENTIALITIES = {"PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"}
RETENTION_MODES = {"YEARS", "PERMANENT"}
SEAL_KINDS = {"OFFICIAL", "CONTRACT", "FINANCE", "LEGAL_REPRESENTATIVE", "ELECTRONIC", "OTHER"}
ACCESS_MODES = {"VIEW", "BORROW"}
SIGNATURE_ROLES = {"SIGNER", "CC", "APPROVER"}
SIGNATURE_ADAPTERS = {"LOCAL_SANDBOX", "EXTERNAL"}

_CONFIDENTIALITY_RANK = {
    "PUBLIC": 0,
    "INTERNAL": 1,
    "CONFIDENTIAL": 2,
    "RESTRICTED": 3,
}
_SEAL_TRANSITIONS = {
    "ACTIVE": {"TRANSFER_PENDING", "SUSPENDED", "LOST", "RETIRED"},
    "TRANSFER_PENDING": {"ACTIVE", "SUSPENDED", "LOST"},
    "SUSPENDED": {"ACTIVE", "LOST", "RETIRED"},
    "LOST": {"SUSPENDED", "RETIRED"},
    "RETIRED": set(),
}
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


def enum_value(value: Any, *, field: str, allowed: set[str]) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in allowed:
        raise AppError(f"{field} 无效", code="VALIDATION_ERROR", status_code=400)
    return normalized


def bounded_text(
    value: Any,
    *,
    field: str,
    maximum: int,
    required: bool = False,
) -> str:
    normalized = str(value or "").strip()
    if required and not normalized:
        raise AppError(f"{field} 必填", code="VALIDATION_ERROR", status_code=400)
    if len(normalized) > maximum:
        raise AppError(f"{field} 过长", code="VALIDATION_ERROR", status_code=400)
    return normalized


def confidentiality(value: Any) -> str:
    return enum_value(value, field="confidentiality", allowed=CONFIDENTIALITIES)


def assert_category_confidentiality(*, category_max: str, requested: str) -> str:
    normalized = confidentiality(requested)
    if _CONFIDENTIALITY_RANK[normalized] > _CONFIDENTIALITY_RANK[confidentiality(category_max)]:
        raise AppError(
            "档案密级超过分类允许上限",
            code="RECORD_CONFIDENTIALITY_EXCEEDED",
            status_code=409,
        )
    return normalized


def retention_values(
    *, mode: Any, years: Any, filed_on: date
) -> tuple[str, int | None, date | None]:
    normalized = enum_value(mode, field="retention_mode", allowed=RETENTION_MODES)
    if normalized == "PERMANENT":
        if years not in (None, ""):
            raise AppError("永久档案不得设置保管年限", code="VALIDATION_ERROR", status_code=400)
        return normalized, None, None
    try:
        normalized_years = int(years)
    except (TypeError, ValueError) as exc:
        raise AppError("保管年限无效", code="VALIDATION_ERROR", status_code=400) from exc
    if normalized_years < 1 or normalized_years > 100:
        raise AppError("保管年限必须为 1-100 年", code="VALIDATION_ERROR", status_code=400)
    target_year = filed_on.year + normalized_years
    target_day = min(filed_on.day, monthrange(target_year, filed_on.month)[1])
    return normalized, normalized_years, date(target_year, filed_on.month, target_day)


def assert_checksum(value: Any, *, field: str = "checksum_sha256") -> str:
    normalized = str(value or "").strip().lower()
    if not _HEX_64.fullmatch(normalized):
        raise AppError(f"{field} 无效", code="VALIDATION_ERROR", status_code=400)
    return normalized


def seal_kind(value: Any) -> str:
    return enum_value(value, field="seal kind", allowed=SEAL_KINDS)


def transition_seal(current: str, target: str) -> str:
    normalized_current = str(current).upper()
    normalized_target = str(target).upper()
    if normalized_target not in _SEAL_TRANSITIONS.get(normalized_current, set()):
        raise AppError("印章状态迁移无效", code="SEAL_STATE_INVALID", status_code=409)
    return normalized_target


def access_mode(value: Any) -> str:
    return enum_value(value, field="access mode", allowed=ACCESS_MODES)


def signature_adapter(value: Any) -> str:
    return enum_value(value, field="signature adapter", allowed=SIGNATURE_ADAPTERS)


def signature_role(value: Any) -> str:
    return enum_value(value, field="signature role", allowed=SIGNATURE_ROLES)


def canonical_payload_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def manifest_hash(revisions: list[dict[str, Any]]) -> str:
    return canonical_payload_hash(
        {"revisions": sorted(revisions, key=lambda item: int(item["id"]))}
    )


def approval_submission_key(*, biz_type: str, request_key: str) -> str:
    return sha256(f"{biz_type}:{request_key}".encode()).hexdigest()

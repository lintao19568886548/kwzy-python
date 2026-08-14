"""Pure business rules for governed enterprise profiles and evidence."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from app.core.errors import AppError

REGISTRATION_STATUSES = {"ACTIVE", "SUSPENDED", "REVOKED", "CANCELLED", "UNKNOWN"}
EMPLOYEE_SIZE_BANDS = {"MICRO", "SMALL", "MEDIUM", "LARGE", "UNKNOWN"}
RELATIONSHIP_TYPES = {"PARENT_OF", "INVESTED_IN", "COMMON_CONTROL", "BUSINESS_PARTNER"}
SYMMETRIC_RELATIONSHIP_TYPES = {"COMMON_CONTROL", "BUSINESS_PARTNER"}
SOURCE_TYPES = {"MANUAL", "MIGRATION", "EXTERNAL"}
CREDENTIAL_TYPES = {
    "BUSINESS_LICENSE",
    "TAX_REGISTRATION",
    "ORGANIZATION_CODE",
    "INDUSTRY_LICENSE",
    "OTHER",
}
CREDENTIAL_STATUSES = {"ACTIVE", "EXPIRED", "REVOKED", "ARCHIVED"}
LOCAL_CREDENTIAL_REVIEWS = {"LOCALLY_REVIEWED", "REJECTED"}
TAG_TYPES = {"INDUSTRY", "CAPABILITY", "QUALIFICATION", "INTENT", "CUSTOM"}
TAG_VERIFICATION_STATES = {
    "UNVERIFIED",
    "LOCALLY_REVIEWED",
    "EXTERNALLY_VERIFIED",
    "REJECTED",
}
RISK_CATEGORIES = {"LEGAL", "FINANCIAL", "COMPLIANCE", "OPERATIONAL", "REPUTATION", "OTHER"}
RISK_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
RISK_RESOLUTION_TYPES = {"MITIGATED", "DISMISSED", "ACCEPTED"}
_SEVERITY_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
_WHITESPACE = re.compile(r"\s+")
_IDENTIFIER = re.compile(r"[^0-9A-Z]+")


def required_text(value: object, field: str, *, max_length: int) -> str:
    normalized = _WHITESPACE.sub(" ", str(value or "").strip())
    if not normalized:
        raise AppError(f"{field} 必填", code="VALIDATION_ERROR", status_code=400)
    if len(normalized) > max_length:
        raise AppError(f"{field} 超出长度限制", code="VALIDATION_ERROR", status_code=400)
    return normalized


def optional_text(value: object, field: str, *, max_length: int) -> str | None:
    if value is None:
        return None
    normalized = _WHITESPACE.sub(" ", str(value).strip())
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise AppError(f"{field} 超出长度限制", code="VALIDATION_ERROR", status_code=400)
    return normalized


def enum_value(value: object, allowed: set[str], field: str, *, default: str | None = None) -> str:
    normalized = str(value or default or "").strip().upper()
    if normalized not in allowed:
        raise AppError(f"{field} 非法", code="VALIDATION_ERROR", status_code=400)
    return normalized


def capital_value(value: object) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        normalized = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise AppError("注册资本非法", code="VALIDATION_ERROR", status_code=400) from exc
    if normalized < 0 or normalized > Decimal("9999999999999999.99"):
        raise AppError("注册资本超出范围", code="VALIDATION_ERROR", status_code=400)
    return normalized


def currency_value(value: object, *, required: bool) -> str | None:
    if value is None or not str(value).strip():
        if required:
            raise AppError("资本币种必填", code="VALIDATION_ERROR", status_code=400)
        return None
    normalized = str(value).strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", normalized):
        raise AppError("资本币种非法", code="VALIDATION_ERROR", status_code=400)
    return normalized


def website_value(value: object) -> str | None:
    normalized = optional_text(value, "website", max_length=512)
    if normalized is None:
        return None
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise AppError("企业网站地址非法", code="VALIDATION_ERROR", status_code=400)
    return normalized


def canonical_relationship(
    source_party_id: int, target_party_id: int, relationship_type: object
) -> tuple[int, int, str]:
    source = int(source_party_id)
    target = int(target_party_id)
    kind = enum_value(relationship_type, RELATIONSHIP_TYPES, "relationship_type")
    if source <= 0 or target <= 0 or source == target:
        raise AppError("企业关系端点非法", code="ENTERPRISE_RELATIONSHIP_INVALID", status_code=400)
    if kind in SYMMETRIC_RELATIONSHIP_TYPES and source > target:
        source, target = target, source
    return source, target, kind


def ownership_value(value: object, relationship_type: str) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    if relationship_type not in {"PARENT_OF", "INVESTED_IN"}:
        raise AppError(
            "该关系类型不支持持股比例",
            code="ENTERPRISE_RELATIONSHIP_OWNERSHIP_INVALID",
            status_code=400,
        )
    try:
        normalized = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise AppError("持股比例非法", code="VALIDATION_ERROR", status_code=400) from exc
    if normalized < 0 or normalized > 100:
        raise AppError("持股比例须在 0 到 100 之间", code="VALIDATION_ERROR", status_code=400)
    return normalized


def reduce_organization_identifier(value: object) -> tuple[str | None, str | None]:
    if value is None or not str(value).strip():
        return None, None
    normalized = _IDENTIFIER.sub("", str(value).strip().upper())
    if len(normalized) < 4 or len(normalized) > 64:
        raise AppError("组织证照标识非法", code="VALIDATION_ERROR", status_code=400)
    fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    visible = normalized[-4:]
    return fingerprint, f"{'*' * min(12, max(4, len(normalized) - 4))}{visible}"


def effective_credential_status(status: str, expires_on: date | None, *, today: date) -> str:
    if status == "ACTIVE" and expires_on is not None and expires_on < today:
        return "EXPIRED"
    return status


def normalize_tag_name(value: object) -> tuple[str, str]:
    name = required_text(value, "tag name", max_length=128)
    return name, name.casefold()


def confidence_value(value: object) -> Decimal:
    try:
        normalized = Decimal(str(value if value is not None else "1")).quantize(Decimal("0.0001"))
    except (InvalidOperation, ValueError) as exc:
        raise AppError("标签置信度非法", code="VALIDATION_ERROR", status_code=400) from exc
    if normalized < 0 or normalized > 1:
        raise AppError("标签置信度须在 0 到 1 之间", code="VALIDATION_ERROR", status_code=400)
    return normalized


@dataclass(frozen=True)
class CompletenessResult:
    score: int
    missing: tuple[str, ...]


def enterprise_completeness(dimensions: Mapping[str, bool]) -> CompletenessResult:
    weights = (
        ("CREDIT_CODE", 15),
        ("LEGAL_REPRESENTATIVE", 10),
        ("ESTABLISHED_ON", 10),
        ("REGISTERED_CAPITAL", 10),
        ("REGISTRATION_STATUS", 5),
        ("INDUSTRY", 10),
        ("BUSINESS_SCOPE", 10),
        ("REGISTERED_ADDRESS", 10),
        ("PRIMARY_CONTACT", 10),
        ("BUSINESS_LICENSE", 10),
    )
    score = sum(weight for code, weight in weights if bool(dimensions.get(code)))
    missing = tuple(code for code, _ in weights if not bool(dimensions.get(code)))
    return CompletenessResult(score=score, missing=missing)


def enterprise_risk_summary(unresolved: Iterable[tuple[str, str]]) -> dict[str, object]:
    severity_counts = {severity: 0 for severity in ("LOW", "MEDIUM", "HIGH", "CRITICAL")}
    category_counts: dict[str, int] = {}
    level = "NONE"
    for severity, category in unresolved:
        normalized_severity = enum_value(severity, RISK_SEVERITIES, "severity")
        normalized_category = enum_value(category, RISK_CATEGORIES, "category")
        severity_counts[normalized_severity] += 1
        category_counts[normalized_category] = category_counts.get(normalized_category, 0) + 1
        if level == "NONE" or _SEVERITY_ORDER[normalized_severity] > _SEVERITY_ORDER[level]:
            level = normalized_severity
    return {
        "overall_level": level,
        "unresolved_count": sum(severity_counts.values()),
        "severity_counts": severity_counts,
        "category_counts": category_counts,
        "label": "本地未解决风险信号汇总，不是外部信用评分",
    }

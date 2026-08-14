"""Canonical Lease snapshot serialization and optimistic command helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from app.modules.lease.domain.errors import LeaseDomainError

CURRENT_SNAPSHOT_SCHEMA_VERSION = 1


def _decimal_text(value: Decimal) -> str:
    if not value.is_finite():
        raise LeaseDomainError("LEASE_SNAPSHOT_INVALID", "snapshot decimal must be finite")
    normalized = value.normalize()
    text = format(normalized, "f")
    return "0" if text in {"-0", "-0.0"} else text


def canonical_value(value: Any) -> Any:
    """Convert supported values into a stable JSON-compatible representation."""

    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        return {str(key): canonical_value(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [canonical_value(item) for item in value]
    if isinstance(value, Decimal):
        return _decimal_text(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return canonical_value(value.value)
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return _decimal_text(Decimal(str(value)))
    raise LeaseDomainError(
        "LEASE_SNAPSHOT_INVALID",
        f"unsupported snapshot value: {type(value).__name__}",
    )


def validate_schema_version(schema_version: int) -> int:
    """Only explicitly supported snapshot schema versions may be persisted."""

    try:
        version = int(schema_version)
    except (TypeError, ValueError) as exc:
        raise LeaseDomainError(
            "LEASE_SNAPSHOT_SCHEMA_UNSUPPORTED", "snapshot schema version is invalid"
        ) from exc
    if version != CURRENT_SNAPSHOT_SCHEMA_VERSION:
        raise LeaseDomainError(
            "LEASE_SNAPSHOT_SCHEMA_UNSUPPORTED",
            f"unsupported snapshot schema version: {version}",
        )
    return version


def canonical_snapshot(snapshot: dict[str, Any], *, schema_version: int = 1) -> dict[str, Any]:
    """Return the normalized complete snapshot with an explicit schema version."""

    version = validate_schema_version(schema_version)
    if not isinstance(snapshot, dict):
        raise LeaseDomainError("LEASE_SNAPSHOT_INVALID", "snapshot must be an object")
    normalized = canonical_value(snapshot)
    normalized["schema_version"] = version
    return {key: normalized[key] for key in sorted(normalized)}


def canonical_json(snapshot: dict[str, Any], *, schema_version: int = 1) -> str:
    normalized = canonical_snapshot(snapshot, schema_version=schema_version)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def snapshot_checksum(snapshot: dict[str, Any], *, schema_version: int = 1) -> str:
    payload = canonical_json(snapshot, schema_version=schema_version).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def assert_expected_version(actual: int, expected: int | None) -> int:
    """Fail with stable semantics before applying a mutable command."""

    if expected is None:
        raise LeaseDomainError("EXPECTED_VERSION_REQUIRED", "expected_version is required")
    if int(actual) != int(expected):
        raise LeaseDomainError(
            "LEASE_VERSION_CONFLICT",
            f"expected version {expected}, current version is {actual}",
        )
    return int(actual)


def scoped_idempotency_key(tenant_id: int, command: str, key: str | None) -> str:
    """Normalize retry keys so they cannot collide across tenants or commands."""

    normalized_command = (command or "").strip().upper()
    normalized_key = (key or "").strip()
    if not normalized_command or not normalized_key:
        raise LeaseDomainError(
            "IDEMPOTENCY_KEY_REQUIRED", "command and idempotency key are required"
        )
    if len(normalized_key) > 160:
        raise LeaseDomainError("IDEMPOTENCY_KEY_INVALID", "idempotency key is too long")
    return f"lease:t{int(tenant_id)}:{normalized_command}:{normalized_key}"

"""关键业务写操作的事务内、脱敏且可验证审计记录器。"""

from __future__ import annotations

import json
from datetime import date, datetime
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.audit import AuditChainHead, AuditLog
from app.shared.tenant_context import TenantContext

AUDIT_INTEGRITY_VERSION = 1
AUDIT_DETAIL_MAX_BYTES = 8192
_BLOCKED_KEYS = {
    "password",
    "password_hash",
    "passwd",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "cookie",
    "secret",
    "client_secret",
    "api_key",
    "sms_code",
    "verification_code",
}
_PHONE_KEYS = {"phone", "mobile", "telephone", "contact_phone"}
_EMAIL_KEYS = {"email", "contact_email"}


def _mask_phone(value: Any) -> str:
    raw = str(value or "")
    if len(raw) <= 4:
        return "*" * len(raw)
    if len(raw) <= 7:
        return f"{raw[:1]}***{raw[-2:]}"
    return f"{raw[:3]}****{raw[-4:]}"


def _mask_email(value: Any) -> str:
    raw = str(value or "")
    local, separator, domain = raw.partition("@")
    if not separator:
        return "***"
    return f"{local[:1]}***@{domain}"


def sanitize_audit_detail(value: Any, *, _depth: int = 0) -> Any:
    """Return a bounded JSON-compatible value with secrets removed and PII masked."""

    if _depth >= 6:
        return "[DEPTH_LIMIT]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, str):
        return value[:512]
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for raw_key in sorted(value, key=lambda item: str(item))[:100]:
            key = str(raw_key)[:128]
            normalized = key.lower().replace("-", "_")
            item = value[raw_key]
            if normalized in _BLOCKED_KEYS or any(
                normalized.endswith(f"_{suffix}") for suffix in _BLOCKED_KEYS
            ):
                sanitized[key] = "[REDACTED]"
            elif normalized in _PHONE_KEYS or normalized.endswith("_phone"):
                sanitized[key] = _mask_phone(item)
            elif normalized in _EMAIL_KEYS or normalized.endswith("_email"):
                sanitized[key] = _mask_email(item)
            else:
                sanitized[key] = sanitize_audit_detail(item, _depth=_depth + 1)
        if len(value) > 100:
            sanitized["_omitted_keys"] = len(value) - 100
        return sanitized
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        result = [sanitize_audit_detail(item, _depth=_depth + 1) for item in items[:100]]
        if len(items) > 100:
            result.append({"_omitted_items": len(items) - 100})
        return result
    return str(value)[:512]


def bounded_audit_detail(detail: dict[str, Any] | None) -> dict[str, Any] | None:
    if detail is None:
        return None
    sanitized = sanitize_audit_detail(detail)
    encoded = json.dumps(
        sanitized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(encoded) <= AUDIT_DETAIL_MAX_BYTES:
        return sanitized
    return {
        "_truncated": True,
        "canonical_bytes": len(encoded),
        "canonical_sha256": sha256(encoded).hexdigest(),
    }


def canonical_audit_payload(
    *,
    tenant_id: int,
    sequence_no: int,
    previous_hash: str,
    user_id: int | None,
    request_id: str,
    action: str,
    resource_type: str,
    resource_id: str | None,
    park_id: int | None,
    detail_json: dict[str, Any] | None,
    client_ip: str | None,
    created_at: datetime,
    integrity_version: int = AUDIT_INTEGRITY_VERSION,
) -> bytes:
    payload = {
        "action": action,
        "client_ip": client_ip,
        "created_at": created_at.isoformat(timespec="microseconds"),
        "detail_json": detail_json,
        "integrity_version": integrity_version,
        "park_id": park_id,
        "previous_hash": previous_hash,
        "request_id": request_id,
        "resource_id": resource_id,
        "resource_type": resource_type,
        "sequence_no": sequence_no,
        "tenant_id": tenant_id,
        "user_id": user_id,
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def calculate_audit_hash(**payload: Any) -> str:
    return sha256(canonical_audit_payload(**payload)).hexdigest()


class AuditRecorder:
    """使用业务 Session 写入审计，随业务事务一起提交或回滚。"""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def record(
        self,
        *,
        action: str,
        resource_type: str,
        resource_id: int | str | None,
        park_id: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Append and flush a sanitized, tenant-sequenced audit record."""

        dialect = self.session.bind.dialect.name if self.session.bind is not None else ""
        insert_values = {
            "tenant_id": self.ctx.tenant_id,
            "sequence_no": 0,
            "last_hash": "GENESIS",
            "updated_at": utc_now(),
        }
        if dialect == "postgresql":
            stmt = pg_insert(AuditChainHead).values(**insert_values)
            self.session.execute(stmt.on_conflict_do_nothing(index_elements=["tenant_id"]))
        elif dialect == "sqlite":
            stmt = sqlite_insert(AuditChainHead).values(**insert_values)
            self.session.execute(stmt.on_conflict_do_nothing(index_elements=["tenant_id"]))
        else:
            existing = self.session.get(AuditChainHead, self.ctx.tenant_id)
            if existing is None:
                self.session.add(AuditChainHead(**insert_values))
                self.session.flush()

        head_query = select(AuditChainHead).where(AuditChainHead.tenant_id == self.ctx.tenant_id)
        if dialect == "postgresql":
            head_query = head_query.with_for_update()
        head = self.session.scalars(head_query).one()
        sequence_no = int(head.sequence_no) + 1
        previous_hash = str(head.last_hash)
        created_at = utc_now()
        safe_detail = bounded_audit_detail(detail)
        payload = {
            "tenant_id": self.ctx.tenant_id,
            "sequence_no": sequence_no,
            "previous_hash": previous_hash,
            "user_id": self.ctx.user_id or None,
            "request_id": self.ctx.request_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id is not None else None,
            "park_id": park_id,
            "detail_json": safe_detail,
            "client_ip": self.ctx.client_ip,
            "created_at": created_at,
            "integrity_version": AUDIT_INTEGRITY_VERSION,
        }
        record_hash = calculate_audit_hash(**payload)
        audit = AuditLog(
            **payload,
            record_hash=record_hash,
        )
        self.session.add(audit)
        head.sequence_no = sequence_no
        head.last_hash = record_hash
        head.updated_at = created_at
        self.session.add(head)
        self.session.flush()
        return audit

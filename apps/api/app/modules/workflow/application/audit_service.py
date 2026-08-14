"""Scoped audit search, verification and controlled CSV export."""

from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.modules.workflow.infrastructure.audit_repository import AuditRepository
from app.shared.tenant_context import TenantContext


class AuditService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.repo = AuditRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def _require(self, permission: str) -> None:
        if not self.ctx.has_permission(permission):
            raise AppError("无审计访问权限", code="PERMISSION_DENIED", status_code=403)

    def search(self, *, filters: dict[str, Any], page: int, page_size: int) -> dict[str, Any]:
        self._require("audit.read")
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        integrity_state = str(filters.get("integrity_state") or "").upper()
        states, _ = self.repo.verify_chain()
        if integrity_state in {"VERIFIED", "FAILED"}:
            rows = self.repo.search_bounded(filters=filters, limit=5000)
            rows = [row for row in rows if states.get(int(row.id)) == integrity_state]
            total = len(rows)
            rows = rows[(page - 1) * page_size : page * page_size]
        else:
            rows, total = self.repo.search(
                filters=filters,
                offset=(page - 1) * page_size,
                limit=page_size,
            )
        return {
            "items": [self._row_dict(row, states) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get(self, audit_id: int) -> dict[str, Any]:
        self._require("audit.read")
        row = self.repo.get(audit_id)
        if row is None:
            raise AppError("审计记录不存在", code="AUDIT_NOT_FOUND", status_code=404)
        states, _ = self.repo.verify_chain()
        return self._row_dict(row, states)

    def verify(self) -> dict[str, Any]:
        self._require("audit.read")
        _, summary = self.repo.verify_chain()
        return summary

    def export_csv(self, *, filters: dict[str, Any], limit: int) -> str:
        self._require("audit.export")
        safe_limit = min(max(limit, 1), 2000)
        rows = self.repo.search_bounded(filters=filters, limit=safe_limit)
        states, _ = self.repo.verify_chain()
        integrity_state = str(filters.get("integrity_state") or "").upper()
        if integrity_state in {"VERIFIED", "FAILED", "LEGACY_UNVERIFIED"}:
            rows = [row for row in rows if self._integrity_state(row, states) == integrity_state]
        stream = StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\r\n")
        writer.writerow(
            [
                "id",
                "created_at",
                "user_id",
                "action",
                "resource_type",
                "resource_id",
                "park_id",
                "request_id",
                "integrity_state",
                "detail_json",
            ]
        )
        for row in rows:
            values = [
                row.id,
                row.created_at.isoformat(),
                row.user_id,
                row.action,
                row.resource_type,
                row.resource_id,
                row.park_id,
                row.request_id,
                self._integrity_state(row, states),
                json.dumps(row.detail_json, ensure_ascii=False, sort_keys=True),
            ]
            writer.writerow([self._formula_safe(value) for value in values])
        self.audit.record(
            action="export",
            resource_type="AUDIT_LOG",
            resource_id=None,
            detail={"filters": self._safe_filter_summary(filters), "row_count": len(rows)},
        )
        self.session.commit()
        return "\ufeff" + stream.getvalue()

    @staticmethod
    def _formula_safe(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        stripped = value.lstrip()
        if stripped.startswith(("=", "+", "-", "@", "\t", "\r")):
            return "'" + value
        return value

    @staticmethod
    def _safe_filter_summary(filters: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "user_id",
            "action",
            "resource_type",
            "resource_id",
            "park_id",
            "request_id",
            "integrity_state",
            "created_from",
            "created_to",
        }
        return {
            key: value for key, value in filters.items() if key in allowed and value is not None
        }

    @staticmethod
    def _integrity_state(row, states: dict[int, str]) -> str:
        if row.sequence_no is None:
            return "LEGACY_UNVERIFIED"
        return states.get(int(row.id), "FAILED")

    def _row_dict(self, row, states: dict[int, str]) -> dict[str, Any]:
        return {
            "id": int(row.id),
            "user_id": row.user_id,
            "request_id": row.request_id,
            "action": row.action,
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "park_id": row.park_id,
            "detail": row.detail_json,
            "client_ip": row.client_ip,
            "created_at": row.created_at.isoformat(),
            "sequence_no": row.sequence_no,
            "previous_hash": row.previous_hash,
            "record_hash": row.record_hash,
            "integrity_version": row.integrity_version,
            "integrity_state": self._integrity_state(row, states),
        }

"""Tenant/park-scoped audit ledger search and independent integrity verification."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.infrastructure.database.audit import calculate_audit_hash
from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.audit import AuditChainHead, AuditLog
from app.shared.tenant_context import ParkScopeMode, TenantContext


class AuditRepository:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def _scope(self, stmt):
        stmt = stmt.where(AuditLog.tenant_id == self.ctx.tenant_id)
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(
                or_(AuditLog.park_id.is_(None), AuditLog.park_id.in_(list(self.ctx.park_ids)))
            )
        return stmt.where(AuditLog.park_id.is_(None))

    def _filters(self, stmt, filters: dict[str, Any]):
        if filters.get("user_id") is not None:
            stmt = stmt.where(AuditLog.user_id == int(filters["user_id"]))
        if filters.get("action"):
            stmt = stmt.where(AuditLog.action == str(filters["action"]))
        if filters.get("resource_type"):
            stmt = stmt.where(AuditLog.resource_type == str(filters["resource_type"]))
        if filters.get("resource_id"):
            stmt = stmt.where(AuditLog.resource_id == str(filters["resource_id"]))
        if filters.get("park_id") is not None:
            stmt = stmt.where(AuditLog.park_id == int(filters["park_id"]))
        if filters.get("request_id"):
            stmt = stmt.where(AuditLog.request_id == str(filters["request_id"]))
        if filters.get("created_from"):
            stmt = stmt.where(AuditLog.created_at >= filters["created_from"])
        if filters.get("created_to"):
            stmt = stmt.where(AuditLog.created_at <= filters["created_to"])
        integrity_state = str(filters.get("integrity_state") or "").upper()
        if integrity_state == "LEGACY_UNVERIFIED":
            stmt = stmt.where(AuditLog.sequence_no.is_(None))
        elif integrity_state in {"CHAINED", "VERIFIED", "FAILED"}:
            stmt = stmt.where(AuditLog.sequence_no.is_not(None))
        return stmt

    def search(
        self,
        *,
        filters: dict[str, Any],
        offset: int,
        limit: int,
    ) -> tuple[list[AuditLog], int]:
        stmt = self._filters(self._scope(select(AuditLog)), filters)
        count_stmt = self._filters(self._scope(select(AuditLog.id)), filters)
        rows = list(
            self.session.scalars(
                stmt.order_by(AuditLog.id.desc()).offset(offset).limit(limit)
            ).all()
        )
        total = int(
            self.session.scalar(select(func.count()).select_from(count_stmt.subquery())) or 0
        )
        return rows, total

    def search_bounded(self, *, filters: dict[str, Any], limit: int) -> list[AuditLog]:
        stmt = self._filters(self._scope(select(AuditLog)), filters)
        return list(self.session.scalars(stmt.order_by(AuditLog.id.desc()).limit(limit)).all())

    def get(self, audit_id: int) -> AuditLog | None:
        return self.session.scalars(
            self._scope(select(AuditLog).where(AuditLog.id == audit_id))
        ).first()

    def verify_chain(self) -> tuple[dict[int, str], dict[str, Any]]:
        rows = list(
            self.session.scalars(
                select(AuditLog)
                .where(
                    AuditLog.tenant_id == self.ctx.tenant_id,
                    AuditLog.sequence_no.is_not(None),
                )
                .order_by(AuditLog.sequence_no, AuditLog.id)
            ).all()
        )
        states: dict[int, str] = {}
        expected_sequence = 1
        expected_previous = "GENESIS"
        chain_failed = False
        first_failed_sequence: int | None = None
        for row in rows:
            try:
                recalculated = calculate_audit_hash(
                    tenant_id=int(row.tenant_id),
                    sequence_no=int(row.sequence_no),
                    previous_hash=str(row.previous_hash),
                    user_id=int(row.user_id) if row.user_id is not None else None,
                    request_id=row.request_id,
                    action=row.action,
                    resource_type=row.resource_type,
                    resource_id=row.resource_id,
                    park_id=int(row.park_id) if row.park_id is not None else None,
                    detail_json=row.detail_json,
                    client_ip=row.client_ip,
                    created_at=row.created_at,
                    integrity_version=int(row.integrity_version or 0),
                )
            except (TypeError, ValueError):
                recalculated = ""
            valid = (
                not chain_failed
                and int(row.sequence_no) == expected_sequence
                and str(row.previous_hash) == expected_previous
                and str(row.record_hash) == recalculated
                and int(row.integrity_version or 0) == 1
            )
            if not valid:
                chain_failed = True
                first_failed_sequence = first_failed_sequence or int(row.sequence_no)
                states[int(row.id)] = "FAILED"
            else:
                states[int(row.id)] = "VERIFIED"
            expected_sequence = int(row.sequence_no) + 1
            expected_previous = str(row.record_hash)

        head = self.session.get(AuditChainHead, self.ctx.tenant_id)
        head_matches = bool(
            (not rows and (head is None or int(head.sequence_no) == 0))
            or (
                rows
                and head is not None
                and int(head.sequence_no) == int(rows[-1].sequence_no)
                and str(head.last_hash) == str(rows[-1].record_hash)
            )
        )
        if not head_matches and rows:
            states[int(rows[-1].id)] = "FAILED"
            first_failed_sequence = first_failed_sequence or int(rows[-1].sequence_no)
        legacy_count = int(
            self.session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.tenant_id == self.ctx.tenant_id,
                    AuditLog.sequence_no.is_(None),
                )
            )
            or 0
        )
        failed_count = sum(1 for state in states.values() if state == "FAILED")
        return states, {
            "state": "FAILED" if failed_count or not head_matches else "VERIFIED",
            "chained_count": len(rows),
            "verified_count": len(rows) - failed_count,
            "failed_count": failed_count,
            "legacy_count": legacy_count,
            "first_failed_sequence": first_failed_sequence,
            "head_matches": head_matches,
            "verified_at": utc_now().isoformat(),
        }

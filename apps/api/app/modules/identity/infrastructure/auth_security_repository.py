"""Shared-store authentication rate-limit and security-event persistence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.identity import AuthSecurityEvent


class AuthSecurityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def count_recent_subject_failures(
        self,
        *,
        subject_digest: str,
        since: datetime,
    ) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(AuthSecurityEvent)
                .where(
                    AuthSecurityEvent.event_type == "LOGIN_FAILURE",
                    AuthSecurityEvent.subject_digest == subject_digest,
                    AuthSecurityEvent.created_at >= since,
                )
            )
            or 0
        )

    def count_recent_client_failures(
        self,
        *,
        client_digest: str,
        since: datetime,
    ) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(AuthSecurityEvent)
                .where(
                    AuthSecurityEvent.event_type == "LOGIN_FAILURE",
                    AuthSecurityEvent.client_digest == client_digest,
                    AuthSecurityEvent.created_at >= since,
                )
            )
            or 0
        )

    def record(
        self,
        *,
        event_type: str,
        subject_digest: str,
        client_digest: str,
        reason_code: str,
        tenant_id: int | None = None,
    ) -> None:
        self.session.add(
            AuthSecurityEvent(
                tenant_id=tenant_id,
                event_type=event_type,
                subject_digest=subject_digest,
                client_digest=client_digest,
                reason_code=reason_code,
            )
        )

    def commit(self) -> None:
        self.session.commit()

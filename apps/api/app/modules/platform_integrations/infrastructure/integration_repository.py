"""Persistence boundary for external integration delivery records."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.database.models.identity import User
from app.infrastructure.database.models.integration_outbox import IntegrationOutbox


class IntegrationRepository:
    def __init__(self, session: Session, tenant_id: int) -> None:
        self.session = session
        self.tenant_id = tenant_id

    def get_by_key(self, *, channel: str, idempotency_key: str) -> IntegrationOutbox | None:
        return self.session.scalar(
            select(IntegrationOutbox).where(
                IntegrationOutbox.tenant_id == self.tenant_id,
                IntegrationOutbox.channel == channel,
                IntegrationOutbox.idempotency_key == idempotency_key,
            )
        )

    def claim(
        self,
        *,
        channel: str,
        provider: str,
        idempotency_key: str,
        payload_json: str,
        stale_after_seconds: int,
    ) -> tuple[IntegrationOutbox, str]:
        """Atomically reserve a delivery key before any external side effect."""

        existing = self.get_by_key(channel=channel, idempotency_key=idempotency_key)
        if existing is not None:
            if existing.status == "SUCCESS":
                return existing, "SUCCESS"
            reference = existing.updated_at or existing.created_at
            if existing.status == "PENDING" and reference is not None:
                if reference > datetime.utcnow() - timedelta(seconds=stale_after_seconds):
                    return existing, "IN_PROGRESS"
            existing.status = "PENDING"
            existing.provider = provider
            existing.payload_json = payload_json
            existing.last_error = None
            self.session.add(existing)
            self.session.commit()
            self.session.refresh(existing)
            return existing, "CLAIMED"

        row = IntegrationOutbox(
            tenant_id=self.tenant_id,
            channel=channel,
            provider=provider,
            idempotency_key=idempotency_key,
            status="PENDING",
            attempts=0,
            payload_json=payload_json,
        )
        self.session.add(row)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            winner = self.get_by_key(channel=channel, idempotency_key=idempotency_key)
            if winner is None:
                raise
            return winner, "SUCCESS" if winner.status == "SUCCESS" else "IN_PROGRESS"
        self.session.refresh(row)
        return row, "CLAIMED"

    def complete(
        self,
        row: IntegrationOutbox,
        *,
        ok: bool,
        attempts: int,
        external_id: str | None,
        error: str | None,
    ) -> None:
        row.status = "SUCCESS" if ok else "FAILED"
        row.attempts = int(row.attempts or 0) + max(1, int(attempts or 1))
        row.external_id = external_id
        row.last_error = (error or "")[:512] or None
        self.session.add(row)
        self.session.commit()

    def list_recent(self, *, limit: int = 100) -> list[IntegrationOutbox]:
        return list(
            self.session.scalars(
                select(IntegrationOutbox)
                .where(IntegrationOutbox.tenant_id == self.tenant_id)
                .order_by(IntegrationOutbox.id.desc())
                .limit(limit)
            ).all()
        )

    def active_user_exists(self, user_id: int) -> bool:
        return (
            self.session.scalar(
                select(User.id).where(
                    User.id == user_id,
                    User.tenant_id == self.tenant_id,
                    User.status == "ACTIVE",
                )
            )
            is not None
        )

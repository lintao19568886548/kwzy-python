"""Persistence for one-time verification codes and page-access proofs."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.infrastructure.database.models.identity import (
    PageAccessProof,
    User,
    VerificationCode,
)
from app.infrastructure.database.models.integration_outbox import IntegrationOutbox


class VerificationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_active_user(self, tenant_id: int, user_id: int) -> User | None:
        return self.session.scalar(
            select(User).where(
                User.id == user_id,
                User.tenant_id == tenant_id,
                User.status == "ACTIVE",
            )
        )

    def count_recent_sends(
        self,
        *,
        tenant_id: int,
        user_id: int,
        purpose: str,
        since: datetime,
    ) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(VerificationCode)
                .where(
                    VerificationCode.tenant_id == tenant_id,
                    VerificationCode.user_id == user_id,
                    VerificationCode.purpose == purpose,
                    VerificationCode.created_at >= since,
                )
            )
            or 0
        )

    def consume_previous_codes(
        self,
        *,
        tenant_id: int,
        user_id: int,
        purpose: str,
        when: datetime,
    ) -> None:
        self.session.execute(
            update(VerificationCode)
            .where(
                VerificationCode.tenant_id == tenant_id,
                VerificationCode.user_id == user_id,
                VerificationCode.purpose == purpose,
                VerificationCode.consumed_at.is_(None),
            )
            .values(consumed_at=when)
        )

    def create_code(
        self,
        *,
        tenant_id: int,
        user_id: int,
        purpose: str,
        recipient_digest: str,
        code_hash: str,
        expires_at: datetime,
        max_attempts: int,
    ) -> VerificationCode:
        row = VerificationCode(
            tenant_id=tenant_id,
            user_id=user_id,
            purpose=purpose,
            recipient_digest=recipient_digest,
            code_hash=code_hash,
            expires_at=expires_at,
            max_attempts=max_attempts,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def latest_code_for_update(
        self,
        *,
        tenant_id: int,
        user_id: int,
        purpose: str,
    ) -> VerificationCode | None:
        return self.session.scalar(
            select(VerificationCode)
            .where(
                VerificationCode.tenant_id == tenant_id,
                VerificationCode.user_id == user_id,
                VerificationCode.purpose == purpose,
                VerificationCode.consumed_at.is_(None),
            )
            .order_by(VerificationCode.id.desc())
            .limit(1)
            .with_for_update()
        )

    def create_proof(
        self,
        *,
        tenant_id: int,
        user_id: int,
        purpose: str,
        proof_hash: str,
        expires_at: datetime,
    ) -> None:
        self.session.add(
            PageAccessProof(
                tenant_id=tenant_id,
                user_id=user_id,
                purpose=purpose,
                proof_hash=proof_hash,
                expires_at=expires_at,
            )
        )

    def add_sms_outbox(
        self,
        *,
        tenant_id: int,
        provider: str,
        idempotency_key: str,
        status: str,
        attempts: int,
        payload_json: str,
        last_error: str | None,
        external_id: str | None,
    ) -> None:
        self.session.add(
            IntegrationOutbox(
                tenant_id=tenant_id,
                channel="sms",
                provider=provider,
                idempotency_key=idempotency_key,
                status=status,
                attempts=attempts,
                payload_json=payload_json,
                last_error=last_error,
                external_id=external_id,
            )
        )

    def proof_for_update(self, proof_hash: str) -> PageAccessProof | None:
        return self.session.scalar(
            select(PageAccessProof)
            .where(PageAccessProof.proof_hash == proof_hash)
            .with_for_update()
        )

    def commit(self) -> None:
        self.session.commit()

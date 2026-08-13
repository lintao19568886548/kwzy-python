"""One-time SMS verification and page-access proof use cases."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.infrastructure.platform.providers import SmsMessage, get_sms_provider
from app.modules.identity.infrastructure.verification_repository import (
    VerificationRepository,
)

UTC = timezone.utc
_PURPOSE_RE = re.compile(r"^[a-z][a-z0-9_.:-]{2,63}$")


def _digest(kind: str, value: str) -> str:
    key = get_settings().jwt_secret.encode("utf-8")
    return hmac.new(
        key,
        f"{kind}:{value}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class PageAccessService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = VerificationRepository(session)

    def send_code(self, *, tenant_id: int, user_id: int, purpose: str) -> dict:
        purpose = self._valid_purpose(purpose)
        user = self.repo.get_active_user(tenant_id, user_id)
        if user is None:
            raise AppError("用户不存在", code="AUTH_USER_NOT_FOUND", status_code=404)
        phone = (user.phone or "").strip()
        if len(phone) < 5:
            raise AppError(
                "当前用户未配置可用手机号",
                code="AUTH_PHONE_REQUIRED",
                status_code=400,
            )

        settings = get_settings()
        now = datetime.now(UTC).replace(tzinfo=None)
        recent = self.repo.count_recent_sends(
            tenant_id=tenant_id,
            user_id=user_id,
            purpose=purpose,
            since=now - timedelta(seconds=settings.verification_code_send_window_seconds),
        )
        if recent >= settings.verification_code_max_sends_per_window:
            raise AppError(
                "验证码发送过于频繁",
                code="AUTH_CODE_RATE_LIMITED",
                status_code=429,
            )

        self.repo.consume_previous_codes(
            tenant_id=tenant_id,
            user_id=user_id,
            purpose=purpose,
            when=now,
        )
        raw_code = f"{secrets.randbelow(1_000_000):06d}"
        code = self.repo.create_code(
            tenant_id=tenant_id,
            user_id=user_id,
            purpose=purpose,
            recipient_digest=_digest("verification-recipient", phone),
            code_hash=_digest(
                "verification-code",
                f"{tenant_id}:{user_id}:{purpose}:{raw_code}",
            ),
            expires_at=now + timedelta(seconds=settings.verification_code_ttl_seconds),
            max_attempts=settings.verification_code_max_attempts,
        )

        provider = get_sms_provider(
            app_env=settings.app_env,
            provider=settings.sms_provider,
            api_key=settings.sms_api_key,
            endpoint=settings.sms_endpoint,
            timeout_seconds=settings.sms_timeout_seconds,
            max_retries=settings.sms_max_retries,
        )
        idempotency_key = f"page-access-{tenant_id}-{user_id}-{purpose}-{code.id}"
        result = provider.send(
            SmsMessage(
                to=phone,
                template_code="PAGE_ACCESS_CODE",
                params={
                    "code": raw_code,
                    "purpose": purpose,
                    "expires_in": settings.verification_code_ttl_seconds,
                },
                idempotency_key=idempotency_key,
            )
        )
        self.repo.add_sms_outbox(
            tenant_id=tenant_id,
            provider=result.provider,
            idempotency_key=idempotency_key,
            status="SUCCESS" if result.ok else "FAILED",
            attempts=result.attempts,
            payload_json=json.dumps(
                {
                    "to": self._mask_phone(phone),
                    "template": "PAGE_ACCESS_CODE",
                    "purpose": purpose,
                },
                ensure_ascii=False,
            ),
            last_error=result.error,
            external_id=result.message_id or None,
        )
        if not result.ok:
            code.consumed_at = now
            self.repo.commit()
            raise AppError(
                result.error or "验证码发送失败",
                code="SMS_SEND_FAILED",
                status_code=502,
            )
        self.repo.commit()
        return {
            "provider": result.provider,
            "message_id": result.message_id,
            "expires_in": settings.verification_code_ttl_seconds,
        }

    def verify_code(
        self,
        *,
        tenant_id: int,
        user_id: int,
        purpose: str,
        code: str,
    ) -> dict:
        purpose = self._valid_purpose(purpose)
        now = datetime.now(UTC).replace(tzinfo=None)
        row = self.repo.latest_code_for_update(
            tenant_id=tenant_id,
            user_id=user_id,
            purpose=purpose,
        )
        if row is None or row.expires_at < now or row.attempts >= row.max_attempts:
            raise AppError(
                "验证码无效或已过期",
                code="AUTH_CODE_INVALID",
                status_code=400,
            )
        expected = _digest(
            "verification-code",
            f"{tenant_id}:{user_id}:{purpose}:{code}",
        )
        if not hmac.compare_digest(row.code_hash, expected):
            row.attempts += 1
            if row.attempts >= row.max_attempts:
                row.consumed_at = now
            self.repo.commit()
            raise AppError(
                "验证码无效或已过期",
                code="AUTH_CODE_INVALID",
                status_code=400,
            )

        row.consumed_at = now
        raw_proof = secrets.token_urlsafe(32)
        settings = get_settings()
        self.repo.create_proof(
            tenant_id=tenant_id,
            user_id=user_id,
            purpose=purpose,
            proof_hash=_digest("page-access-proof", raw_proof),
            expires_at=now + timedelta(seconds=settings.page_access_proof_ttl_seconds),
        )
        self.repo.commit()
        return {
            "proof": raw_proof,
            "purpose": purpose,
            "expires_in": settings.page_access_proof_ttl_seconds,
        }

    def consume_proof(
        self,
        *,
        tenant_id: int,
        user_id: int,
        purpose: str,
        proof: str,
    ) -> dict:
        purpose = self._valid_purpose(purpose)
        now = datetime.now(UTC).replace(tzinfo=None)
        row = self.repo.proof_for_update(_digest("page-access-proof", proof))
        if (
            row is None
            or row.tenant_id != tenant_id
            or row.user_id != user_id
            or row.purpose != purpose
            or row.consumed_at is not None
            or row.expires_at < now
        ):
            raise AppError(
                "页面验证凭证无效或已过期",
                code="PAGE_ACCESS_PROOF_INVALID",
                status_code=403,
            )
        row.consumed_at = now
        self.repo.commit()
        return {"verified": True, "purpose": purpose}

    @staticmethod
    def _valid_purpose(purpose: str) -> str:
        value = purpose.strip().lower()
        if not _PURPOSE_RE.fullmatch(value):
            raise AppError(
                "验证用途不合法",
                code="PAGE_ACCESS_PURPOSE_INVALID",
                status_code=400,
            )
        return value

    @staticmethod
    def _mask_phone(phone: str) -> str:
        if len(phone) <= 5:
            return "***"
        return f"{phone[:3]}****{phone[-2:]}"

"""Application orchestration for fail-closed external integrations."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.infrastructure.platform.providers import (
    FakeNotificationProvider,
    NotifyMessage,
    ProductionWeChatNotifyProvider,
    SmsMessage,
    get_sms_provider,
)
from app.modules.platform_integrations.infrastructure.integration_repository import (
    IntegrationRepository,
)
from app.modules.workbench.application.summary_service import WorkbenchSummaryService
from app.shared.tenant_context import TenantContext

_FAKE_NOTIFY = FakeNotificationProvider()


class IntegrationService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.repo = IntegrationRepository(session, ctx.tenant_id)

    def _opaque_key(self, *, channel: str, source: str) -> str:
        digest = hashlib.sha256(
            f"{self.ctx.tenant_id}:{channel}:{source}".encode("utf-8")
        ).hexdigest()
        return f"idem-{digest}"

    def _claim(
        self,
        *,
        channel: str,
        provider: str,
        source_key: str,
        payload: dict[str, Any],
    ):
        key = self._opaque_key(channel=channel, source=source_key)
        row, state = self.repo.claim(
            channel=channel,
            provider=provider,
            idempotency_key=key,
            payload_json=json.dumps(payload, ensure_ascii=False),
            stale_after_seconds=300,
        )
        if state == "IN_PROGRESS":
            raise AppError(
                "相同幂等请求正在处理，请稍后查询结果",
                code="INTEGRATION_IN_PROGRESS",
                status_code=409,
            )
        return row, state, key

    def send_sms(
        self,
        *,
        to: str,
        template_code: str,
        params: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        settings = get_settings()
        provider = get_sms_provider(
            app_env=settings.app_env,
            provider=settings.sms_provider,
            api_key=settings.sms_api_key,
            endpoint=settings.sms_endpoint,
            timeout_seconds=settings.sms_timeout_seconds,
            max_retries=settings.sms_max_retries,
        )
        source_key = idempotency_key or f"{to}:{template_code}"
        row, state, opaque_key = self._claim(
            channel="sms",
            provider=provider.name,
            source_key=source_key,
            payload={"to_masked": self._mask_phone(to), "template": template_code},
        )
        if state == "SUCCESS":
            return {
                "provider": row.provider,
                "message_id": row.external_id,
                "deduped": True,
            }
        try:
            result = provider.send(
                SmsMessage(
                    to=to,
                    template_code=template_code,
                    params=params,
                    idempotency_key=opaque_key,
                )
            )
        except Exception as exc:
            self.repo.complete(
                row,
                ok=False,
                attempts=1,
                external_id=None,
                error=type(exc).__name__,
            )
            raise AppError("短信服务异常", code="SMS_SEND_FAILED", status_code=502) from exc
        self.repo.complete(
            row,
            ok=result.ok,
            attempts=result.attempts,
            external_id=result.message_id or None,
            error=result.error,
        )
        if not result.ok:
            raise AppError(result.error or "短信发送失败", code="SMS_SEND_FAILED", status_code=502)
        return {
            "provider": result.provider,
            "message_id": result.message_id,
            "deduped": False,
        }

    def notify(
        self,
        *,
        channel: str,
        subject: str,
        body: str,
        user_id: int | None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        target_user_id = user_id or self.ctx.user_id
        if not self.repo.active_user_exists(target_user_id):
            raise AppError("通知接收人不存在", code="NOTIFY_USER_NOT_FOUND", status_code=404)
        settings = get_settings()
        production_like = settings.app_env in {"staging", "production"}
        if production_like:
            provider_name = "wechat_production" if channel == "wechat" else "unconfigured"
        else:
            provider_name = "fake"
        source_key = idempotency_key or f"{channel}:{target_user_id}:{subject}"
        row, state, opaque_key = self._claim(
            channel=channel,
            provider=provider_name,
            source_key=source_key,
            payload={"subject": subject, "user_id": target_user_id},
        )
        if state == "SUCCESS":
            return {
                "ok": True,
                "provider": row.provider,
                "id": row.external_id,
                "deduped": True,
            }

        message = NotifyMessage(
            channel=channel,
            subject=subject,
            body=body,
            user_id=target_user_id,
            idempotency_key=opaque_key,
        )
        if not production_like:
            result = _FAKE_NOTIFY.notify(message)
        elif channel == "wechat" and settings.wechat_provider == "production":
            result = ProductionWeChatNotifyProvider(
                settings.wechat_app_id, settings.wechat_app_secret
            ).notify(message)
        else:
            result = {
                "ok": False,
                "provider": provider_name,
                "error": "NOTIFICATION_PROVIDER_NOT_CONFIGURED",
            }
        self.repo.complete(
            row,
            ok=bool(result.get("ok")),
            attempts=1,
            external_id=str(result.get("id") or "") or None,
            error=str(result.get("error") or "") or None,
        )
        if not result.get("ok"):
            raise AppError(
                "通知渠道未配置或调用失败",
                code="NOTIFY_FAILED",
                status_code=502,
            )
        return result

    def list_outbox(self) -> list[dict[str, Any]]:
        return [
            {
                "id": row.id,
                "channel": row.channel,
                "provider": row.provider,
                "status": row.status,
                "attempts": row.attempts,
                "last_error": row.last_error,
                "external_id": row.external_id,
            }
            for row in self.repo.list_recent()
        ]

    def park_summary_report(self) -> dict[str, Any]:
        data = WorkbenchSummaryService(self.session, self.ctx).summary()
        return {"report": "park_summary_v1", "data": data}

    @staticmethod
    def _mask_phone(value: str) -> str:
        if len(value) <= 5:
            return "***"
        return f"{value[:3]}****{value[-2:]}"

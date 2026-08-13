"""功能说明：集成适配层 HTTP + 出站持久化。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.infrastructure.database.models.integration_outbox import IntegrationOutbox
from app.infrastructure.database.session import get_db
from app.infrastructure.platform.providers import (
    FakeNotificationProvider,
    NotifyMessage,
    ProductionWeChatNotifyProvider,
    SmsMessage,
    get_sms_provider,
)
from app.shared.deps import get_tenant_context, require_permissions
from app.shared.response import ok
from app.shared.tenant_context import TenantContext

router = APIRouter(prefix="/integrations", tags=["Integrations"])

_FAKE_NOTIFY = FakeNotificationProvider()


class SmsSendBody(BaseModel):
    to: str = Field(min_length=5, max_length=32)
    template_code: str = "DEFAULT"
    params: dict = Field(default_factory=dict)
    idempotency_key: str = ""


@router.post("/sms/send")
def sms_send(
    body: SmsSendBody,
    ctx: TenantContext = Depends(require_permissions("identity.param.write")),
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    key = body.idempotency_key or f"sms-t{ctx.tenant_id}-{body.to}-{body.template_code}"
    existing = db.scalars(
        select(IntegrationOutbox).where(
            IntegrationOutbox.tenant_id == ctx.tenant_id,
            IntegrationOutbox.channel == "sms",
            IntegrationOutbox.idempotency_key == key,
            IntegrationOutbox.status == "SUCCESS",
        )
    ).first()
    if existing:
        return ok(
            {
                "provider": existing.provider,
                "message_id": existing.external_id,
                "deduped": True,
            },
            message="sent",
        )

    provider = get_sms_provider(
        app_env=settings.app_env,
        provider=settings.sms_provider,
        api_key=settings.sms_api_key,
        endpoint=settings.sms_endpoint,
        timeout_seconds=settings.sms_timeout_seconds,
        max_retries=settings.sms_max_retries,
    )
    result = provider.send(
        SmsMessage(
            to=body.to,
            template_code=body.template_code,
            params=body.params,
            idempotency_key=key,
        )
    )
    row = IntegrationOutbox(
        tenant_id=ctx.tenant_id,
        channel="sms",
        provider=result.provider,
        idempotency_key=key,
        status="SUCCESS" if result.ok else "FAILED",
        attempts=result.attempts,
        payload_json=json.dumps(
            {"to": body.to[:3] + "****", "template": body.template_code},
            ensure_ascii=False,
        ),
        last_error=result.error,
        external_id=result.message_id or None,
    )
    db.add(row)
    db.commit()
    if not result.ok:
        raise AppError(result.error or "短信发送失败", code="SMS_SEND_FAILED", status_code=502)
    return ok(
        {"provider": result.provider, "message_id": result.message_id, "deduped": False},
        message="sent",
    )


class NotifyBody(BaseModel):
    channel: str = "in_app"
    subject: str
    body: str
    user_id: int | None = None
    idempotency_key: str = ""


@router.post("/notify")
def notify(
    body: NotifyBody,
    ctx: TenantContext = Depends(require_permissions("identity.param.write")),
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    key = body.idempotency_key or f"notify-t{ctx.tenant_id}-{body.channel}-{body.subject}"
    if body.channel == "wechat" and settings.wechat_provider == "production":
        provider = ProductionWeChatNotifyProvider(
            settings.wechat_app_id, settings.wechat_app_secret
        )
        res = provider.notify(
            NotifyMessage(
                channel=body.channel,
                subject=body.subject,
                body=body.body,
                user_id=body.user_id or ctx.user_id,
                idempotency_key=key,
            )
        )
    else:
        res = _FAKE_NOTIFY.notify(
            NotifyMessage(
                channel=body.channel,
                subject=body.subject,
                body=body.body,
                user_id=body.user_id or ctx.user_id,
                idempotency_key=key,
            )
        )
    row = IntegrationOutbox(
        tenant_id=ctx.tenant_id,
        channel=body.channel,
        provider=str(res.get("provider") or "unknown"),
        idempotency_key=key,
        status="SUCCESS" if res.get("ok") else "FAILED",
        attempts=1,
        payload_json=json.dumps({"subject": body.subject}, ensure_ascii=False),
        last_error=res.get("error"),
        external_id=str(res.get("id") or "") or None,
    )
    db.add(row)
    db.commit()
    if not res.get("ok"):
        raise AppError(str(res.get("error") or "notify failed"), code="NOTIFY_FAILED", status_code=502)
    return ok(res, message="notified")


@router.get("/outbox")
def list_outbox(
    ctx: TenantContext = Depends(require_permissions("identity.param.read")),
    db: Session = Depends(get_db),
) -> dict:
    rows = db.scalars(
        select(IntegrationOutbox)
        .where(IntegrationOutbox.tenant_id == ctx.tenant_id)
        .order_by(IntegrationOutbox.id.desc())
        .limit(100)
    ).all()
    return ok(
        [
            {
                "id": r.id,
                "channel": r.channel,
                "provider": r.provider,
                "status": r.status,
                "attempts": r.attempts,
                "last_error": r.last_error,
                "external_id": r.external_id,
            }
            for r in rows
        ]
    )


@router.get("/reports/park-summary")
def park_summary_report(
    ctx: TenantContext = Depends(require_permissions("work_item:read")),
) -> dict:
    from app.infrastructure.database.session import SessionLocal
    from app.modules.workbench.application.summary_service import WorkbenchSummaryService

    db = SessionLocal()
    try:
        data = WorkbenchSummaryService(db, ctx).summary()
        return ok({"report": "park_summary_v1", "data": data})
    finally:
        db.close()

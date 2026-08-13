"""功能说明：集成适配层 HTTP（测试/运维探针，非业务主链）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.errors import AppError
from app.infrastructure.platform.providers import (
    FakeNotificationProvider,
    InMemoryFileStorage,
    NotifyMessage,
    SmsMessage,
    get_sms_provider,
)
from app.shared.deps import require_permissions
from app.shared.response import ok
from app.shared.tenant_context import TenantContext

router = APIRouter(prefix="/integrations", tags=["Integrations"])

# process-local fakes for test probe (not multi-worker durable)
_FAKE_NOTIFY = FakeNotificationProvider()
_MEM_FILES = InMemoryFileStorage()


class SmsSendBody(BaseModel):
    to: str = Field(min_length=5, max_length=32)
    template_code: str = "DEFAULT"
    params: dict = Field(default_factory=dict)
    idempotency_key: str = ""


@router.post("/sms/send")
def sms_send(
    body: SmsSendBody,
    ctx: TenantContext = Depends(require_permissions("identity.param.write")),
) -> dict:
    """发送短信（local/test=Fake；production 缺密钥 fail-closed）。"""

    settings = get_settings()
    provider = get_sms_provider(app_env=settings.app_env, api_key=None)
    result = provider.send(
        SmsMessage(
            to=body.to,
            template_code=body.template_code,
            params=body.params,
            idempotency_key=body.idempotency_key or f"t{ctx.tenant_id}-{body.to}",
        )
    )
    if not result.ok:
        raise AppError(result.error or "短信发送失败", code="SMS_SEND_FAILED", status_code=502)
    return ok(
        {
            "provider": result.provider,
            "message_id": result.message_id,
            "tenant_id": ctx.tenant_id,
        },
        message="sent",
    )


class NotifyBody(BaseModel):
    channel: str = "in_app"
    subject: str
    body: str
    user_id: int | None = None


@router.post("/notify")
def notify(
    body: NotifyBody,
    ctx: TenantContext = Depends(require_permissions("identity.param.write")),
) -> dict:
    res = _FAKE_NOTIFY.notify(
        NotifyMessage(
            channel=body.channel,
            subject=body.subject,
            body=body.body,
            user_id=body.user_id or ctx.user_id,
        )
    )
    return ok(res, message="notified")


class FilePutBody(BaseModel):
    object_key: str
    content_base64: str
    content_type: str = "text/plain"


@router.post("/files")
def put_file(
    body: FilePutBody,
    ctx: TenantContext = Depends(require_permissions("identity.param.write")),
) -> dict:
    import base64

    raw = base64.b64decode(body.content_base64.encode("ascii"))
    key = f"t{ctx.tenant_id}/{body.object_key.lstrip('/')}"
    obj = _MEM_FILES.put_bytes(object_key=key, data=raw, content_type=body.content_type)
    return ok(
        {
            "object_key": obj.object_key,
            "size": obj.size,
            "etag": obj.etag,
            "content_type": obj.content_type,
        },
        message="stored",
    )


@router.get("/reports/park-summary")
def park_summary_report(
    ctx: TenantContext = Depends(require_permissions("work_item:read")),
) -> dict:
    """最小报表适配：复用工作台指标语义（本地可运行）。"""

    from app.infrastructure.database.session import SessionLocal
    from app.modules.workbench.application.summary_service import WorkbenchSummaryService

    db = SessionLocal()
    try:
        data = WorkbenchSummaryService(db, ctx).summary()
        return ok({"report": "park_summary_v1", "data": data})
    finally:
        db.close()

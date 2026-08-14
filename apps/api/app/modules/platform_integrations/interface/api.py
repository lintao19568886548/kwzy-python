"""External integration HTTP boundary."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.platform_integrations.application.integration_service import (
    IntegrationService,
)
from app.shared.deps import require_permissions
from app.shared.response import ok
from app.shared.tenant_context import TenantContext

router = APIRouter(prefix="/integrations", tags=["Integrations"])
_IDEMPOTENCY_PATTERN = r"^[A-Za-z0-9._:-]{8,128}$"


class SmsSendBody(BaseModel):
    to: str = Field(pattern=r"^\+?[0-9]{5,20}$")
    template_code: str = Field(default="DEFAULT", min_length=1, max_length=64)
    params: dict = Field(default_factory=dict)
    idempotency_key: str = Field(default="", pattern=f"^(?:{_IDEMPOTENCY_PATTERN[1:-1]})?$")


class NotifyBody(BaseModel):
    channel: Literal["in_app", "email", "sms", "wechat"] = "in_app"
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)
    user_id: int | None = Field(default=None, gt=0)
    idempotency_key: str = Field(default="", pattern=f"^(?:{_IDEMPOTENCY_PATTERN[1:-1]})?$")


def _service(db: Session, ctx: TenantContext) -> IntegrationService:
    return IntegrationService(db, ctx)


@router.post("/sms/send")
def sms_send(
    body: SmsSendBody,
    ctx: TenantContext = Depends(require_permissions("identity.param.write")),
    db: Session = Depends(get_db),
) -> dict:
    data = _service(db, ctx).send_sms(
        to=body.to,
        template_code=body.template_code,
        params=body.params,
        idempotency_key=body.idempotency_key,
    )
    return ok(data, message="sent")


@router.post("/notify")
def notify(
    body: NotifyBody,
    ctx: TenantContext = Depends(require_permissions("identity.param.write")),
    db: Session = Depends(get_db),
) -> dict:
    data = _service(db, ctx).notify(
        channel=body.channel,
        subject=body.subject,
        body=body.body,
        user_id=body.user_id,
        idempotency_key=body.idempotency_key,
    )
    return ok(data, message="notified")


@router.get("/outbox")
def list_outbox(
    ctx: TenantContext = Depends(require_permissions("identity.param.read")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(_service(db, ctx).list_outbox())


@router.get("/reports/park-summary")
def park_summary_report(
    ctx: TenantContext = Depends(require_permissions("work_item:read")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(_service(db, ctx).park_summary_report())

"""Integration boundary security, idempotency, and fail-closed tests."""

from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.infrastructure.database.models.identity import Tenant, User
from app.infrastructure.database.models.integration_outbox import IntegrationOutbox


def _headers() -> dict[str, str]:
    token = create_access_token(
        "admin",
        {
            "uid": 1,
            "tenant_id": 1,
            "permissions": ["identity.param.write", "identity.param.read", "work_item:read"],
            "park_scope_mode": "ALL",
            "park_ids": [],
        },
    )
    return {"Authorization": f"Bearer {token}"}


def test_sms_idempotency_is_persisted_without_phone_pii(client, db_session) -> None:
    payload = {
        "to": "13800138000",
        "template_code": "COLLECTION",
        "params": {"case_id": 7},
        "idempotency_key": "collection-case-7",
    }
    first = client.post("/api/v1/integrations/sms/send", headers=_headers(), json=payload)
    second = client.post("/api/v1/integrations/sms/send", headers=_headers(), json=payload)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["data"]["deduped"] is False
    assert second.json()["data"]["deduped"] is True

    db_session.expire_all()
    rows = list(
        db_session.scalars(
            select(IntegrationOutbox).where(IntegrationOutbox.channel == "sms")
        ).all()
    )
    assert len(rows) == 1
    persisted = f"{rows[0].idempotency_key} {rows[0].payload_json}"
    assert "13800138000" not in persisted
    assert "collection-case-7" not in persisted


def test_notify_rejects_cross_tenant_user(client, db_session) -> None:
    foreign_tenant = Tenant(code="notify-foreign", name="通知外租户", status="ACTIVE")
    db_session.add(foreign_tenant)
    db_session.flush()
    foreign_user = User(
        tenant_id=foreign_tenant.id,
        username="foreign-notify-user",
        password_hash=hash_password("Foreign#73915"),
        real_name="外租户",
        status="ACTIVE",
    )
    db_session.add(foreign_user)
    db_session.commit()

    response = client.post(
        "/api/v1/integrations/notify",
        headers=_headers(),
        json={
            "channel": "in_app",
            "subject": "scope",
            "body": "must not cross tenant",
            "user_id": foreign_user.id,
            "idempotency_key": "notify-scope-check",
        },
    )
    assert response.status_code == 404
    assert response.json()["code"] == "NOTIFY_USER_NOT_FOUND"


def test_production_notification_never_reports_fake_success(client, monkeypatch) -> None:
    from app.modules.platform_integrations.application import integration_service

    monkeypatch.setattr(
        integration_service,
        "get_settings",
        lambda: SimpleNamespace(
            app_env="production",
            wechat_provider="auto",
            wechat_app_id="",
            wechat_app_secret="",
        ),
    )
    response = client.post(
        "/api/v1/integrations/notify",
        headers=_headers(),
        json={
            "channel": "in_app",
            "subject": "production",
            "body": "must fail closed",
            "idempotency_key": "production-notify-check",
        },
    )
    assert response.status_code == 502
    assert response.json()["code"] == "NOTIFY_FAILED"

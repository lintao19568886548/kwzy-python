"""Provider abstraction tests (no external network)."""

from __future__ import annotations

from app.infrastructure.platform.providers import (
    FakeNotificationProvider,
    FakeSmsProvider,
    InMemoryFileStorage,
    NotifyMessage,
    ProductionSmsProvider,
    SmsMessage,
    get_sms_provider,
)


def test_fake_sms_idempotent() -> None:
    p = FakeSmsProvider()
    r1 = p.send(SmsMessage(to="13800138000", template_code="T1", idempotency_key="k1"))
    r2 = p.send(SmsMessage(to="13800138000", template_code="T1", idempotency_key="k1"))
    assert r1.ok and r2.ok
    assert len(p.sent) == 1


def test_production_sms_fail_closed_without_key() -> None:
    p = ProductionSmsProvider(api_key=None)
    r = p.send(SmsMessage(to="13800138000", template_code="T1"))
    assert not r.ok
    assert r.error == "SMS_API_KEY_MISSING"


def test_get_sms_provider_local_is_fake() -> None:
    assert isinstance(get_sms_provider(app_env="test"), FakeSmsProvider)


def test_file_storage_roundtrip() -> None:
    s = InMemoryFileStorage()
    obj = s.put_bytes(object_key="a/b.txt", data=b"hello", content_type="text/plain")
    assert obj.size == 5
    assert s.get_bytes("a/b.txt") == b"hello"


def test_notify_fake() -> None:
    n = FakeNotificationProvider()
    res = n.notify(NotifyMessage(channel="in_app", subject="hi", body="x", user_id=1))
    assert res["ok"] is True
    assert len(n.messages) == 1

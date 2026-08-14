"""Provider abstraction tests (no external network)."""

from __future__ import annotations

from app.infrastructure.platform.providers import (
    FakeNotificationProvider,
    FakeSmsProvider,
    InMemoryFileStorage,
    LocalDiskFileStorage,
    NotifyMessage,
    ProductionSmsProvider,
    ProductionWeChatNotifyProvider,
    SmsMessage,
    get_file_storage,
    get_sms_provider,
)
from pathlib import Path


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


def test_production_cannot_force_fake_sms() -> None:
    assert isinstance(
        get_sms_provider(app_env="production", provider="fake"),
        ProductionSmsProvider,
    )


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


def test_wechat_production_fail_closed() -> None:
    p = ProductionWeChatNotifyProvider("", "")
    r = p.notify(NotifyMessage(channel="wechat", subject="s", body="b"))
    assert r["ok"] is False


def test_local_disk_storage(tmp_path: Path) -> None:
    s = LocalDiskFileStorage(str(tmp_path))
    s.put_bytes(object_key="a/b.txt", data=b"xyz")
    assert s.get_bytes("a/b.txt") == b"xyz"
    try:
        s.put_bytes(object_key="../x.txt", data=b"no")
        assert False, "should reject path escape"
    except ValueError:
        pass


def test_get_file_storage_auto_local() -> None:
    s = get_file_storage(app_env="test", provider="auto", local_root="./data/t")
    assert isinstance(s, LocalDiskFileStorage)


def test_production_storage_never_falls_back_to_local() -> None:
    from app.infrastructure.platform.providers import S3FileStorage

    assert isinstance(get_file_storage(app_env="production", provider="auto"), S3FileStorage)
    try:
        get_file_storage(app_env="production", provider="local")
        assert False, "production local storage must fail closed"
    except RuntimeError as exc:
        assert str(exc) == "LOCAL_STORAGE_FORBIDDEN_IN_PRODUCTION"

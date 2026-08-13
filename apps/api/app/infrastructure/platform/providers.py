"""功能说明：外部集成 Provider 抽象与本地 Fake 实现。

业务职责：
    短信、通知、附件等长尾能力的可替换适配层；
    local/test 默认 Fake，不调用外部收费服务。
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SmsMessage:
    to: str
    template_code: str
    params: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""


@dataclass
class SmsResult:
    ok: bool
    provider: str
    message_id: str
    error: Optional[str] = None


class SmsProvider(ABC):
    name: str = "base"

    @abstractmethod
    def send(self, message: SmsMessage) -> SmsResult:
        raise NotImplementedError


class FakeSmsProvider(SmsProvider):
    """测试/本地：记录发送并不外呼。"""

    name = "fake"

    def __init__(self) -> None:
        self.sent: list[SmsMessage] = []

    def send(self, message: SmsMessage) -> SmsResult:
        if not message.to:
            return SmsResult(ok=False, provider=self.name, message_id="", error="empty_to")
        key = message.idempotency_key or uuid.uuid4().hex
        # 幂等：同 key 只记一次
        if any(m.idempotency_key == key for m in self.sent if m.idempotency_key):
            return SmsResult(ok=True, provider=self.name, message_id=f"dup-{key[:8]}")
        message.idempotency_key = key
        self.sent.append(message)
        logger.info(
            "fake_sms_sent action=sms_send to_masked=%s",
            (message.to[:3] + "****" + message.to[-2:]) if len(message.to) > 5 else "***",
        )
        return SmsResult(ok=True, provider=self.name, message_id=f"fake-{key[:12]}")


class ProductionSmsProvider(SmsProvider):
    """生产短信：必须配置 API 密钥，否则 fail-closed。"""

    name = "production"

    def __init__(self, api_key: str | None, endpoint: str | None = None) -> None:
        self.api_key = (api_key or "").strip()
        self.endpoint = endpoint or ""

    def send(self, message: SmsMessage) -> SmsResult:
        if not self.api_key:
            return SmsResult(
                ok=False,
                provider=self.name,
                message_id="",
                error="SMS_API_KEY_MISSING",
            )
        # 不在无密钥时外呼；真实实现由运维配置后扩展
        return SmsResult(
            ok=False,
            provider=self.name,
            message_id="",
            error="SMS_PROVIDER_NOT_WIRED",
        )


def get_sms_provider(*, app_env: str, api_key: str | None = None) -> SmsProvider:
    env = (app_env or "local").lower()
    if env in {"local", "test", "dev"}:
        return FakeSmsProvider()
    return ProductionSmsProvider(api_key=api_key)


@dataclass
class NotifyMessage:
    channel: str  # in_app | email | sms
    subject: str
    body: str
    user_id: Optional[int] = None
    idempotency_key: str = ""


class NotificationProvider(ABC):
    @abstractmethod
    def notify(self, message: NotifyMessage) -> dict[str, Any]:
        raise NotImplementedError


class FakeNotificationProvider(NotificationProvider):
    def __init__(self) -> None:
        self.messages: list[NotifyMessage] = []

    def notify(self, message: NotifyMessage) -> dict[str, Any]:
        self.messages.append(message)
        return {"ok": True, "provider": "fake", "id": uuid.uuid4().hex[:12]}


@dataclass
class StoredObject:
    object_key: str
    content_type: str
    size: int
    etag: str


class FileStorageProvider(ABC):
    @abstractmethod
    def put_bytes(
        self, *, object_key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> StoredObject:
        raise NotImplementedError

    @abstractmethod
    def get_bytes(self, object_key: str) -> bytes:
        raise NotImplementedError


class InMemoryFileStorage(FileStorageProvider):
    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}
        self._meta: dict[str, StoredObject] = {}

    def put_bytes(
        self, *, object_key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> StoredObject:
        self._store[object_key] = data
        obj = StoredObject(
            object_key=object_key,
            content_type=content_type,
            size=len(data),
            etag=uuid.uuid4().hex[:16],
        )
        self._meta[object_key] = obj
        return obj

    def get_bytes(self, object_key: str) -> bytes:
        if object_key not in self._store:
            raise FileNotFoundError(object_key)
        return self._store[object_key]

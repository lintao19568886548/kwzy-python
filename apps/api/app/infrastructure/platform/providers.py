"""功能说明：外部集成 Provider 抽象、Fake/生产入口、重试与幂等。"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
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
    attempts: int = 1


class SmsProvider(ABC):
    name: str = "base"

    @abstractmethod
    def send(self, message: SmsMessage) -> SmsResult:
        raise NotImplementedError


class FakeSmsProvider(SmsProvider):
    name = "fake"

    def __init__(self) -> None:
        self.sent: list[SmsMessage] = []
        self._keys: set[str] = set()

    def send(self, message: SmsMessage) -> SmsResult:
        if not message.to:
            return SmsResult(ok=False, provider=self.name, message_id="", error="empty_to")
        key = message.idempotency_key or uuid.uuid4().hex
        if key in self._keys:
            return SmsResult(ok=True, provider=self.name, message_id=f"dup-{key[:8]}")
        message.idempotency_key = key
        self._keys.add(key)
        self.sent.append(message)
        logger.info(
            "fake_sms_sent action=sms_send to_masked=%s key=%s",
            (message.to[:3] + "****" + message.to[-2:]) if len(message.to) > 5 else "***",
            key[:8],
        )
        return SmsResult(ok=True, provider=self.name, message_id=f"fake-{key[:12]}")


class ProductionSmsProvider(SmsProvider):
    name = "production"

    def __init__(
        self,
        api_key: str | None,
        endpoint: str | None = None,
        *,
        timeout_seconds: int = 5,
        max_retries: int = 2,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.endpoint = endpoint or ""
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)

    def send(self, message: SmsMessage) -> SmsResult:
        if not self.api_key:
            return SmsResult(
                ok=False, provider=self.name, message_id="", error="SMS_API_KEY_MISSING"
            )
        # 未配置真实 HTTP 客户端时 fail-closed；保留重试骨架
        last_err = "SMS_PROVIDER_NOT_WIRED"
        for attempt in range(1, self.max_retries + 2):
            # 故意不外呼；接入真实密钥后替换此分支
            last_err = "SMS_PROVIDER_NOT_WIRED"
            if attempt <= self.max_retries:
                time.sleep(min(0.05 * attempt, 0.2))
        return SmsResult(
            ok=False,
            provider=self.name,
            message_id="",
            error=last_err,
            attempts=self.max_retries + 1,
        )


def get_sms_provider(
    *,
    app_env: str,
    provider: str = "auto",
    api_key: str | None = None,
    endpoint: str | None = None,
    timeout_seconds: int = 5,
    max_retries: int = 2,
) -> SmsProvider:
    mode = (provider or "auto").lower()
    env = (app_env or "local").lower()
    if mode == "fake" or (mode == "auto" and env in {"local", "test", "dev"}):
        return FakeSmsProvider()
    return ProductionSmsProvider(
        api_key=api_key,
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )


@dataclass
class NotifyMessage:
    channel: str  # in_app | email | sms | wechat
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
        self._keys: set[str] = set()

    def notify(self, message: NotifyMessage) -> dict[str, Any]:
        key = message.idempotency_key or uuid.uuid4().hex
        if key in self._keys:
            return {"ok": True, "provider": "fake", "id": f"dup-{key[:8]}", "deduped": True}
        self._keys.add(key)
        message.idempotency_key = key
        self.messages.append(message)
        return {"ok": True, "provider": "fake", "id": uuid.uuid4().hex[:12], "deduped": False}


class ProductionWeChatNotifyProvider(NotificationProvider):
    def __init__(self, app_id: str | None, app_secret: str | None) -> None:
        self.app_id = (app_id or "").strip()
        self.app_secret = (app_secret or "").strip()

    def notify(self, message: NotifyMessage) -> dict[str, Any]:
        if not self.app_id or not self.app_secret:
            return {
                "ok": False,
                "provider": "wechat_production",
                "error": "WECHAT_CREDENTIALS_MISSING",
            }
        return {
            "ok": False,
            "provider": "wechat_production",
            "error": "WECHAT_PROVIDER_NOT_WIRED",
        }


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

    @abstractmethod
    def delete(self, object_key: str) -> None:
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

    def delete(self, object_key: str) -> None:
        self._store.pop(object_key, None)
        self._meta.pop(object_key, None)


class LocalDiskFileStorage(FileStorageProvider):
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, object_key: str) -> Path:
        # 防路径穿越
        safe = object_key.replace("\\", "/").lstrip("/")
        if ".." in safe.split("/"):
            raise ValueError("invalid object_key")
        path = (self.root / safe).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise ValueError("path escape")
        return path

    def put_bytes(
        self, *, object_key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> StoredObject:
        path = self._path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredObject(
            object_key=object_key,
            content_type=content_type,
            size=len(data),
            etag=uuid.uuid4().hex[:16],
        )

    def get_bytes(self, object_key: str) -> bytes:
        path = self._path(object_key)
        if not path.is_file():
            raise FileNotFoundError(object_key)
        return path.read_bytes()

    def delete(self, object_key: str) -> None:
        path = self._path(object_key)
        if path.is_file():
            path.unlink()


class S3FileStorage(FileStorageProvider):
    """生产对象存储入口；无密钥 fail-closed。"""

    def __init__(
        self,
        *,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
    ) -> None:
        self.endpoint = endpoint
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key

    def put_bytes(
        self, *, object_key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> StoredObject:
        if not self.access_key or not self.bucket:
            raise RuntimeError("OSS_CREDENTIALS_MISSING")
        raise RuntimeError("S3_PROVIDER_NOT_WIRED")

    def get_bytes(self, object_key: str) -> bytes:
        raise RuntimeError("S3_PROVIDER_NOT_WIRED")

    def delete(self, object_key: str) -> None:
        raise RuntimeError("S3_PROVIDER_NOT_WIRED")


def get_file_storage(
    *,
    app_env: str,
    provider: str = "auto",
    local_root: str = "./data/attachments",
    endpoint: str = "",
    bucket: str = "",
    access_key: str = "",
    secret_key: str = "",
) -> FileStorageProvider:
    mode = (provider or "auto").lower()
    env = (app_env or "local").lower()
    if mode == "s3":
        return S3FileStorage(
            endpoint=endpoint,
            bucket=bucket,
            access_key=access_key,
            secret_key=secret_key,
        )
    if mode == "local" or (mode == "auto" and env in {"local", "test", "dev", "staging"}):
        return LocalDiskFileStorage(local_root)
    return LocalDiskFileStorage(local_root)

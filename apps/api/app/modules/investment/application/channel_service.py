"""Signed external lead channel administration, intake and replay."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time
import uuid
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.modules.investment.application.lead_service import LeadService
from app.modules.investment.domain.entities import ChannelSignatureEnvelope
from app.modules.investment.domain.rules import mask_phone
from app.modules.investment.infrastructure.completion_repository import (
    ChannelRepository,
    PublicChannelRepository,
)
from app.modules.park_property.infrastructure.park_repository import ParkRepository
from app.shared.tenant_context import ParkScopeMode, TenantContext

MAX_CHANNEL_BODY_BYTES = 64 * 1024
CHANNEL_FIELDS = {
    "name",
    "contact_phone",
    "contact_name",
    "agent_name",
    "intent_level",
    "intent_area",
    "desired_usage",
    "budget_unit_price",
    "remark",
}


def _channel_auth_error() -> AppError:
    return AppError("渠道认证失败", code="CHANNEL_AUTH_FAILED", status_code=401)


class ChannelService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.channels = ChannelRepository(session, ctx)
        self.parks = ParkRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def _require(self, permission: str) -> None:
        if not self.ctx.has_permission(permission):
            raise AppError("无渠道管理权限", code="PERMISSION_DENIED", status_code=403)

    def _assert_park(self, park_id: int) -> int:
        park_id = int(park_id)
        if not self.ctx.allows_park(park_id) or not self.parks.exists_in_tenant(park_id):
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        return park_id

    @staticmethod
    def _normalize_env_key(value: Any, field: str) -> str | None:
        key = str(value or "").strip()
        if not key:
            return None
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,127}", key):
            raise AppError(f"{field} 无效", code="VALIDATION_ERROR", status_code=400)
        return key

    @staticmethod
    def _normalize_mapping(value: Any) -> dict[str, str]:
        if value in (None, {}):
            return {field: field for field in sorted(CHANNEL_FIELDS)}
        if not isinstance(value, dict) or len(value) > len(CHANNEL_FIELDS):
            raise AppError("mapping 无效", code="VALIDATION_ERROR", status_code=400)
        mapping: dict[str, str] = {}
        for internal, external in value.items():
            internal_name = str(internal).strip()
            external_name = str(external).strip()
            if internal_name not in CHANNEL_FIELDS or not re.fullmatch(
                r"[A-Za-z][A-Za-z0-9_.-]{0,63}", external_name
            ):
                raise AppError("mapping 字段无效", code="VALIDATION_ERROR", status_code=400)
            if external_name in mapping.values():
                raise AppError("mapping 外部字段不得重复", code="VALIDATION_ERROR", status_code=400)
            mapping[internal_name] = external_name
        if not {"name", "contact_phone"}.issubset(mapping):
            raise AppError("mapping 必须包含 name/contact_phone", code="VALIDATION_ERROR", status_code=400)
        return mapping

    @staticmethod
    def _channel_dict(row) -> dict[str, Any]:
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "code": row.code,
            "name": row.name,
            "public_id": row.public_id,
            "enabled": bool(row.enabled),
            "secret_env_key": row.secret_env_key,
            "previous_secret_env_key": row.previous_secret_env_key,
            "secret_configured": bool(os.getenv(row.secret_env_key)),
            "previous_secret_configured": bool(
                row.previous_secret_env_key and os.getenv(row.previous_secret_env_key)
            ),
            "max_clock_skew_seconds": int(row.max_clock_skew_seconds),
            "allow_auto_assign": bool(row.allow_auto_assign),
            "mapping": row.mapping_json or {},
            "verification_status": row.verification_status,
            "lock_version": int(row.lock_version),
        }

    @staticmethod
    def _event_dict(row) -> dict[str, Any]:
        return {
            "id": int(row.id),
            "channel_id": int(row.channel_id),
            "park_id": int(row.park_id),
            "external_event_id": row.external_event_id,
            "payload_sha256": row.payload_sha256,
            "status": row.status,
            "safe_preview": row.safe_preview_json or {},
            "failure_code": row.failure_code,
            "lead_id": row.lead_id,
            "received_at": row.received_at.isoformat(),
            "processed_at": row.processed_at.isoformat() if row.processed_at else None,
            "replay_count": int(row.replay_count),
            "last_replayed_at": row.last_replayed_at.isoformat() if row.last_replayed_at else None,
        }

    def list(self) -> list[dict[str, Any]]:
        self._require("lead.channel.read")
        return [self._channel_dict(row) for row in self.channels.list()]

    def get(self, channel_id: int) -> dict[str, Any]:
        self._require("lead.channel.read")
        row = self.channels.get(channel_id)
        if row is None:
            raise AppError("渠道不存在", code="CHANNEL_NOT_FOUND", status_code=404)
        result = self._channel_dict(row)
        result["events"] = [self._event_dict(event) for event in self.channels.events(channel_id)]
        return result

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        self._require("lead.channel.write")
        park_id = self._assert_park(int(data["park_id"]))
        code = str(data.get("code") or "").strip().upper()
        name = str(data.get("name") or "").strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_.-]{1,63}", code) or not name:
            raise AppError("渠道 code/name 无效", code="VALIDATION_ERROR", status_code=400)
        secret_key = self._normalize_env_key(data.get("secret_env_key"), "secret_env_key")
        if secret_key is None:
            raise AppError("secret_env_key 必填", code="VALIDATION_ERROR", status_code=400)
        previous_key = self._normalize_env_key(
            data.get("previous_secret_env_key"), "previous_secret_env_key"
        )
        skew = int(data.get("max_clock_skew_seconds", 300))
        if skew < 30 or skew > 900:
            raise AppError("max_clock_skew_seconds 无效", code="VALIDATION_ERROR", status_code=400)
        enabled = bool(data.get("enabled", False))
        if enabled and not os.getenv(secret_key):
            raise AppError("渠道密钥环境变量未配置", code="CHANNEL_SECRET_UNAVAILABLE", status_code=409)
        try:
            row = self.channels.create(
                park_id=park_id,
                code=code,
                name=name[:128],
                public_id=str(uuid.uuid4()),
                enabled=enabled,
                secret_env_key=secret_key,
                previous_secret_env_key=previous_key,
                max_clock_skew_seconds=skew,
                allow_auto_assign=bool(data.get("allow_auto_assign", True)),
                mapping_json=self._normalize_mapping(data.get("mapping")),
                verification_status="NOT_CONNECTED",
                lock_version=1,
                created_by=self.ctx.user_id or None,
                updated_by=self.ctx.user_id or None,
            )
            self.audit.record(
                action="create",
                resource_type="LEAD_CHANNEL",
                resource_id=row.id,
                park_id=park_id,
                detail={"code": code, "enabled": enabled, "secret_env_key": secret_key},
            )
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError("渠道 code 冲突", code="CHANNEL_CONFLICT", status_code=409) from exc
        return self._channel_dict(row)

    def update(self, channel_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._require("lead.channel.write")
        row = self.channels.get(channel_id, for_update=True)
        if row is None:
            raise AppError("渠道不存在", code="CHANNEL_NOT_FOUND", status_code=404)
        if int(row.lock_version) != int(data.get("expected_version") or 0):
            raise AppError("渠道版本冲突", code="VERSION_CONFLICT", status_code=409)
        if "name" in data:
            name = str(data.get("name") or "").strip()
            if not name:
                raise AppError("name 无效", code="VALIDATION_ERROR", status_code=400)
            row.name = name[:128]
        if "secret_env_key" in data:
            key = self._normalize_env_key(data.get("secret_env_key"), "secret_env_key")
            if key is None:
                raise AppError("secret_env_key 无效", code="VALIDATION_ERROR", status_code=400)
            row.secret_env_key = key
            row.verification_status = "NOT_CONNECTED"
        if "previous_secret_env_key" in data:
            row.previous_secret_env_key = self._normalize_env_key(
                data.get("previous_secret_env_key"), "previous_secret_env_key"
            )
        if "mapping" in data:
            row.mapping_json = self._normalize_mapping(data.get("mapping"))
        if "max_clock_skew_seconds" in data:
            skew = int(data["max_clock_skew_seconds"])
            if skew < 30 or skew > 900:
                raise AppError("max_clock_skew_seconds 无效", code="VALIDATION_ERROR", status_code=400)
            row.max_clock_skew_seconds = skew
        if "allow_auto_assign" in data:
            row.allow_auto_assign = bool(data["allow_auto_assign"])
        if "enabled" in data:
            enabled = bool(data["enabled"])
            if enabled and not os.getenv(row.secret_env_key):
                raise AppError("渠道密钥环境变量未配置", code="CHANNEL_SECRET_UNAVAILABLE", status_code=409)
            row.enabled = enabled
        row.lock_version += 1
        row.updated_by = self.ctx.user_id or None
        self.channels.save(row)
        self.audit.record(
            action="update",
            resource_type="LEAD_CHANNEL",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"enabled": bool(row.enabled), "verification_status": row.verification_status},
        )
        self.session.commit()
        return self._channel_dict(row)

    def list_events(
        self, channel_id: int, *, status: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        self._require("lead.channel.read")
        if self.channels.get(channel_id) is None:
            raise AppError("渠道不存在", code="CHANNEL_NOT_FOUND", status_code=404)
        normalized = str(status or "").strip().upper() or None
        if normalized not in {None, "RECEIVED", "ACCEPTED", "QUARANTINED"}:
            raise AppError("status 无效", code="VALIDATION_ERROR", status_code=400)
        return [
            self._event_dict(row)
            for row in self.channels.events(channel_id, status=normalized, limit=min(max(limit, 1), 200))
        ]

    def replay(self, channel_id: int, event_id: int) -> dict[str, Any]:
        self._require("lead.channel.replay")
        channel = self.channels.get(channel_id, for_update=True)
        event = self.channels.event(event_id, for_update=True)
        if channel is None or event is None or int(event.channel_id) != int(channel.id):
            raise AppError("渠道事件不存在", code="CHANNEL_EVENT_NOT_FOUND", status_code=404)
        if event.status != "QUARANTINED":
            return self._event_dict(event)
        if not event.payload_ciphertext or not event.payload_key_ref:
            raise AppError("事件没有可安全重放的载荷", code="CHANNEL_REPLAY_UNAVAILABLE", status_code=409)
        secret = os.getenv(event.payload_key_ref)
        if not secret:
            raise AppError("重放密钥不可用", code="CHANNEL_REPLAY_KEY_UNAVAILABLE", status_code=409)
        raw = PublicChannelIntake.decrypt_payload(
            event.payload_ciphertext,
            secret=secret,
            channel_id=int(channel.id),
            external_event_id=event.external_event_id,
        )
        event.replay_count += 1
        event.last_replayed_at = utc_now()
        event.failure_code = None
        event.status = "RECEIVED"
        self.channels.save(event)
        self.session.commit()
        public = PublicChannelIntake(self.session)
        public.process(channel=channel, event=event, raw_body=raw, actor_user_id=self.ctx.user_id)
        refreshed = self.channels.event(event_id)
        if refreshed is None:
            raise AppError("渠道事件不存在", code="CHANNEL_EVENT_NOT_FOUND", status_code=404)
        return self._event_dict(refreshed)


class PublicChannelIntake:
    """Unauthenticated transport boundary that trusts only a configured HMAC channel."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.public = PublicChannelRepository(session)

    @staticmethod
    def _encryption_key(secret: str) -> bytes:
        return hashlib.sha256(("kwzy-channel-payload-v1|" + secret).encode("utf-8")).digest()

    @classmethod
    def encrypt_payload(
        cls, raw: bytes, *, secret: str, channel_id: int, external_event_id: str
    ) -> str:
        nonce = os.urandom(12)
        aad = f"{channel_id}:{external_event_id}".encode()
        encrypted = AESGCM(cls._encryption_key(secret)).encrypt(nonce, raw, aad)
        return base64.urlsafe_b64encode(nonce + encrypted).decode("ascii")

    @classmethod
    def decrypt_payload(
        cls, value: str, *, secret: str, channel_id: int, external_event_id: str
    ) -> bytes:
        try:
            packed = base64.urlsafe_b64decode(value.encode("ascii"))
            aad = f"{channel_id}:{external_event_id}".encode()
            return AESGCM(cls._encryption_key(secret)).decrypt(packed[:12], packed[12:], aad)
        except Exception as exc:
            raise AppError(
                "渠道载荷无法解密", code="CHANNEL_REPLAY_DECRYPT_FAILED", status_code=409
            ) from exc

    @staticmethod
    def _verify(
        channel,
        *,
        raw_body: bytes,
        timestamp: str,
        external_event_id: str,
        signature: str,
    ) -> tuple[str, str, str]:
        if len(raw_body) > MAX_CHANNEL_BODY_BYTES:
            raise _channel_auth_error()
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", external_event_id or ""):
            raise _channel_auth_error()
        try:
            timestamp_value = int(timestamp)
        except (TypeError, ValueError) as exc:
            raise _channel_auth_error() from exc
        if abs(int(time.time()) - timestamp_value) > int(channel.max_clock_skew_seconds):
            raise _channel_auth_error()
        body_sha = hashlib.sha256(raw_body).hexdigest()
        envelope = ChannelSignatureEnvelope(
            timestamp=timestamp_value,
            external_event_id=external_event_id,
            body_sha256=body_sha,
        )
        provided = str(signature or "")
        if not provided.startswith("v1=") or len(provided) != 67:
            raise _channel_auth_error()
        for key_ref in (channel.secret_env_key, channel.previous_secret_env_key):
            if not key_ref:
                continue
            secret = os.getenv(key_ref)
            if not secret:
                continue
            expected = "v1=" + hmac.new(
                secret.encode("utf-8"), envelope.signing_input(), hashlib.sha256
            ).hexdigest()
            if hmac.compare_digest(expected, provided):
                return key_ref, secret, body_sha
        raise _channel_auth_error()

    @staticmethod
    def _safe_preview(payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {"payload_type": type(payload).__name__}
        phone = payload.get("contact_phone")
        name = str(payload.get("name") or "")
        return {
            "fields": sorted(str(key)[:64] for key in payload)[:32],
            "name_sha256_prefix": hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
            if name
            else None,
            "contact_phone_masked": mask_phone(str(phone)) if phone else None,
        }

    @staticmethod
    def _normalize_payload(channel, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise AppError("载荷必须为对象", code="CHANNEL_PAYLOAD_INVALID", status_code=400)
        mapping = channel.mapping_json or {field: field for field in CHANNEL_FIELDS}
        external_fields = set(mapping.values())
        unknown = sorted(str(key) for key in payload if key not in external_fields)
        if unknown:
            raise AppError(
                "载荷包含未允许字段",
                code="CHANNEL_PAYLOAD_FIELD_DENIED",
                status_code=400,
                data={"fields": unknown[:20]},
            )
        normalized = {
            internal: payload[external]
            for internal, external in mapping.items()
            if external in payload
        }
        if not normalized.get("name") or not normalized.get("contact_phone"):
            raise AppError("载荷缺少必要字段", code="CHANNEL_PAYLOAD_INVALID", status_code=400)
        normalized["source_type"] = f"CHANNEL:{channel.code}"[:32]
        return normalized

    @staticmethod
    def _system_context(channel, *, actor_user_id: int = 0) -> TenantContext:
        permissions = ["lead:write", "lead:manage", "lead.assignment_rule.run"]
        return TenantContext(
            tenant_id=int(channel.tenant_id),
            user_id=int(actor_user_id or 0),
            username="channel-intake",
            park_ids=[int(channel.park_id)],
            permissions=permissions,
            database_permissions=permissions,
            park_scope_mode=ParkScopeMode.LIST,
            request_id=f"channel:{channel.public_id}",
        )

    def receive(
        self,
        *,
        public_id: str,
        raw_body: bytes,
        timestamp: str,
        external_event_id: str,
        signature: str,
    ) -> dict[str, Any]:
        channel = self.public.enabled_by_public_id(public_id)
        if channel is None:
            raise _channel_auth_error()
        key_ref, secret, payload_sha = self._verify(
            channel,
            raw_body=raw_body,
            timestamp=timestamp,
            external_event_id=external_event_id,
            signature=signature,
        )
        previous = self.public.event_by_external_id(int(channel.id), external_event_id)
        if previous is not None:
            if previous.payload_sha256 != payload_sha:
                raise AppError("事件标识载荷冲突", code="CHANNEL_EVENT_CONFLICT", status_code=409)
            return ChannelService._event_dict(previous)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        event = self.public.create_event(
            tenant_id=int(channel.tenant_id),
            channel_id=int(channel.id),
            park_id=int(channel.park_id),
            external_event_id=external_event_id,
            payload_sha256=payload_sha,
            payload_ciphertext=self.encrypt_payload(
                raw_body,
                secret=secret,
                channel_id=int(channel.id),
                external_event_id=external_event_id,
            ),
            payload_key_ref=key_ref,
            status="RECEIVED",
            safe_preview_json=self._safe_preview(payload),
            received_at=utc_now(),
        )
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            previous = self.public.event_by_external_id(int(channel.id), external_event_id)
            if previous is not None and previous.payload_sha256 == payload_sha:
                return ChannelService._event_dict(previous)
            raise AppError("渠道事件并发冲突", code="CHANNEL_EVENT_CONFLICT", status_code=409)
        if channel.verification_status == "NOT_CONNECTED":
            channel.verification_status = "LOCAL_CONTRACT_VERIFIED"
            self.session.add(channel)
            self.session.commit()
        self.process(channel=channel, event=event, raw_body=raw_body)
        refreshed = self.public.event_by_external_id(int(channel.id), external_event_id)
        if refreshed is None:
            raise AppError("渠道事件处理失败", code="CHANNEL_PROCESSING_FAILED", status_code=500)
        return ChannelService._event_dict(refreshed)

    def process(self, *, channel, event, raw_body: bytes, actor_user_id: int = 0) -> None:
        try:
            payload = json.loads(raw_body.decode("utf-8"))
            normalized = self._normalize_payload(channel, payload)
            normalized.update(
                {
                    "park_id": int(channel.park_id),
                    "source_ref": event.external_event_id,
                    "pool_status": "PUBLIC",
                    "auto_assign": bool(channel.allow_auto_assign),
                }
            )
            result = LeadService(
                self.session, self._system_context(channel, actor_user_id=actor_user_id)
            ).create_lead(normalized)
            event = self.public.event_by_external_id(int(channel.id), event.external_event_id)
            if event is None:
                raise AppError("渠道事件不存在", code="CHANNEL_EVENT_NOT_FOUND", status_code=404)
            event.status = "ACCEPTED"
            event.failure_code = None
            event.lead_id = int(result["id"])
            event.processed_at = utc_now()
            self.public.save_event(event)
            self.session.commit()
        except (AppError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.session.rollback()
            event = self.public.event_by_external_id(int(channel.id), event.external_event_id)
            if event is None:
                raise
            event.status = "QUARANTINED"
            event.failure_code = exc.code if isinstance(exc, AppError) else "CHANNEL_PAYLOAD_INVALID"
            event.processed_at = utc_now()
            self.public.save_event(event)
            self.session.commit()

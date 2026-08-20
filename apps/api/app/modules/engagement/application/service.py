"""Governed policy, enterprise-service, activity, and announcement orchestration."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.modules.engagement.domain.rules import (
    activity_transition,
    announcement_transition,
    canonical_hash,
    clean_text,
    evaluate_applicability,
    normalize_code,
    normalize_external_url,
    normalize_rule_set,
    policy_transition,
    require_version,
    service_case_transition,
)
from app.modules.engagement.infrastructure.repository import EngagementRepository
from app.modules.workflow.application.approval_service import ApprovalService
from app.shared.tenant_context import TenantContext


class EngagementService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.repo = EngagementRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)
        self.approvals = ApprovalService(session, ctx)

    def _permission(self, *codes: str) -> None:
        if any(self.ctx.has_permission(code) for code in codes):
            return
        raise AppError("无操作权限", code="PERMISSION_DENIED", status_code=403)

    def _commit(self, message: str, code: str = "ENGAGEMENT_CONFLICT") -> None:
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(message, code=code, status_code=409) from exc

    def _park(self, value: Any) -> int:
        park_id = int(value)
        if self.repo.park(park_id) is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        return park_id

    def _principal(self, park_id: int | None = None):  # type: ignore[no-untyped-def]
        principal = self.repo.principal_for_user(self.ctx.user_id, park_id=park_id)
        if principal is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        return principal

    def _attachments(self, values: list[int]) -> list[dict[str, int]]:
        result: list[dict[str, int]] = []
        for value in sorted({int(item) for item in values}):
            if self.repo.attachment(value) is None:
                raise AppError("附件不存在", code="ATTACHMENT_NOT_FOUND", status_code=404)
            result.append({"attachment_id": value})
        return result

    @staticmethod
    def _evidence(value: Any) -> list[dict[str, str]] | None:
        if value is None:
            return None
        if not isinstance(value, list) or len(value) > 32:
            raise AppError("evidence 格式不正确", code="VALIDATION_ERROR", status_code=400)
        normalized: list[dict[str, str]] = []
        for index, raw in enumerate(value):
            if not isinstance(raw, dict) or not raw or len(raw) > 8:
                raise AppError(
                    f"evidence[{index}] 格式不正确",
                    code="VALIDATION_ERROR",
                    status_code=400,
                )
            normalized.append(
                {
                    clean_text(key, field="evidence key", maximum=48): clean_text(
                        item, field="evidence value", maximum=1000
                    )
                    for key, item in raw.items()
                }
            )
        return normalized

    @staticmethod
    def _content(value: Any, *, field: str, maximum: int = 50000) -> str:
        content = str(value or "").strip()
        if not content:
            raise AppError(f"{field} 必填", code="VALIDATION_ERROR", status_code=400)
        if len(content) > maximum or "\x00" in content:
            raise AppError(f"{field} 不合法", code="VALIDATION_ERROR", status_code=400)
        if "<script" in content.lower() or "javascript:" in content.lower():
            raise AppError(f"{field} 含不安全内容", code="UNSAFE_CONTENT", status_code=400)
        return content

    @staticmethod
    def _key(value: str) -> str:
        return clean_text(value, field="Idempotency-Key", maximum=128)

    @staticmethod
    def _definition(value: str) -> str:
        return normalize_code(value, field="definition_code")

    @staticmethod
    def _approval_key(kind: str, aggregate_id: int, value: str) -> str:
        normalized_kind = normalize_code(kind, field="approval_kind").lower().replace("_", "-")
        fingerprint = canonical_hash(
            {"aggregate_id": int(aggregate_id), "key": EngagementService._key(value)}
        )
        return f"eng-{normalized_kind}:{fingerprint[:40]}"

    @staticmethod
    def _number(prefix: str, key: str) -> str:
        return f"{prefix}-{utc_now():%Y%m%d}-{canonical_hash(key)[:10].upper()}"

    @staticmethod
    def _approval_biz_id(aggregate_id: int, version) -> str:  # type: ignore[no-untyped-def]
        return canonical_hash(
            {
                "aggregate_id": int(aggregate_id),
                "version": int(version.version),
                "checksum": version.checksum,
            }
        )

    @staticmethod
    def _approved_exact(approval, *, biz_type: str, aggregate_id: int, version) -> bool:  # type: ignore[no-untyped-def]
        return bool(
            approval is not None
            and approval.status == "APPROVED"
            and approval.biz_type == biz_type
            and approval.biz_id == EngagementService._approval_biz_id(aggregate_id, version)
        )

    @staticmethod
    def _version_base(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "version": int(row.version),
            "status": row.status,
            "checksum": row.checksum,
            "created_at": row.created_at.isoformat(),
            "published_at": row.published_at.isoformat() if row.published_at else None,
        }

    def overview(self) -> dict[str, Any]:
        self._permission("engagement:read")
        return {
            **self.repo.counts(),
            "truth": {
                "policy_guidance": "LOCAL_RELEVANCE_NOT_OFFICIAL_ELIGIBILITY",
                "external_service_providers": "NOT_CONNECTED",
                "external_notifications": "NOT_CONNECTED",
                "tenant_mini_program": "OUT_OF_SCOPE",
                "legacy_real_migration": "BLOCKED_AUTHORIZED_EXPORT_REQUIRED",
                "production_contacted": False,
            },
        }

    # Policy governance -------------------------------------------------

    def _policy_version_dict(self, row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            **self._version_base(row),
            "title": row.title,
            "summary": row.summary,
            "content_text": row.content_text,
            "category": row.category,
            "region_code": row.region_code,
            "source": {
                "type": row.source_type,
                "system": row.source_system,
                "identifier": row.source_identifier,
                "publisher": row.source_publisher,
                "url": row.source_url,
                "published_at": (
                    row.source_published_at.isoformat() if row.source_published_at else None
                ),
            },
            "effective_on": row.effective_on.isoformat() if row.effective_on else None,
            "expires_on": row.expires_on.isoformat() if row.expires_on else None,
            "attachments": row.attachments_json,
            "applicability": row.applicability_json,
            "approval_id": row.approval_id,
        }

    def _policy_dict(self, row, *, include_events: bool = False) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        version = self.repo.policy_version(row.id, row.current_version)
        result = {
            "id": int(row.id),
            "park_id": int(row.park_id) if row.park_id is not None else None,
            "code": row.code,
            "status": row.status,
            "current_version": int(row.current_version),
            "published_version": row.published_version,
            "lock_version": int(row.lock_version),
            "version": self._policy_version_dict(version) if version else None,
        }
        if include_events:
            result["events"] = [
                {
                    "id": int(item.id),
                    "version": int(item.version),
                    "event_type": item.event_type,
                    "reason": item.reason,
                    "detail": item.detail_json,
                    "occurred_at": item.occurred_at.isoformat(),
                }
                for item in self.repo.policy_events(row.id)
            ]
        return result

    def list_policies(self, *, tenant_view: bool = False) -> list[dict[str, Any]]:
        self._permission("engagement:read")
        principal = self._principal() if tenant_view else None
        rows = self.repo.policies(published_only=tenant_view)
        result: list[dict[str, Any]] = []
        today = utc_now().date()
        for row in rows:
            if (
                principal is not None
                and row.park_id is not None
                and int(row.park_id) not in principal[1]
            ):
                continue
            version_no = row.published_version if tenant_view else row.current_version
            version = self.repo.policy_version(row.id, version_no or row.current_version)
            if tenant_view and (
                version is None
                or version.status != "PUBLISHED"
                or (version.effective_on and version.effective_on > today)
                or (version.expires_on and version.expires_on < today)
            ):
                continue
            item = self._policy_dict(row)
            if version is not None:
                item["version"] = self._policy_version_dict(version)
            result.append(item)
        return result

    def get_policy(self, policy_id: int, *, tenant_view: bool = False) -> dict[str, Any]:
        self._permission("engagement:read")
        row = self.repo.policy(policy_id)
        if row is None or (
            tenant_view
            and (
                row.published_version is None
                or row.status in {"EXPIRED", "WITHDRAWN"}
            )
        ):
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        if tenant_view:
            principal, parks = self._principal()
            if row.park_id is not None and int(row.park_id) not in parks:
                raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
            del principal
            version = self.repo.policy_version(row.id, row.published_version or 0)
            today = utc_now().date()
            if version is None or (
                (version.effective_on and version.effective_on > today)
                or (version.expires_on and version.expires_on < today)
            ):
                raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        result = self._policy_dict(row, include_events=not tenant_view)
        if tenant_view:
            published = self.repo.policy_version(row.id, row.published_version or 0)
            result["version"] = self._policy_version_dict(published) if published else None
        return result

    def create_policy(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("engagement:policy_manage")
        park_id = self._park(data["park_id"]) if data.get("park_id") is not None else None
        source_url = (
            normalize_external_url(data["source_url"], allowed_hosts=set(data["allowed_hosts"]))
            if data.get("source_url")
            else None
        )
        snapshot = {
            "title": clean_text(data["title"], field="title", maximum=255),
            "summary": clean_text(
                data.get("summary"), field="summary", maximum=1000, required=False
            )
            or None,
            "content_text": self._content(data["content_text"], field="content_text"),
            "category": normalize_code(data["category"], field="category"),
            "region_code": data.get("region_code"),
            "source_type": normalize_code(data["source_type"], field="source_type"),
            "source_system": data.get("source_system"),
            "source_identifier": data.get("source_identifier"),
            "source_publisher": clean_text(
                data["source_publisher"], field="source_publisher", maximum=255
            ),
            "source_url": source_url,
            "source_published_at": data.get("source_published_at"),
            "effective_on": data.get("effective_on"),
            "expires_on": data.get("expires_on"),
            "attachments_json": self._attachments(data.get("attachment_ids", [])),
            "applicability_json": normalize_rule_set(data.get("applicability", [])),
        }
        if (
            snapshot["effective_on"]
            and snapshot["expires_on"]
            and snapshot["expires_on"] < snapshot["effective_on"]
        ):
            raise AppError("政策有效期不正确", code="VALIDATION_ERROR", status_code=400)
        row = self.repo.create(
            "policy",
            park_id=park_id,
            code=normalize_code(data["code"]),
            status="DRAFT",
            current_version=1,
            lock_version=1,
            created_by=self.ctx.user_id or None,
        )
        version = self.repo.create(
            "policy_version",
            policy_id=row.id,
            version=1,
            status="DRAFT",
            checksum=canonical_hash(snapshot),
            created_by=self.ctx.user_id or None,
            **snapshot,
        )
        self.repo.create(
            "policy_event",
            policy_id=row.id,
            version=1,
            event_type="CREATED",
            reason=None,
            detail_json={"checksum": version.checksum},
            idempotency_key=f"policy-created:{row.id}:1",
            actor_user_id=self.ctx.user_id or None,
            occurred_at=utc_now(),
        )
        self.audit.record(
            action="create",
            resource_type="ENGAGEMENT_POLICY",
            resource_id=row.id,
            park_id=park_id,
            detail={"code": row.code, "version": 1, "checksum": version.checksum},
        )
        self._commit("政策编码或引用冲突", "POLICY_CONFLICT")
        return self._policy_dict(row, include_events=True)

    def revise_policy(
        self, policy_id: int, data: dict[str, Any], *, key: str
    ) -> dict[str, Any]:
        self._permission("engagement:policy_manage")
        row = self.repo.policy(policy_id, for_update=True)
        if row is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        event_key = f"policy-updated:{row.id}:{self._key(key)}"
        request_fingerprint = canonical_hash(data)
        existing_event = self.repo.policy_event_by_key(event_key)
        if existing_event is not None:
            if (existing_event.detail_json or {}).get("request_fingerprint") != request_fingerprint:
                raise AppError(
                    "幂等键请求内容冲突", code="IDEMPOTENCY_CONFLICT", status_code=409
                )
            return self._policy_dict(row, include_events=True)
        require_version(row.lock_version, data["expected_version"])
        supplied_park = int(data["park_id"]) if data.get("park_id") is not None else None
        if supplied_park != row.park_id or normalize_code(data["code"]) != row.code:
            raise AppError("政策标识或园区不可变", code="VALIDATION_ERROR", status_code=400)
        current = self.repo.policy_version(row.id, row.current_version, for_update=True)
        if current is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        approval = self.repo.approval(row.approval_id)
        if row.status == "PENDING_APPROVAL" and approval is not None and approval.status == "PENDING":
            raise AppError("待审版本须先撤回审批", code="APPROVAL_PENDING", status_code=409)
        source_url = (
            normalize_external_url(data["source_url"], allowed_hosts=set(data["allowed_hosts"]))
            if data.get("source_url")
            else None
        )
        snapshot = {
            "title": clean_text(data["title"], field="title", maximum=255),
            "summary": clean_text(
                data.get("summary"), field="summary", maximum=1000, required=False
            )
            or None,
            "content_text": self._content(data["content_text"], field="content_text"),
            "category": normalize_code(data["category"], field="category"),
            "region_code": data.get("region_code"),
            "source_type": normalize_code(data["source_type"], field="source_type"),
            "source_system": data.get("source_system"),
            "source_identifier": data.get("source_identifier"),
            "source_publisher": clean_text(
                data["source_publisher"], field="source_publisher", maximum=255
            ),
            "source_url": source_url,
            "source_published_at": data.get("source_published_at"),
            "effective_on": data.get("effective_on"),
            "expires_on": data.get("expires_on"),
            "attachments_json": self._attachments(data.get("attachment_ids", [])),
            "applicability_json": normalize_rule_set(data.get("applicability", [])),
        }
        if (
            snapshot["effective_on"]
            and snapshot["expires_on"]
            and snapshot["expires_on"] < snapshot["effective_on"]
        ):
            raise AppError("政策有效期不正确", code="VALIDATION_ERROR", status_code=400)
        checksum = canonical_hash(snapshot)
        if current.status == "DRAFT" and row.published_version is None:
            version = current
            for field, value in snapshot.items():
                setattr(version, field, value)
            version.checksum = checksum
        else:
            if current.status != "PUBLISHED":
                current.status = "RETIRED"
                self.repo.save(current)
            row.current_version += 1
            version = self.repo.create(
                "policy_version",
                policy_id=row.id,
                version=row.current_version,
                status="DRAFT",
                checksum=checksum,
                created_by=self.ctx.user_id or None,
                **snapshot,
            )
        row.status = "DRAFT"
        row.approval_id = None
        row.lock_version += 1
        self.repo.save(row)
        self.repo.save(version)
        self.repo.create(
            "policy_event",
            policy_id=row.id,
            version=version.version,
            event_type="UPDATED",
            reason=None,
            detail_json={
                "checksum": version.checksum,
                "request_fingerprint": request_fingerprint,
            },
            idempotency_key=event_key,
            actor_user_id=self.ctx.user_id or None,
            occurred_at=utc_now(),
        )
        self.audit.record(
            action="revise",
            resource_type="ENGAGEMENT_POLICY",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"version": int(version.version), "checksum": version.checksum},
        )
        self._commit("政策修订冲突", "POLICY_REVISION_CONFLICT")
        return self._policy_dict(row, include_events=True)

    def submit_policy(self, policy_id: int, data: dict[str, Any], *, key: str) -> dict[str, Any]:
        self._permission("engagement:policy_manage")
        row = self.repo.policy(policy_id, for_update=True)
        if row is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        version = self.repo.policy_version(row.id, row.current_version, for_update=True)
        approval_key = self._approval_key("POLICY", row.id, key)
        submit_fingerprint = canonical_hash(data)
        existing_approval = self.repo.approval(row.approval_id)
        if (
            row.status == "PENDING_APPROVAL"
            and version is not None
            and version.status == "SUBMITTED"
            and existing_approval is not None
            and existing_approval.idempotency_key == approval_key
        ):
            if (existing_approval.snapshot_json or {}).get("_submit_fingerprint") != submit_fingerprint:
                raise AppError(
                    "幂等键请求内容冲突", code="IDEMPOTENCY_CONFLICT", status_code=409
                )
            return self._policy_dict(row, include_events=True)
        require_version(row.lock_version, data["expected_version"])
        if version is None or version.status != "DRAFT" or row.status != "DRAFT":
            raise AppError("政策状态不可提交", code="POLICY_STATE_INVALID", status_code=409)
        approval = self.approvals.create(
            {
                "biz_type": "ENGAGEMENT_POLICY",
                "biz_id": self._approval_biz_id(row.id, version),
                "title": f"政策发布：{version.title}",
                "park_id": row.park_id,
                "definition_code": self._definition(data["definition_code"]),
                "idempotency_key": approval_key,
                "priority": data.get("priority", "MEDIUM"),
                "snapshot": {
                    **self._policy_version_dict(version),
                    "_submit_fingerprint": submit_fingerprint,
                },
            }
        )
        row.status = policy_transition(row.status, "PENDING_APPROVAL")
        row.approval_id = int(approval["id"])
        row.lock_version += 1
        version.status = "SUBMITTED"
        version.approval_id = int(approval["id"])
        self.repo.save(row)
        self.repo.save(version)
        self.repo.create(
            "policy_event",
            policy_id=row.id,
            version=version.version,
            event_type="SUBMITTED",
            reason=None,
            detail_json={"approval_id": approval["id"], "checksum": version.checksum},
            idempotency_key=f"policy-submit:{row.id}:{version.version}",
            actor_user_id=self.ctx.user_id or None,
            occurred_at=utc_now(),
        )
        self._commit("政策提交冲突", "POLICY_SUBMIT_CONFLICT")
        return self._policy_dict(row, include_events=True)

    def publish_policy(self, policy_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("engagement:policy_manage")
        row = self.repo.policy(policy_id, for_update=True)
        if row is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        require_version(row.lock_version, data["expected_version"])
        version = self.repo.policy_version(row.id, row.current_version, for_update=True)
        approval = self.repo.approval(row.approval_id)
        if version is None or version.status != "SUBMITTED" or approval is None:
            raise AppError("政策审批关联无效", code="POLICY_APPROVAL_INVALID", status_code=409)
        if not self._approved_exact(
            approval,
            biz_type="ENGAGEMENT_POLICY",
            aggregate_id=row.id,
            version=version,
        ):
            raise AppError("政策尚未审批通过", code="APPROVAL_NOT_APPROVED", status_code=409)
        row.status = policy_transition(policy_transition(row.status, "APPROVED"), "PUBLISHED")
        row.published_version = version.version
        row.lock_version += 1
        version.status = "PUBLISHED"
        version.published_by = self.ctx.user_id or None
        version.published_at = utc_now()
        self.repo.save(row)
        self.repo.save(version)
        for event_type in ("APPROVED", "PUBLISHED"):
            self.repo.create(
                "policy_event",
                policy_id=row.id,
                version=version.version,
                event_type=event_type,
                reason=None,
                detail_json={"approval_id": approval.id, "checksum": version.checksum},
                idempotency_key=f"policy-{event_type.lower()}:{row.id}:{version.version}",
                actor_user_id=self.ctx.user_id or None,
                occurred_at=utc_now(),
            )
        self.audit.record(
            action="publish",
            resource_type="ENGAGEMENT_POLICY",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"version": version.version, "checksum": version.checksum},
        )
        self._commit("政策发布冲突", "POLICY_PUBLISH_CONFLICT")
        return self._policy_dict(row, include_events=True)

    def withdraw_policy(
        self, policy_id: int, data: dict[str, Any], *, key: str
    ) -> dict[str, Any]:
        self._permission("engagement:policy_manage")
        row = self.repo.policy(policy_id, for_update=True)
        if row is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        event_key = f"policy-withdrawn:{row.id}:{self._key(key)}"
        if self.repo.policy_event_by_key(event_key) is not None:
            return self._policy_dict(row, include_events=True)
        require_version(row.lock_version, data["expected_version"])
        row.status = policy_transition(row.status, "WITHDRAWN")
        row.lock_version += 1
        version_no = row.published_version or row.current_version
        version = self.repo.policy_version(row.id, version_no, for_update=True)
        if version is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        if version.status != "DRAFT":
            version.status = "RETIRED"
            self.repo.save(version)
        self.repo.save(row)
        self.repo.create(
            "policy_event",
            policy_id=row.id,
            version=version.version,
            event_type="WITHDRAWN",
            reason=clean_text(data["reason"], field="reason", maximum=1000),
            detail_json={"checksum": version.checksum},
            idempotency_key=event_key,
            actor_user_id=self.ctx.user_id or None,
            occurred_at=utc_now(),
        )
        self.audit.record(
            action="withdraw",
            resource_type="ENGAGEMENT_POLICY",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"version": int(version.version), "checksum": version.checksum},
        )
        self._commit("政策撤回冲突", "POLICY_WITHDRAW_CONFLICT")
        return self._policy_dict(row, include_events=True)

    def expire_policies(self, *, due_on, limit: int) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        self._permission("engagement:policy_manage")
        expired = 0
        for row in list(self.repo.expirable_policies(due_on))[: int(limit)]:
            version = self.repo.policy_version(row.id, row.published_version or 0, for_update=True)
            if version is None:
                continue
            event_key = f"policy-expired:{row.id}:{version.version}"
            if self.repo.policy_event_by_key(event_key) is not None:
                continue
            row.status = policy_transition(row.status, "EXPIRED")
            row.lock_version += 1
            version.status = "RETIRED"
            self.repo.save(row)
            self.repo.save(version)
            self.repo.create(
                "policy_event",
                policy_id=row.id,
                version=version.version,
                event_type="EXPIRED",
                reason="effective window elapsed",
                detail_json={"expires_on": version.expires_on.isoformat()},
                idempotency_key=event_key,
                actor_user_id=self.ctx.user_id or None,
                occurred_at=utc_now(),
            )
            expired += 1
        self._commit("政策到期处理冲突", "POLICY_EXPIRY_CONFLICT")
        return {"expired": expired, "due_on": due_on.isoformat(), "production_contacted": False}

    def match_policy(self, policy_id: int, *, key: str) -> dict[str, Any]:
        self._permission("engagement:read")
        row = self.repo.policy(policy_id)
        if row is None or row.published_version is None or row.status in {"EXPIRED", "WITHDRAWN"}:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        principal, parks = self._principal()
        park_id = int(row.park_id) if row.park_id is not None else (parks[0] if parks else 0)
        if not park_id or park_id not in parks:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        version = self.repo.policy_version(row.id, row.published_version)
        if version is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        today = utc_now().date()
        if (version.effective_on and version.effective_on > today) or (
            version.expires_on and version.expires_on < today
        ):
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        eligible, matched, unmet = evaluate_applicability(
            version.applicability_json,
            self.repo.party_projection(principal.party_id, park_id),
        )
        event_key = f"policy-match:{row.id}:{principal.party_id}:{self._key(key)}"
        existing_event = self.repo.policy_event_by_key(event_key)
        if existing_event is not None:
            detail = existing_event.detail_json or {}
            return {
                "policy_id": int(row.id),
                "version": int(existing_event.version),
                "party_id": int(principal.party_id),
                "local_relevance": bool(detail.get("local_relevance")),
                "matched_reasons": list(detail.get("matched", [])),
                "unmet_reasons": list(detail.get("unmet", [])),
                "official_eligibility": "NOT_DETERMINED",
                "filing_available": False,
            }
        self.repo.create(
            "policy_event",
            policy_id=row.id,
            version=version.version,
            event_type="MATCH_EVALUATED",
            reason=None,
            detail_json={
                "party_id": int(principal.party_id),
                "matched": matched,
                "unmet": unmet,
                "local_relevance": eligible,
                "official_eligibility": "NOT_DETERMINED",
            },
            idempotency_key=event_key,
            actor_user_id=self.ctx.user_id or None,
            occurred_at=utc_now(),
        )
        self._commit("政策匹配记录冲突", "POLICY_MATCH_CONFLICT")
        return {
            "policy_id": int(row.id),
            "version": int(version.version),
            "party_id": int(principal.party_id),
            "local_relevance": eligible,
            "matched_reasons": matched,
            "unmet_reasons": unmet,
            "official_eligibility": "NOT_DETERMINED",
            "filing_available": False,
        }

    def follow_policy(self, policy_id: int, *, active: bool) -> dict[str, Any]:
        self._permission("engagement:read")
        row = self.repo.policy(policy_id)
        if row is None or row.published_version is None or row.status in {"EXPIRED", "WITHDRAWN"}:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        principal, parks = self._principal()
        park_id = int(row.park_id) if row.park_id is not None else (parks[0] if parks else 0)
        if not park_id or park_id not in parks:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        follow = self.repo.policy_follow(row.id, principal.party_id)
        if follow is None:
            follow = self.repo.create(
                "policy_follow",
                policy_id=row.id,
                party_id=principal.party_id,
                park_id=park_id,
                user_id=self.ctx.user_id,
                status="ACTIVE" if active else "UNFOLLOWED",
            )
        else:
            follow.status = "ACTIVE" if active else "UNFOLLOWED"
            self.repo.save(follow)
        self._commit("政策关注冲突", "POLICY_FOLLOW_CONFLICT")
        return {"policy_id": int(row.id), "status": follow.status}

    def create_consultation(
        self, policy_id: int, data: dict[str, Any], *, key: str
    ) -> dict[str, Any]:
        self._permission("engagement:read")
        key = self._key(key)
        payload_hash = canonical_hash(data)
        principal, parks = self._principal()
        existing = self.repo.consultation_by_key(key)
        if existing is not None:
            if int(existing.party_id) != int(principal.party_id):
                raise AppError(
                    "幂等键已用于其他主体", code="IDEMPOTENCY_CONFLICT", status_code=409
                )
            if existing.payload_hash != payload_hash:
                raise AppError("幂等键请求内容冲突", code="IDEMPOTENCY_CONFLICT", status_code=409)
            return self._consultation_dict(existing)
        row = self.repo.policy(policy_id)
        if row is None or row.published_version is None or row.status in {"EXPIRED", "WITHDRAWN"}:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        park_id = int(data.get("park_id") or row.park_id or (parks[0] if parks else 0))
        if park_id not in parks:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        consultation = self.repo.create(
            "policy_consultation",
            park_id=park_id,
            policy_id=row.id,
            policy_version=row.published_version,
            party_id=principal.party_id,
            case_no=self._number("PC", key),
            subject=clean_text(data["subject"], field="subject", maximum=255),
            question=self._content(data["question"], field="question", maximum=5000),
            status="OPEN",
            idempotency_key=key,
            payload_hash=payload_hash,
            lock_version=1,
            created_by=self.ctx.user_id,
        )
        self.audit.record(
            action="create_consultation",
            resource_type="ENGAGEMENT_POLICY",
            resource_id=row.id,
            park_id=park_id,
            detail={"consultation_id": consultation.id, "party_id": principal.party_id},
        )
        self._commit("政策咨询创建冲突", "POLICY_CONSULTATION_CONFLICT")
        return self._consultation_dict(consultation)

    @staticmethod
    def _consultation_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "case_no": row.case_no,
            "park_id": int(row.park_id),
            "policy_id": int(row.policy_id),
            "policy_version": int(row.policy_version),
            "party_id": int(row.party_id),
            "subject": row.subject,
            "question": row.question,
            "status": row.status,
            "lock_version": int(row.lock_version),
        }

    # Enterprise services ----------------------------------------------

    def _service_version_dict(self, row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            **self._version_base(row),
            "title": row.title,
            "description": row.description,
            "category": row.category,
            "provider": {
                "type": row.provider_type,
                "name": row.provider_name,
                "state": row.provider_state,
                "connected": row.provider_state == "LOCAL",
            },
            "sla_hours": int(row.sla_hours),
            "appointment_required": bool(row.appointment_required),
            "eligibility": row.eligibility_json,
            "evidence_rules": row.evidence_rules_json,
            "price": {
                "amount": str(row.price_amount) if row.price_amount is not None else None,
                "currency": row.currency,
                "payment_available": False,
            },
            "approval_id": row.approval_id,
        }

    def _catalog_dict(
        self, row, *, published_view: bool = False
    ) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        version_no = (
            row.published_version
            if published_view and row.published_version is not None
            else row.current_version
        )
        version = self.repo.service_version(row.id, version_no)
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "code": row.code,
            "status": row.status,
            "current_version": int(row.current_version),
            "published_version": row.published_version,
            "lock_version": int(row.lock_version),
            "version": self._service_version_dict(version) if version else None,
        }

    def list_services(self, *, tenant_view: bool = False) -> list[dict[str, Any]]:
        self._permission("engagement:read")
        principal = self._principal() if tenant_view else None
        return [
            self._catalog_dict(row, published_view=tenant_view)
            for row in self.repo.service_catalogs(published_only=tenant_view)
            if principal is None or int(row.park_id) in principal[1]
        ]

    def create_service(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("engagement:service_manage")
        park_id = self._park(data["park_id"])
        provider_type = normalize_code(data["provider_type"], field="provider_type")
        provider_state = normalize_code(data["provider_state"], field="provider_state")
        if provider_type == "EXTERNAL" and provider_state != "NOT_CONNECTED":
            raise AppError("外部服务商尚未连接", code="PROVIDER_NOT_CONNECTED", status_code=409)
        snapshot = {
            "title": clean_text(data["title"], field="title", maximum=255),
            "description": self._content(data["description"], field="description"),
            "category": normalize_code(data["category"], field="category"),
            "provider_type": provider_type,
            "provider_name": clean_text(data["provider_name"], field="provider_name", maximum=255),
            "provider_state": provider_state,
            "sla_hours": int(data["sla_hours"]),
            "appointment_required": bool(data.get("appointment_required", False)),
            "eligibility_json": normalize_rule_set(data.get("eligibility", [])),
            "evidence_rules_json": self._evidence(data.get("evidence_rules", [])) or [],
            "price_amount": data.get("price_amount"),
            "currency": str(data.get("currency") or "CNY").upper(),
        }
        row = self.repo.create(
            "service_catalog",
            park_id=park_id,
            code=normalize_code(data["code"]),
            status="DRAFT",
            current_version=1,
            lock_version=1,
            created_by=self.ctx.user_id or None,
        )
        self.repo.create(
            "service_version",
            catalog_id=row.id,
            version=1,
            status="DRAFT",
            checksum=canonical_hash(snapshot),
            created_by=self.ctx.user_id or None,
            **snapshot,
        )
        self.audit.record(
            action="create",
            resource_type="ENGAGEMENT_SERVICE",
            resource_id=row.id,
            park_id=park_id,
            detail={"code": row.code, "provider_state": provider_state},
        )
        self._commit("服务目录编码或引用冲突", "SERVICE_CATALOG_CONFLICT")
        return self._catalog_dict(row)

    def revise_service(
        self, catalog_id: int, data: dict[str, Any], *, key: str
    ) -> dict[str, Any]:
        self._permission("engagement:service_manage")
        row = self.repo.service_catalog(catalog_id, for_update=True)
        if row is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        event_key = f"service-revised:{row.id}:{self._key(key)}"
        request_fingerprint = canonical_hash(data)
        existing_event = self.repo.business_event_by_key(event_key)
        if existing_event is not None:
            previous = json.loads(existing_event.payload_json)
            if previous.get("request_fingerprint") != request_fingerprint:
                raise AppError(
                    "幂等键请求内容冲突", code="IDEMPOTENCY_CONFLICT", status_code=409
                )
            return self._catalog_dict(row)
        require_version(row.lock_version, data["expected_version"])
        if int(data["park_id"]) != int(row.park_id) or normalize_code(data["code"]) != row.code:
            raise AppError("服务标识或园区不可变", code="VALIDATION_ERROR", status_code=400)
        current = self.repo.service_version(row.id, row.current_version, for_update=True)
        if current is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        approval = self.repo.approval(row.approval_id)
        if row.status == "PENDING_APPROVAL" and approval is not None and approval.status == "PENDING":
            raise AppError("待审版本须先撤回审批", code="APPROVAL_PENDING", status_code=409)
        provider_type = normalize_code(data["provider_type"], field="provider_type")
        provider_state = normalize_code(data["provider_state"], field="provider_state")
        if provider_type == "EXTERNAL" and provider_state != "NOT_CONNECTED":
            raise AppError("外部服务商尚未连接", code="PROVIDER_NOT_CONNECTED", status_code=409)
        snapshot = {
            "title": clean_text(data["title"], field="title", maximum=255),
            "description": self._content(data["description"], field="description"),
            "category": normalize_code(data["category"], field="category"),
            "provider_type": provider_type,
            "provider_name": clean_text(
                data["provider_name"], field="provider_name", maximum=255
            ),
            "provider_state": provider_state,
            "sla_hours": int(data["sla_hours"]),
            "appointment_required": bool(data.get("appointment_required", False)),
            "eligibility_json": normalize_rule_set(data.get("eligibility", [])),
            "evidence_rules_json": self._evidence(data.get("evidence_rules", [])) or [],
            "price_amount": data.get("price_amount"),
            "currency": str(data.get("currency") or "CNY").upper(),
        }
        checksum = canonical_hash(snapshot)
        if current.status == "DRAFT" and row.published_version is None:
            version = current
            for field, value in snapshot.items():
                setattr(version, field, value)
            version.checksum = checksum
        else:
            if current.status != "PUBLISHED":
                current.status = "RETIRED"
                self.repo.save(current)
            row.current_version += 1
            version = self.repo.create(
                "service_version",
                catalog_id=row.id,
                version=row.current_version,
                status="DRAFT",
                checksum=checksum,
                created_by=self.ctx.user_id or None,
                **snapshot,
            )
        row.status = "DRAFT"
        row.approval_id = None
        row.lock_version += 1
        self.repo.save(row)
        self.repo.save(version)
        self.repo.create(
            "business_event",
            park_id=row.park_id,
            event_type="ENGAGEMENT_SERVICE_REVISED",
            source_type="ENGAGEMENT_SERVICE",
            source_id=str(row.id),
            idempotency_key=event_key,
            schema_version=1,
            payload_json=json.dumps(
                {
                    "catalog_id": int(row.id),
                    "version": int(version.version),
                    "checksum": checksum,
                    "request_fingerprint": request_fingerprint,
                },
                sort_keys=True,
            ),
            occurred_at=utc_now(),
        )
        self.audit.record(
            action="revise",
            resource_type="ENGAGEMENT_SERVICE",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"version": int(version.version), "checksum": checksum},
        )
        self._commit("服务目录修订冲突", "SERVICE_REVISION_CONFLICT")
        return self._catalog_dict(row)

    def submit_service(self, catalog_id: int, data: dict[str, Any], *, key: str) -> dict[str, Any]:
        self._permission("engagement:service_manage")
        row = self.repo.service_catalog(catalog_id, for_update=True)
        if row is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        version = self.repo.service_version(row.id, row.current_version, for_update=True)
        approval_key = self._approval_key("SERVICE", row.id, key)
        submit_fingerprint = canonical_hash(data)
        existing_approval = self.repo.approval(row.approval_id)
        if (
            row.status == "PENDING_APPROVAL"
            and version is not None
            and version.status == "SUBMITTED"
            and existing_approval is not None
            and existing_approval.idempotency_key == approval_key
        ):
            if (existing_approval.snapshot_json or {}).get("_submit_fingerprint") != submit_fingerprint:
                raise AppError(
                    "幂等键请求内容冲突", code="IDEMPOTENCY_CONFLICT", status_code=409
                )
            return self._catalog_dict(row)
        require_version(row.lock_version, data["expected_version"])
        if row.status != "DRAFT" or version is None or version.status != "DRAFT":
            raise AppError("服务目录状态不可提交", code="SERVICE_STATE_INVALID", status_code=409)
        approval = self.approvals.create(
            {
                "biz_type": "ENGAGEMENT_SERVICE",
                "biz_id": self._approval_biz_id(row.id, version),
                "title": f"企业服务发布：{version.title}",
                "park_id": row.park_id,
                "definition_code": self._definition(data["definition_code"]),
                "idempotency_key": approval_key,
                "priority": data.get("priority", "MEDIUM"),
                "snapshot": {
                    **self._service_version_dict(version),
                    "_submit_fingerprint": submit_fingerprint,
                },
            }
        )
        row.status = "PENDING_APPROVAL"
        row.approval_id = int(approval["id"])
        row.lock_version += 1
        version.status = "SUBMITTED"
        version.approval_id = int(approval["id"])
        self.repo.save(row)
        self.repo.save(version)
        self._commit("服务目录提交冲突", "SERVICE_SUBMIT_CONFLICT")
        return self._catalog_dict(row)

    def publish_service(self, catalog_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("engagement:service_manage")
        row = self.repo.service_catalog(catalog_id, for_update=True)
        if row is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        require_version(row.lock_version, data["expected_version"])
        version = self.repo.service_version(row.id, row.current_version, for_update=True)
        approval = self.repo.approval(row.approval_id)
        if version is None or version.status != "SUBMITTED" or approval is None:
            raise AppError("服务审批关联无效", code="SERVICE_APPROVAL_INVALID", status_code=409)
        if not self._approved_exact(
            approval,
            biz_type="ENGAGEMENT_SERVICE",
            aggregate_id=row.id,
            version=version,
        ):
            raise AppError("服务尚未审批通过", code="APPROVAL_NOT_APPROVED", status_code=409)
        row.status = "PUBLISHED"
        row.published_version = version.version
        row.lock_version += 1
        version.status = "PUBLISHED"
        version.published_at = utc_now()
        self.repo.save(row)
        self.repo.save(version)
        self.audit.record(
            action="publish",
            resource_type="ENGAGEMENT_SERVICE",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"version": version.version, "checksum": version.checksum},
        )
        self._commit("服务发布冲突", "SERVICE_PUBLISH_CONFLICT")
        return self._catalog_dict(row)

    def _case_dict(self, row, *, include_events: bool = False) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        result = {
            "id": int(row.id),
            "case_no": row.case_no,
            "park_id": int(row.park_id),
            "catalog_id": int(row.catalog_id),
            "service_version_id": int(row.service_version_id),
            "party_id": int(row.party_id),
            "status": row.status,
            "priority": row.priority,
            "subject": row.subject,
            "description": row.description,
            "contact_masked": row.contact_masked,
            "assigned_to": row.assigned_to,
            "work_order_id": row.work_order_id,
            "sla_due_at": row.sla_due_at.isoformat(),
            "appointment_at": row.appointment_at.isoformat() if row.appointment_at else None,
            "result_summary": row.result_summary,
            "lock_version": int(row.lock_version),
        }
        if include_events:
            result["events"] = [
                {
                    "id": int(item.id),
                    "event_type": item.event_type,
                    "note": item.note,
                    "evidence": item.evidence_json,
                    "occurred_at": item.occurred_at.isoformat(),
                }
                for item in self.repo.case_events(row.id)
            ]
        return result

    def list_cases(self, *, tenant_view: bool = False) -> list[dict[str, Any]]:
        self._permission("engagement:read")
        party_id = self._principal()[0].party_id if tenant_view else None
        return [
            self._case_dict(row, include_events=True)
            for row in self.repo.service_cases(party_id=party_id)
        ]

    def create_case(
        self, data: dict[str, Any], *, key: str, staff_on_behalf: bool = False
    ) -> dict[str, Any]:
        self._permission(
            "engagement:service_manage" if staff_on_behalf else "engagement:service_request"
        )
        key = self._key(key)
        payload_hash = canonical_hash(data)
        requested_party_id = (
            int(data["party_id"])
            if staff_on_behalf
            else int(self._principal()[0].party_id)
        )
        existing = self.repo.case_by_key(key)
        if existing is not None:
            if int(existing.party_id) != requested_party_id:
                raise AppError(
                    "幂等键已用于其他主体", code="IDEMPOTENCY_CONFLICT", status_code=409
                )
            if existing.payload_hash != payload_hash:
                raise AppError("幂等键请求内容冲突", code="IDEMPOTENCY_CONFLICT", status_code=409)
            return self._case_dict(existing, include_events=True)
        catalog = self.repo.service_catalog(int(data["catalog_id"]))
        if catalog is None or catalog.published_version is None or catalog.status == "RETIRED":
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        if staff_on_behalf:
            party_id = requested_party_id
            if self.repo.active_party(party_id) is None or not self.repo.party_has_park(
                party_id, int(catalog.park_id)
            ):
                raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
            principal_id = None
        else:
            principal, _ = self._principal(int(catalog.park_id))
            party_id = int(principal.party_id)
            principal_id = int(principal.id)
        version = self.repo.service_version(catalog.id, catalog.published_version)
        if version is None or version.status != "PUBLISHED":
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        eligible, _, unmet = evaluate_applicability(
            version.eligibility_json,
            self.repo.party_projection(party_id, int(catalog.park_id)),
        )
        if not eligible:
            raise AppError(
                "企业不满足本地服务条件",
                code="SERVICE_NOT_ELIGIBLE",
                status_code=409,
                data={"unmet_reasons": unmet, "official_eligibility": "NOT_APPLICABLE"},
            )
        contact_last4 = str(data.get("contact_last4") or "")
        contact_masked = f"***{contact_last4}" if contact_last4 else None
        row = self.repo.create(
            "service_case",
            park_id=catalog.park_id,
            catalog_id=catalog.id,
            service_version_id=version.id,
            party_id=party_id,
            principal_id=principal_id,
            case_no=self._number("SC", key),
            status="SUBMITTED",
            priority=str(data.get("priority") or "MEDIUM").upper(),
            subject=clean_text(data["subject"], field="subject", maximum=255),
            description=self._content(data["description"], field="description", maximum=10000),
            contact_masked=contact_masked,
            sla_due_at=utc_now() + timedelta(hours=int(version.sla_hours)),
            idempotency_key=key,
            payload_hash=payload_hash,
            lock_version=1,
            created_by=self.ctx.user_id,
        )
        self.repo.create(
            "service_case_event",
            case_id=row.id,
            event_type="SUBMITTED",
            note=None,
            evidence_json={"service_checksum": version.checksum},
            idempotency_key=f"case-submitted:{row.id}",
            actor_user_id=self.ctx.user_id,
            occurred_at=utc_now(),
        )
        self.audit.record(
            action="create_case",
            resource_type="ENGAGEMENT_SERVICE_CASE",
            resource_id=row.id,
            park_id=row.park_id,
            detail={
                "party_id": row.party_id,
                "service_version_id": row.service_version_id,
                "staff_on_behalf": staff_on_behalf,
            },
        )
        self._commit("服务申请创建冲突", "SERVICE_CASE_CONFLICT")
        return self._case_dict(row, include_events=True)

    def transition_case(
        self, case_id: int, data: dict[str, Any], *, key: str, tenant_view: bool = False
    ) -> dict[str, Any]:
        if tenant_view:
            self._permission("engagement:service_request")
            principal, _ = self._principal()
            party_id = principal.party_id
        else:
            self._permission("engagement:service_manage")
            party_id = None
        row = self.repo.service_case(case_id, for_update=True, party_id=party_id)
        if row is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        target = str(data["target_status"]).upper()
        event_key = f"case-transition:{row.id}:{self._key(key)}"
        request_fingerprint = canonical_hash(data)
        existing_event = self.repo.case_event_by_key(event_key)
        if existing_event is not None:
            expected_event_type = {
                "IN_PROGRESS": "PROGRESS",
                "RESULT_READY": "RESULT_READY",
                "CONFIRMED": "CONFIRMED",
            }.get(target, target)
            if existing_event.event_type != expected_event_type or (
                existing_event.evidence_json or {}
            ).get("request_fingerprint") != request_fingerprint:
                raise AppError(
                    "幂等键请求内容冲突", code="IDEMPOTENCY_CONFLICT", status_code=409
                )
            return self._case_dict(row, include_events=True)
        require_version(row.lock_version, data["expected_version"])
        if tenant_view and (row.status, target) not in {
            ("SUBMITTED", "CANCELLED"),
            ("RESULT_READY", "CONFIRMED"),
            ("RESULT_READY", "DISPUTED"),
        }:
            raise AppError("租户不可执行该状态变更", code="PERMISSION_DENIED", status_code=403)
        if tenant_view and any(
            data.get(field) is not None
            for field in (
                "assigned_to",
                "appointment_at",
                "result_summary",
                "work_order_id",
                "evidence",
            )
        ):
            raise AppError("租户不可写入工作人员字段", code="PERMISSION_DENIED", status_code=403)
        service_version = self.repo.service_version_by_id(row.service_version_id)
        if service_version is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        if target == "ASSIGNED" and data.get("assigned_to") is None and row.assigned_to is None:
            raise AppError("assigned_to 必填", code="VALIDATION_ERROR", status_code=400)
        if target == "APPOINTED" and data.get("appointment_at") is None:
            raise AppError("appointment_at 必填", code="VALIDATION_ERROR", status_code=400)
        if target == "RESULT_READY" and not data.get("result_summary"):
            raise AppError("result_summary 必填", code="VALIDATION_ERROR", status_code=400)
        if (
            target == "RESULT_READY"
            and service_version.evidence_rules_json
            and not data.get("evidence")
        ):
            raise AppError("结果证据必填", code="VALIDATION_ERROR", status_code=400)
        row.status = service_case_transition(row.status, target)
        row.lock_version += 1
        if data.get("assigned_to") is not None:
            assigned_to = int(data["assigned_to"])
            if self.repo.active_user(assigned_to) is None:
                raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
            row.assigned_to = assigned_to
        if data.get("appointment_at") is not None:
            row.appointment_at = data["appointment_at"]
        if data.get("result_summary") is not None:
            row.result_summary = self._content(
                data["result_summary"], field="result_summary", maximum=10000
            )
        if data.get("work_order_id") is not None:
            work_order_id = int(data["work_order_id"])
            if self.repo.work_order(work_order_id, row.park_id) is None:
                raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
            row.work_order_id = work_order_id
        self.repo.save(row)
        event_type = {
            "IN_PROGRESS": "PROGRESS",
            "RESULT_READY": "RESULT_READY",
            "CONFIRMED": "CONFIRMED",
        }.get(target, target)
        self.repo.create(
            "service_case_event",
            case_id=row.id,
            event_type=event_type,
            note=(
                clean_text(data["note"], field="note", maximum=1000)
                if data.get("note")
                else None
            ),
            evidence_json={
                "items": self._evidence(data.get("evidence")) or [],
                "request_fingerprint": request_fingerprint,
            },
            idempotency_key=event_key,
            actor_user_id=self.ctx.user_id,
            occurred_at=utc_now(),
        )
        self.audit.record(
            action="transition",
            resource_type="ENGAGEMENT_SERVICE_CASE",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"status": row.status, "party_id": row.party_id},
        )
        if data.get("work_order_id") is not None:
            self.repo.create(
                "service_case_event",
                case_id=row.id,
                event_type="WORK_ORDER_LINKED",
                note=None,
                evidence_json={"work_order_id": int(data["work_order_id"])},
                idempotency_key=f"case-work-order:{row.id}:{int(data['work_order_id'])}",
                actor_user_id=self.ctx.user_id,
                occurred_at=utc_now(),
            )
        self._commit("服务申请状态或工单关联冲突", "SERVICE_CASE_STATE_CONFLICT")
        return self._case_dict(row, include_events=True)

    def escalate_service_sla(self, *, due_at, limit: int) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        self._permission("engagement:service_manage")
        escalated = 0
        for row in self.repo.overdue_service_cases(due_at, limit):
            event_key = f"case-sla-escalated:{row.id}:{row.sla_due_at.isoformat()}"
            if self.repo.case_event_by_key(event_key) is not None:
                continue
            self.repo.create(
                "service_case_event",
                case_id=row.id,
                event_type="SLA_ESCALATED",
                note="SLA deadline reached before terminal state",
                evidence_json={
                    "sla_due_at": row.sla_due_at.isoformat(),
                    "observed_at": due_at.isoformat(),
                },
                idempotency_key=event_key,
                actor_user_id=self.ctx.user_id,
                occurred_at=utc_now(),
            )
            self.audit.record(
                action="sla_escalate",
                resource_type="ENGAGEMENT_SERVICE_CASE",
                resource_id=row.id,
                park_id=row.park_id,
                detail={"status": row.status, "sla_due_at": row.sla_due_at.isoformat()},
            )
            escalated += 1
        self._commit("服务 SLA 升级冲突", "SERVICE_SLA_CONFLICT")
        return {
            "escalated": escalated,
            "due_at": due_at.isoformat(),
            "external_provider_contacted": False,
            "production_contacted": False,
        }

    def feedback_case(self, case_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("engagement:service_request")
        principal, _ = self._principal()
        row = self.repo.service_case(case_id, party_id=principal.party_id)
        if row is None or row.status != "CONFIRMED":
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        existing = self.repo.service_feedback(row.id)
        if existing is not None:
            return {"id": int(existing.id), "score": int(existing.score)}
        feedback = self.repo.create(
            "service_feedback",
            case_id=row.id,
            party_id=principal.party_id,
            score=int(data["score"]),
            comment=(
                clean_text(data["comment"], field="comment", maximum=1000)
                if data.get("comment")
                else None
            ),
            submitted_at=utc_now(),
        )
        self._commit("服务评价冲突", "SERVICE_FEEDBACK_CONFLICT")
        return {"id": int(feedback.id), "case_id": int(row.id), "score": int(feedback.score)}

    # Park activities ---------------------------------------------------

    def _activity_version_dict(self, row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            **self._version_base(row),
            "title": row.title,
            "description": row.description,
            "location": row.location,
            "starts_at": row.starts_at.isoformat(),
            "ends_at": row.ends_at.isoformat(),
            "registration_opens_at": row.registration_opens_at.isoformat(),
            "registration_closes_at": row.registration_closes_at.isoformat(),
            "capacity": int(row.capacity),
            "confirmed_count": int(row.confirmed_count),
            "waitlist_count": int(row.waitlist_count),
            "attendee_rules": row.attendee_rules_json,
            "audience": row.audience_json,
            "attachments": row.attachments_json,
            "cancellation_terms": row.cancellation_terms,
            "approval_id": row.approval_id,
        }

    def _activity_dict(
        self, row, *, published_view: bool = False
    ) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        version_no = (
            row.published_version
            if published_view and row.published_version is not None
            else row.current_version
        )
        version = self.repo.activity_version(row.id, version_no)
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "code": row.code,
            "status": row.status,
            "current_version": int(row.current_version),
            "published_version": row.published_version,
            "lock_version": int(row.lock_version),
            "version": self._activity_version_dict(version) if version else None,
        }

    def list_activities(self, *, tenant_view: bool = False) -> list[dict[str, Any]]:
        self._permission("engagement:read")
        principal = self._principal() if tenant_view else None
        return [
            self._activity_dict(row, published_view=tenant_view)
            for row in self.repo.activities(published_only=tenant_view)
            if principal is None or int(row.park_id) in principal[1]
        ]

    def create_activity(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("engagement:activity_manage")
        park_id = self._park(data["park_id"])
        starts_at = data["starts_at"]
        ends_at = data["ends_at"]
        opens_at = data["registration_opens_at"]
        closes_at = data["registration_closes_at"]
        if not (opens_at <= closes_at <= starts_at < ends_at):
            raise AppError("活动或报名时间不正确", code="VALIDATION_ERROR", status_code=400)
        snapshot = {
            "title": clean_text(data["title"], field="title", maximum=255),
            "description": self._content(data["description"], field="description"),
            "location": clean_text(data["location"], field="location", maximum=255),
            "starts_at": starts_at,
            "ends_at": ends_at,
            "registration_opens_at": opens_at,
            "registration_closes_at": closes_at,
            "capacity": int(data["capacity"]),
            "confirmed_count": 0,
            "waitlist_count": 0,
            "attendee_rules_json": normalize_rule_set(data.get("attendee_rules", [])),
            "audience_json": normalize_rule_set(data.get("audience", [])),
            "attachments_json": self._attachments(data.get("attachment_ids", [])),
            "cancellation_terms": clean_text(
                data["cancellation_terms"], field="cancellation_terms", maximum=1000
            ),
        }
        row = self.repo.create(
            "activity",
            park_id=park_id,
            code=normalize_code(data["code"]),
            status="DRAFT",
            current_version=1,
            lock_version=1,
            created_by=self.ctx.user_id or None,
        )
        self.repo.create(
            "activity_version",
            activity_id=row.id,
            version=1,
            status="DRAFT",
            checksum=canonical_hash(snapshot),
            created_by=self.ctx.user_id or None,
            **snapshot,
        )
        self.audit.record(
            action="create",
            resource_type="ENGAGEMENT_ACTIVITY",
            resource_id=row.id,
            park_id=park_id,
            detail={"code": row.code, "capacity": snapshot["capacity"]},
        )
        self._commit("活动编码或引用冲突", "ACTIVITY_CONFLICT")
        return self._activity_dict(row)

    def revise_activity(
        self, activity_id: int, data: dict[str, Any], *, key: str
    ) -> dict[str, Any]:
        self._permission("engagement:activity_manage")
        row = self.repo.activity(activity_id, for_update=True)
        if row is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        event_key = f"activity-updated:{row.id}:{self._key(key)}"
        request_fingerprint = canonical_hash(data)
        existing_event = self.repo.activity_event_by_key(event_key)
        if existing_event is not None:
            if (existing_event.detail_json or {}).get(
                "request_fingerprint"
            ) != request_fingerprint:
                raise AppError(
                    "幂等键请求内容冲突", code="IDEMPOTENCY_CONFLICT", status_code=409
                )
            return self._activity_dict(row)
        require_version(row.lock_version, data["expected_version"])
        if int(data["park_id"]) != int(row.park_id) or normalize_code(data["code"]) != row.code:
            raise AppError("活动标识或园区不可变", code="VALIDATION_ERROR", status_code=400)
        current = self.repo.activity_version(row.id, row.current_version, for_update=True)
        if current is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        approval = self.repo.approval(row.approval_id)
        if row.status == "PENDING_APPROVAL" and approval is not None and approval.status == "PENDING":
            raise AppError("待审版本须先撤回审批", code="APPROVAL_PENDING", status_code=409)
        starts_at = data["starts_at"]
        ends_at = data["ends_at"]
        opens_at = data["registration_opens_at"]
        closes_at = data["registration_closes_at"]
        if not (opens_at <= closes_at <= starts_at < ends_at):
            raise AppError("活动或报名时间不正确", code="VALIDATION_ERROR", status_code=400)
        snapshot = {
            "title": clean_text(data["title"], field="title", maximum=255),
            "description": self._content(data["description"], field="description"),
            "location": clean_text(data["location"], field="location", maximum=255),
            "starts_at": starts_at,
            "ends_at": ends_at,
            "registration_opens_at": opens_at,
            "registration_closes_at": closes_at,
            "capacity": int(data["capacity"]),
            "confirmed_count": 0,
            "waitlist_count": 0,
            "attendee_rules_json": normalize_rule_set(data.get("attendee_rules", [])),
            "audience_json": normalize_rule_set(data.get("audience", [])),
            "attachments_json": self._attachments(data.get("attachment_ids", [])),
            "cancellation_terms": clean_text(
                data["cancellation_terms"], field="cancellation_terms", maximum=1000
            ),
        }
        checksum = canonical_hash(snapshot)
        if current.status == "DRAFT" and row.published_version is None:
            version = current
            for field, value in snapshot.items():
                setattr(version, field, value)
            version.checksum = checksum
        else:
            if current.status != "PUBLISHED":
                current.status = "RETIRED"
                self.repo.save(current)
            row.current_version += 1
            version = self.repo.create(
                "activity_version",
                activity_id=row.id,
                version=row.current_version,
                status="DRAFT",
                checksum=checksum,
                created_by=self.ctx.user_id or None,
                **snapshot,
            )
        row.status = "DRAFT"
        row.approval_id = None
        row.lock_version += 1
        self.repo.save(row)
        self.repo.save(version)
        self.repo.create(
            "activity_event",
            activity_id=row.id,
            registration_id=None,
            event_type="UPDATED",
            note=None,
            detail_json={"request_fingerprint": request_fingerprint},
            idempotency_key=event_key,
            actor_user_id=self.ctx.user_id,
            occurred_at=utc_now(),
        )
        self.audit.record(
            action="revise",
            resource_type="ENGAGEMENT_ACTIVITY",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"version": int(version.version), "checksum": checksum},
        )
        self._commit("活动修订冲突", "ACTIVITY_REVISION_CONFLICT")
        return self._activity_dict(row)

    def submit_activity(
        self, activity_id: int, data: dict[str, Any], *, key: str
    ) -> dict[str, Any]:
        self._permission("engagement:activity_manage")
        row = self.repo.activity(activity_id, for_update=True)
        if row is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        version = self.repo.activity_version(row.id, row.current_version, for_update=True)
        approval_key = self._approval_key("ACTIVITY", row.id, key)
        submit_fingerprint = canonical_hash(data)
        existing_approval = self.repo.approval(row.approval_id)
        if (
            row.status == "PENDING_APPROVAL"
            and version is not None
            and version.status == "SUBMITTED"
            and existing_approval is not None
            and existing_approval.idempotency_key == approval_key
        ):
            if (existing_approval.snapshot_json or {}).get("_submit_fingerprint") != submit_fingerprint:
                raise AppError(
                    "幂等键请求内容冲突", code="IDEMPOTENCY_CONFLICT", status_code=409
                )
            return self._activity_dict(row)
        require_version(row.lock_version, data["expected_version"])
        if row.status != "DRAFT" or version is None or version.status != "DRAFT":
            raise AppError("活动状态不可提交", code="ACTIVITY_STATE_INVALID", status_code=409)
        approval = self.approvals.create(
            {
                "biz_type": "ENGAGEMENT_ACTIVITY",
                "biz_id": self._approval_biz_id(row.id, version),
                "title": f"园区活动发布：{version.title}",
                "park_id": row.park_id,
                "definition_code": self._definition(data["definition_code"]),
                "idempotency_key": approval_key,
                "priority": data.get("priority", "MEDIUM"),
                "snapshot": {
                    **self._activity_version_dict(version),
                    "_submit_fingerprint": submit_fingerprint,
                },
            }
        )
        row.status = activity_transition(row.status, "PENDING_APPROVAL")
        row.approval_id = int(approval["id"])
        row.lock_version += 1
        version.status = "SUBMITTED"
        version.approval_id = int(approval["id"])
        self.repo.save(row)
        self.repo.save(version)
        self.repo.create(
            "activity_event",
            activity_id=row.id,
            registration_id=None,
            event_type="SUBMITTED",
            note=None,
            idempotency_key=f"activity-submitted:{row.id}:{version.version}",
            actor_user_id=self.ctx.user_id,
            occurred_at=utc_now(),
        )
        self._commit("活动提交冲突", "ACTIVITY_SUBMIT_CONFLICT")
        return self._activity_dict(row)

    def publish_activity(self, activity_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("engagement:activity_manage")
        row = self.repo.activity(activity_id, for_update=True)
        if row is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        require_version(row.lock_version, data["expected_version"])
        version = self.repo.activity_version(row.id, row.current_version, for_update=True)
        approval = self.repo.approval(row.approval_id)
        if version is None or version.status != "SUBMITTED" or approval is None:
            raise AppError("活动审批关联无效", code="ACTIVITY_APPROVAL_INVALID", status_code=409)
        if not self._approved_exact(
            approval,
            biz_type="ENGAGEMENT_ACTIVITY",
            aggregate_id=row.id,
            version=version,
        ):
            raise AppError("活动尚未审批通过", code="APPROVAL_NOT_APPROVED", status_code=409)
        row.status = activity_transition(activity_transition(row.status, "APPROVED"), "PUBLISHED")
        row.published_version = version.version
        row.lock_version += 1
        version.status = "PUBLISHED"
        version.published_at = utc_now()
        self.repo.save(row)
        self.repo.save(version)
        for event_type in ("APPROVED", "PUBLISHED"):
            self.repo.create(
                "activity_event",
                activity_id=row.id,
                registration_id=None,
                event_type=event_type,
                note=None,
                idempotency_key=f"activity-{event_type.lower()}:{row.id}:{version.version}",
                actor_user_id=self.ctx.user_id,
                occurred_at=utc_now(),
            )
        self.audit.record(
            action="publish",
            resource_type="ENGAGEMENT_ACTIVITY",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"version": version.version, "capacity": version.capacity},
        )
        self._commit("活动发布冲突", "ACTIVITY_PUBLISH_CONFLICT")
        return self._activity_dict(row)

    def transition_activity(
        self, activity_id: int, data: dict[str, Any], *, key: str
    ) -> dict[str, Any]:
        self._permission("engagement:activity_manage")
        row = self.repo.activity(activity_id, for_update=True)
        if row is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        target = str(data["target_status"]).upper()
        event_key = f"activity-lifecycle:{row.id}:{self._key(key)}"
        existing = self.repo.activity_event_by_key(event_key)
        if existing is not None:
            if existing.event_type != target or (existing.detail_json or {}).get(
                "request_fingerprint"
            ) != canonical_hash(data):
                raise AppError(
                    "幂等键请求内容冲突", code="IDEMPOTENCY_CONFLICT", status_code=409
                )
            return self._activity_dict(row)
        require_version(row.lock_version, data["expected_version"])
        row.status = activity_transition(row.status, target)
        row.lock_version += 1
        version = self.repo.activity_version(
            row.id, row.published_version or row.current_version, for_update=True
        )
        if version is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        if target == "CANCELLED":
            for registration in self.repo.registrations(
                activity_id=row.id, for_update=True
            ):
                if registration.status in {"CANCELLED", "CHECKED_IN"}:
                    continue
                registration.status = "CANCELLED"
                registration.cancelled_at = utc_now()
                registration.lock_version += 1
                self.repo.save(registration)
                cancellation_key = f"activity-cancelled-by-aggregate:{registration.id}"
                if self.repo.activity_event_by_key(cancellation_key) is None:
                    self.repo.create(
                        "activity_event",
                        activity_id=row.id,
                        registration_id=registration.id,
                        event_type="CANCELLED",
                        note=clean_text(data["reason"], field="reason", maximum=1000),
                        idempotency_key=cancellation_key,
                        actor_user_id=self.ctx.user_id,
                        occurred_at=utc_now(),
                    )
            version.confirmed_count = 0
            version.waitlist_count = 0
            if version.status != "DRAFT":
                version.status = "RETIRED"
            self.repo.save(version)
        self.repo.save(row)
        self.repo.create(
            "activity_event",
            activity_id=row.id,
            registration_id=None,
            event_type=target,
            note=clean_text(data["reason"], field="reason", maximum=1000),
            detail_json={"request_fingerprint": canonical_hash(data)},
            idempotency_key=event_key,
            actor_user_id=self.ctx.user_id,
            occurred_at=utc_now(),
        )
        self.audit.record(
            action="transition",
            resource_type="ENGAGEMENT_ACTIVITY",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"status": row.status, "version": int(version.version)},
        )
        self._commit("活动状态变更冲突", "ACTIVITY_STATE_CONFLICT")
        return self._activity_dict(row)

    @staticmethod
    def _registration_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "activity_id": int(row.activity_id),
            "activity_version_id": int(row.activity_version_id),
            "party_id": int(row.party_id),
            "status": row.status,
            "attendee_count": int(row.attendee_count),
            "waitlist_position": row.waitlist_position,
            "lock_version": int(row.lock_version),
            "cancelled_at": row.cancelled_at.isoformat() if row.cancelled_at else None,
            "checked_in_at": row.checked_in_at.isoformat() if row.checked_in_at else None,
        }

    def list_registrations(self, *, tenant_view: bool = False) -> list[dict[str, Any]]:
        self._permission("engagement:read")
        party_id = self._principal()[0].party_id if tenant_view else None
        return [self._registration_dict(row) for row in self.repo.registrations(party_id=party_id)]

    def register_activity(
        self, activity_id: int, data: dict[str, Any], *, key: str
    ) -> dict[str, Any]:
        self._permission("engagement:activity_register")
        key = self._key(key)
        payload_hash = canonical_hash(data)
        requested_principal, _ = self._principal()
        existing = self.repo.registration_by_key(key)
        if existing is not None:
            if int(existing.party_id) != int(requested_principal.party_id):
                raise AppError(
                    "幂等键已用于其他主体", code="IDEMPOTENCY_CONFLICT", status_code=409
                )
            if existing.payload_hash != payload_hash:
                raise AppError("幂等键请求内容冲突", code="IDEMPOTENCY_CONFLICT", status_code=409)
            return self._registration_dict(existing)
        activity = self.repo.activity(activity_id, for_update=True)
        if (
            activity is None
            or activity.published_version is None
            or activity.status in {"COMPLETED", "CANCELLED"}
        ):
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        principal, _ = self._principal(activity.park_id)
        version = self.repo.activity_version(
            activity.id, activity.published_version, for_update=True
        )
        now = utc_now()
        if version is None or not (
            version.status == "PUBLISHED"
            and version.registration_opens_at <= now <= version.registration_closes_at
        ):
            raise AppError("活动当前不可报名", code="ACTIVITY_REGISTRATION_CLOSED", status_code=409)
        projection = self.repo.party_projection(principal.party_id, int(activity.park_id))
        eligible, _, unmet = evaluate_applicability(
            [*version.audience_json, *version.attendee_rules_json], projection
        )
        if not eligible:
            raise AppError(
                "企业不满足活动报名条件",
                code="ACTIVITY_NOT_ELIGIBLE",
                status_code=409,
                data={"unmet_reasons": unmet},
            )
        attendee_count = int(data["attendee_count"])
        available = int(version.capacity) - int(version.confirmed_count)
        if attendee_count <= available:
            status = "CONFIRMED"
            waitlist_position = None
            version.confirmed_count += attendee_count
            event_type = "REGISTERED"
        else:
            status = "WAITLISTED"
            version.waitlist_count += 1
            waitlist_position = int(version.waitlist_count)
            event_type = "WAITLISTED"
        self.repo.save(version)
        registration = self.repo.create(
            "activity_registration",
            park_id=activity.park_id,
            activity_id=activity.id,
            activity_version_id=version.id,
            party_id=principal.party_id,
            principal_id=principal.id,
            status=status,
            attendee_count=attendee_count,
            waitlist_position=waitlist_position,
            idempotency_key=key,
            payload_hash=payload_hash,
            lock_version=1,
        )
        self.repo.create(
            "activity_event",
            activity_id=activity.id,
            registration_id=registration.id,
            event_type=event_type,
            note=None,
            idempotency_key=f"activity-registration:{registration.id}",
            actor_user_id=self.ctx.user_id,
            occurred_at=now,
        )
        self._commit("活动报名并发冲突", "ACTIVITY_REGISTRATION_CONFLICT")
        return self._registration_dict(registration)

    def cancel_registration(
        self, registration_id: int, data: dict[str, Any], *, key: str
    ) -> dict[str, Any]:
        self._permission("engagement:activity_register")
        principal, _ = self._principal()
        registration = self.repo.registration(
            registration_id, for_update=True, party_id=principal.party_id
        )
        if registration is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        event_key = f"activity-cancelled:{registration.id}:{self._key(key)}"
        existing_event = self.repo.activity_event_by_key(event_key)
        if existing_event is not None:
            if (existing_event.detail_json or {}).get(
                "request_fingerprint"
            ) != canonical_hash(data):
                raise AppError(
                    "幂等键请求内容冲突", code="IDEMPOTENCY_CONFLICT", status_code=409
                )
            return self._registration_dict(registration)
        require_version(registration.lock_version, data["expected_version"])
        if registration.status == "CANCELLED":
            return self._registration_dict(registration)
        if registration.status == "CHECKED_IN":
            raise AppError("已签到报名不可取消", code="ACTIVITY_STATE_INVALID", status_code=409)
        activity = self.repo.activity(registration.activity_id, for_update=True)
        version = self.repo.activity_version(
            registration.activity_id,
            activity.published_version if activity else 0,
            for_update=True,
        )
        if (
            activity is None
            or version is None
            or int(version.id) != int(registration.activity_version_id)
        ):
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        was_confirmed = registration.status == "CONFIRMED"
        registration.status = "CANCELLED"
        registration.cancelled_at = utc_now()
        registration.lock_version += 1
        self.repo.save(registration)
        promoted = None
        if was_confirmed:
            version.confirmed_count -= registration.attendee_count
            available = int(version.capacity) - int(version.confirmed_count)
            candidate = self.repo.next_waitlisted(
                version.id, maximum_attendees=available
            )
            if candidate is not None:
                candidate.status = "CONFIRMED"
                candidate.waitlist_position = None
                candidate.lock_version += 1
                version.confirmed_count += candidate.attendee_count
                version.waitlist_count -= 1
                self.repo.save(candidate)
                promoted = candidate
                self.repo.create(
                    "activity_event",
                    activity_id=activity.id,
                    registration_id=candidate.id,
                    event_type="PROMOTED",
                    note=None,
                    idempotency_key=f"activity-promoted:{candidate.id}:{self._key(key)}",
                    actor_user_id=self.ctx.user_id,
                    occurred_at=utc_now(),
                )
            self.repo.save(version)
        self.repo.create(
            "activity_event",
            activity_id=activity.id,
            registration_id=registration.id,
            event_type="CANCELLED",
            note=clean_text(data["reason"], field="reason", maximum=1000),
            detail_json={"request_fingerprint": canonical_hash(data)},
            idempotency_key=event_key,
            actor_user_id=self.ctx.user_id,
            occurred_at=utc_now(),
        )
        self._commit("活动取消或候补晋升冲突", "ACTIVITY_PROMOTION_CONFLICT")
        result = self._registration_dict(registration)
        result["promoted_registration_id"] = int(promoted.id) if promoted else None
        return result

    def check_in(self, registration_id: int, data: dict[str, Any], *, key: str) -> dict[str, Any]:
        self._permission("engagement:activity_manage")
        registration = self.repo.registration(registration_id, for_update=True)
        if registration is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        event_key = f"activity-checkin:{registration.id}:{self._key(key)}"
        existing_event = self.repo.activity_event_by_key(event_key)
        if existing_event is not None:
            if (existing_event.detail_json or {}).get(
                "request_fingerprint"
            ) != canonical_hash(data):
                raise AppError(
                    "幂等键请求内容冲突", code="IDEMPOTENCY_CONFLICT", status_code=409
                )
            return self._registration_dict(registration)
        require_version(registration.lock_version, data["expected_version"])
        if registration.status != "CONFIRMED":
            raise AppError("报名状态不可签到", code="ACTIVITY_STATE_INVALID", status_code=409)
        registration.status = "CHECKED_IN"
        registration.checked_in_at = utc_now()
        registration.lock_version += 1
        self.repo.save(registration)
        self.repo.create(
            "activity_event",
            activity_id=registration.activity_id,
            registration_id=registration.id,
            event_type="CHECKED_IN",
            note=clean_text(data["evidence_note"], field="evidence_note", maximum=1000),
            detail_json={"request_fingerprint": canonical_hash(data)},
            idempotency_key=event_key,
            actor_user_id=self.ctx.user_id,
            occurred_at=utc_now(),
        )
        self._commit("活动签到冲突", "ACTIVITY_CHECKIN_CONFLICT")
        return self._registration_dict(registration)

    def feedback_activity(self, registration_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("engagement:activity_register")
        principal, _ = self._principal()
        registration = self.repo.registration(registration_id, party_id=principal.party_id)
        if registration is None or registration.status != "CHECKED_IN":
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        existing = self.repo.activity_feedback(registration.id)
        if existing is not None:
            return {"id": int(existing.id), "score": int(existing.score)}
        feedback = self.repo.create(
            "activity_feedback",
            registration_id=registration.id,
            party_id=principal.party_id,
            score=int(data["score"]),
            comment=(
                clean_text(data["comment"], field="comment", maximum=1000)
                if data.get("comment")
                else None
            ),
            submitted_at=utc_now(),
        )
        self._commit("活动评价冲突", "ACTIVITY_FEEDBACK_CONFLICT")
        return {"id": int(feedback.id), "score": int(feedback.score)}

    # Announcements -----------------------------------------------------

    def _announcement_version_dict(self, row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            **self._version_base(row),
            "title": row.title,
            "content_text": row.content_text,
            "priority": row.priority,
            "pin_from": row.pin_from.isoformat() if row.pin_from else None,
            "pin_to": row.pin_to.isoformat() if row.pin_to else None,
            "publish_at": row.publish_at.isoformat(),
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "attachments": row.attachments_json,
            "audience": row.audience_json,
            "approval_id": row.approval_id,
        }

    def _announcement_dict(
        self, row, *, published_view: bool = False
    ) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        version_no = (
            row.published_version
            if published_view and row.published_version is not None
            else row.current_version
        )
        version = self.repo.announcement_version(row.id, version_no)
        return {
            "id": int(row.id),
            "park_id": int(row.park_id) if row.park_id is not None else None,
            "code": row.code,
            "status": row.status,
            "current_version": int(row.current_version),
            "published_version": row.published_version,
            "lock_version": int(row.lock_version),
            "version": self._announcement_version_dict(version) if version else None,
        }

    def list_announcements(self, *, tenant_view: bool = False) -> list[dict[str, Any]]:
        self._permission("engagement:read")
        principal = self._principal() if tenant_view else None
        now = utc_now()
        result: list[dict[str, Any]] = []
        for row in self.repo.announcements(published_only=tenant_view):
            if (
                principal is not None
                and row.park_id is not None
                and int(row.park_id) not in principal[1]
            ):
                continue
            version = self.repo.announcement_version(
                row.id, row.published_version or row.current_version
            )
            if tenant_view and (
                version is None
                or version.publish_at > now
                or (version.expires_at and version.expires_at <= now)
            ):
                continue
            result.append(self._announcement_dict(row, published_view=tenant_view))
        return result

    @staticmethod
    def _audience(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list) or not value or len(value) > 32:
            raise AppError(
                "audience 必须是 1 至 32 条规则", code="VALIDATION_ERROR", status_code=400
            )
        result: list[dict[str, Any]] = []
        allowed = {"USER", "ROLE", "PARTY", "PARK", "TENANT_PRINCIPAL"}
        for raw in value:
            if not isinstance(raw, dict) or set(raw) - {"type", "ids", "codes"}:
                raise AppError("audience 规则字段不正确", code="VALIDATION_ERROR", status_code=400)
            source_type = str(raw.get("type") or "").upper()
            if source_type not in allowed:
                raise AppError("audience 类型不受支持", code="VALIDATION_ERROR", status_code=400)
            ids = sorted({int(item) for item in raw.get("ids", [])})
            codes = sorted(
                {normalize_code(item, field="role_code") for item in raw.get("codes", [])}
            )
            if source_type == "ROLE" and not codes:
                raise AppError("ROLE audience 需要 codes", code="VALIDATION_ERROR", status_code=400)
            if source_type in {"USER", "PARTY", "PARK"} and not ids:
                raise AppError(
                    f"{source_type} audience 需要 ids", code="VALIDATION_ERROR", status_code=400
                )
            result.append({"type": source_type, "ids": ids, "codes": codes})
        return result

    def create_announcement(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("engagement:announcement_manage")
        park_id = self._park(data["park_id"]) if data.get("park_id") is not None else None
        publish_at = data.get("publish_at") or utc_now()
        expires_at = data.get("expires_at")
        pin_from = data.get("pin_from")
        pin_to = data.get("pin_to")
        if expires_at is not None and expires_at <= publish_at:
            raise AppError("公告有效期不正确", code="VALIDATION_ERROR", status_code=400)
        if (pin_from is None) != (pin_to is None) or (
            pin_from is not None and pin_to is not None and pin_to <= pin_from
        ):
            raise AppError("公告置顶时间不正确", code="VALIDATION_ERROR", status_code=400)
        snapshot = {
            "title": clean_text(data["title"], field="title", maximum=255),
            "content_text": self._content(data["content_text"], field="content_text"),
            "priority": str(data.get("priority") or "NORMAL").upper(),
            "pin_from": pin_from,
            "pin_to": pin_to,
            "publish_at": publish_at,
            "expires_at": expires_at,
            "attachments_json": self._attachments(data.get("attachment_ids", [])),
            "audience_json": self._audience(data["audience"]),
        }
        for rule in snapshot["audience_json"]:
            if rule["type"] == "USER" and any(
                self.repo.active_user(value) is None for value in rule["ids"]
            ):
                raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
            if rule["type"] == "ROLE" and any(
                self.repo.active_role(value) is None for value in rule["codes"]
            ):
                raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
            if rule["type"] == "PARTY":
                for value in rule["ids"]:
                    if self.repo.active_party(value) is None or (
                        park_id is not None and not self.repo.party_has_park(value, park_id)
                    ):
                        raise AppError(
                            "资源不存在", code="RESOURCE_NOT_FOUND", status_code=404
                        )
            if rule["type"] == "PARK" and any(
                self.repo.park(value) is None for value in rule["ids"]
            ):
                raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        row = self.repo.create(
            "announcement",
            park_id=park_id,
            code=normalize_code(data["code"]),
            status="DRAFT",
            current_version=1,
            lock_version=1,
            created_by=self.ctx.user_id or None,
        )
        self.repo.create(
            "announcement_version",
            announcement_id=row.id,
            version=1,
            status="DRAFT",
            checksum=canonical_hash(snapshot),
            created_by=self.ctx.user_id or None,
            **snapshot,
        )
        self.audit.record(
            action="create",
            resource_type="ENGAGEMENT_ANNOUNCEMENT",
            resource_id=row.id,
            park_id=park_id,
            detail={"code": row.code, "audience_rules": len(snapshot["audience_json"])},
        )
        self._commit("公告编码或引用冲突", "ANNOUNCEMENT_CONFLICT")
        return self._announcement_dict(row)

    def revise_announcement(
        self, announcement_id: int, data: dict[str, Any], *, key: str
    ) -> dict[str, Any]:
        self._permission("engagement:announcement_manage")
        row = self.repo.announcement(announcement_id, for_update=True)
        if row is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        event_key = f"announcement-revised:{row.id}:{self._key(key)}"
        request_fingerprint = canonical_hash(data)
        existing_event = self.repo.business_event_by_key(event_key)
        if existing_event is not None:
            previous = json.loads(existing_event.payload_json)
            if previous.get("request_fingerprint") != request_fingerprint:
                raise AppError(
                    "幂等键请求内容冲突", code="IDEMPOTENCY_CONFLICT", status_code=409
                )
            return self._announcement_dict(row)
        require_version(row.lock_version, data["expected_version"])
        supplied_park = int(data["park_id"]) if data.get("park_id") is not None else None
        if supplied_park != row.park_id or normalize_code(data["code"]) != row.code:
            raise AppError("公告标识或园区不可变", code="VALIDATION_ERROR", status_code=400)
        current = self.repo.announcement_version(
            row.id, row.current_version, for_update=True
        )
        if current is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        approval = self.repo.approval(row.approval_id)
        if row.status == "PENDING_APPROVAL" and approval is not None and approval.status == "PENDING":
            raise AppError("待审版本须先撤回审批", code="APPROVAL_PENDING", status_code=409)
        publish_at = data.get("publish_at") or utc_now()
        expires_at = data.get("expires_at")
        pin_from = data.get("pin_from")
        pin_to = data.get("pin_to")
        if expires_at is not None and expires_at <= publish_at:
            raise AppError("公告有效期不正确", code="VALIDATION_ERROR", status_code=400)
        if (pin_from is None) != (pin_to is None) or (
            pin_from is not None and pin_to is not None and pin_to <= pin_from
        ):
            raise AppError("公告置顶时间不正确", code="VALIDATION_ERROR", status_code=400)
        audience = self._audience(data["audience"])
        for rule in audience:
            if rule["type"] == "USER" and any(
                self.repo.active_user(value) is None for value in rule["ids"]
            ):
                raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
            if rule["type"] == "ROLE" and any(
                self.repo.active_role(value) is None for value in rule["codes"]
            ):
                raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
            if rule["type"] == "PARTY":
                for value in rule["ids"]:
                    if self.repo.active_party(value) is None or (
                        row.park_id is not None
                        and not self.repo.party_has_park(value, int(row.park_id))
                    ):
                        raise AppError(
                            "资源不存在", code="RESOURCE_NOT_FOUND", status_code=404
                        )
            if rule["type"] == "PARK" and any(
                self.repo.park(value) is None for value in rule["ids"]
            ):
                raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        snapshot = {
            "title": clean_text(data["title"], field="title", maximum=255),
            "content_text": self._content(data["content_text"], field="content_text"),
            "priority": str(data.get("priority") or "NORMAL").upper(),
            "pin_from": pin_from,
            "pin_to": pin_to,
            "publish_at": publish_at,
            "expires_at": expires_at,
            "attachments_json": self._attachments(data.get("attachment_ids", [])),
            "audience_json": audience,
        }
        checksum = canonical_hash(snapshot)
        if current.status == "DRAFT" and row.published_version is None:
            version = current
            for field, value in snapshot.items():
                setattr(version, field, value)
            version.checksum = checksum
        else:
            if current.status != "PUBLISHED":
                current.status = "RETIRED"
                self.repo.save(current)
            row.current_version += 1
            version = self.repo.create(
                "announcement_version",
                announcement_id=row.id,
                version=row.current_version,
                status="DRAFT",
                checksum=checksum,
                created_by=self.ctx.user_id or None,
                **snapshot,
            )
        row.status = "DRAFT"
        row.approval_id = None
        row.lock_version += 1
        self.repo.save(row)
        self.repo.save(version)
        self.repo.create(
            "business_event",
            park_id=row.park_id,
            event_type="ENGAGEMENT_ANNOUNCEMENT_REVISED",
            source_type="ENGAGEMENT_ANNOUNCEMENT",
            source_id=str(row.id),
            idempotency_key=event_key,
            schema_version=1,
            payload_json=json.dumps(
                {
                    "announcement_id": int(row.id),
                    "version": int(version.version),
                    "checksum": checksum,
                    "request_fingerprint": request_fingerprint,
                },
                sort_keys=True,
            ),
            occurred_at=utc_now(),
        )
        self.audit.record(
            action="revise",
            resource_type="ENGAGEMENT_ANNOUNCEMENT",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"version": int(version.version), "checksum": checksum},
        )
        self._commit("公告修订冲突", "ANNOUNCEMENT_REVISION_CONFLICT")
        return self._announcement_dict(row)

    def submit_announcement(
        self, announcement_id: int, data: dict[str, Any], *, key: str
    ) -> dict[str, Any]:
        self._permission("engagement:announcement_manage")
        row = self.repo.announcement(announcement_id, for_update=True)
        if row is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        version = self.repo.announcement_version(row.id, row.current_version, for_update=True)
        approval_key = self._approval_key("ANNOUNCEMENT", row.id, key)
        submit_fingerprint = canonical_hash(data)
        existing_approval = self.repo.approval(row.approval_id)
        if (
            row.status == "PENDING_APPROVAL"
            and version is not None
            and version.status == "SUBMITTED"
            and existing_approval is not None
            and existing_approval.idempotency_key == approval_key
        ):
            if (existing_approval.snapshot_json or {}).get("_submit_fingerprint") != submit_fingerprint:
                raise AppError(
                    "幂等键请求内容冲突", code="IDEMPOTENCY_CONFLICT", status_code=409
                )
            return self._announcement_dict(row)
        require_version(row.lock_version, data["expected_version"])
        if row.status != "DRAFT" or version is None or version.status != "DRAFT":
            raise AppError("公告状态不可提交", code="ANNOUNCEMENT_STATE_INVALID", status_code=409)
        approval = self.approvals.create(
            {
                "biz_type": "ENGAGEMENT_ANNOUNCEMENT",
                "biz_id": self._approval_biz_id(row.id, version),
                "title": f"公告发布：{version.title}",
                "park_id": row.park_id,
                "definition_code": self._definition(data["definition_code"]),
                "idempotency_key": approval_key,
                "priority": data.get("priority", "MEDIUM"),
                "snapshot": {
                    **self._announcement_version_dict(version),
                    "_submit_fingerprint": submit_fingerprint,
                },
            }
        )
        row.status = announcement_transition(row.status, "PENDING_APPROVAL")
        row.approval_id = int(approval["id"])
        row.lock_version += 1
        version.status = "SUBMITTED"
        version.approval_id = int(approval["id"])
        self.repo.save(row)
        self.repo.save(version)
        self._commit("公告提交冲突", "ANNOUNCEMENT_SUBMIT_CONFLICT")
        return self._announcement_dict(row)

    def _freeze_announcement_audience(self, row, version) -> int:  # type: ignore[no-untyped-def]
        existing_targets = self.repo.announcement_targets(version.id)
        if existing_targets:
            return len(existing_targets)
        event_key = f"announcement-published:{row.id}:{version.version}:{version.checksum}"
        event = self.repo.business_event_by_key(event_key)
        if event is None:
            event = self.repo.create(
                "business_event",
                park_id=row.park_id,
                event_type="ENGAGEMENT_ANNOUNCEMENT_PUBLISHED",
                source_type="ENGAGEMENT_ANNOUNCEMENT",
                source_id=str(row.id),
                idempotency_key=event_key,
                schema_version=1,
                payload_json=json.dumps(
                    {
                        "announcement_id": int(row.id),
                        "version_id": int(version.id),
                        "checksum": version.checksum,
                    },
                    sort_keys=True,
                ),
                occurred_at=utc_now(),
            )
        candidates = self.repo.recipient_candidates(version.audience_json)
        for user_id, snapshot in sorted(candidates.items()):
            target = self.repo.create(
                "announcement_target",
                announcement_id=row.id,
                announcement_version_id=version.id,
                park_id=snapshot["park_id"] or row.park_id,
                party_id=snapshot["party_id"],
                recipient_user_id=user_id,
                source_type=snapshot["source_type"],
                source_key=snapshot["source_key"],
                audience_snapshot_json=snapshot,
                status="TARGETED",
            )
            self.repo.create(
                "announcement_delivery",
                target_id=target.id,
                event_id=event.id,
                notification_id=None,
                idempotency_key=f"engagement-announcement:{version.id}:{user_id}",
                channel="IN_APP",
                status="PENDING",
                attempt_count=0,
            )
        return len(candidates)

    def publish_announcement(self, announcement_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("engagement:announcement_manage")
        row = self.repo.announcement(announcement_id, for_update=True)
        if row is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        require_version(row.lock_version, data["expected_version"])
        version = self.repo.announcement_version(row.id, row.current_version, for_update=True)
        approval = self.repo.approval(row.approval_id)
        if version is None or version.status != "SUBMITTED" or approval is None:
            raise AppError(
                "公告审批关联无效", code="ANNOUNCEMENT_APPROVAL_INVALID", status_code=409
            )
        if not self._approved_exact(
            approval,
            biz_type="ENGAGEMENT_ANNOUNCEMENT",
            aggregate_id=row.id,
            version=version,
        ):
            raise AppError("公告尚未审批通过", code="APPROVAL_NOT_APPROVED", status_code=409)
        now = utc_now()
        target_status = "SCHEDULED" if version.publish_at > now else "PUBLISHED"
        row.status = announcement_transition(
            announcement_transition(row.status, "APPROVED"), target_status
        )
        if target_status == "PUBLISHED":
            row.published_version = version.version
        row.lock_version += 1
        version.status = target_status
        version.published_at = now if target_status == "PUBLISHED" else None
        self.repo.save(row)
        self.repo.save(version)
        frozen_recipient_count = (
            self._freeze_announcement_audience(row, version)
            if target_status == "PUBLISHED"
            else 0
        )
        self.audit.record(
            action="publish" if target_status == "PUBLISHED" else "schedule",
            resource_type="ENGAGEMENT_ANNOUNCEMENT",
            resource_id=row.id,
            park_id=row.park_id,
            detail={
                "version": version.version,
                "checksum": version.checksum,
                "frozen_recipients": frozen_recipient_count,
                "external_delivery": False,
            },
        )
        self._commit("公告发布或受众冻结冲突", "ANNOUNCEMENT_PUBLISH_CONFLICT")
        result = self._announcement_dict(row)
        result["frozen_recipient_count"] = frozen_recipient_count
        result["delivery_state"] = (
            "PENDING_IN_APP" if target_status == "PUBLISHED" else "SCHEDULED"
        )
        return result

    def process_due_announcements(self, *, due_at, limit: int) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        self._permission("engagement:announcement_manage")
        published = expired = 0
        for row in self.repo.due_announcements(due_at, limit):
            version = self.repo.announcement_version(
                row.id, row.published_version or row.current_version, for_update=True
            )
            if version is None:
                continue
            row.status = announcement_transition(row.status, "PUBLISHED")
            row.published_version = version.version
            row.lock_version += 1
            version.status = "PUBLISHED"
            version.published_at = due_at
            self.repo.save(row)
            self.repo.save(version)
            self._freeze_announcement_audience(row, version)
            published += 1
        for row in self.repo.expirable_announcements(due_at, limit):
            version = self.repo.announcement_version(
                row.id, row.published_version or 0, for_update=True
            )
            if version is None:
                continue
            row.status = announcement_transition(row.status, "EXPIRED")
            row.lock_version += 1
            version.status = "RETIRED"
            self.repo.save(row)
            self.repo.save(version)
            event_key = f"announcement-expired:{row.id}:{version.version}"
            if self.repo.business_event_by_key(event_key) is None:
                self.repo.create(
                    "business_event",
                    park_id=row.park_id,
                    event_type="ENGAGEMENT_ANNOUNCEMENT_EXPIRED",
                    source_type="ENGAGEMENT_ANNOUNCEMENT",
                    source_id=str(row.id),
                    idempotency_key=event_key,
                    schema_version=1,
                    payload_json=json.dumps(
                        {"announcement_id": int(row.id), "checksum": version.checksum},
                        sort_keys=True,
                    ),
                    occurred_at=due_at,
                )
            expired += 1
        self._commit("公告定时处理冲突", "ANNOUNCEMENT_SCHEDULE_CONFLICT")
        return {
            "published": published,
            "expired": expired,
            "due_at": due_at.isoformat(),
            "production_contacted": False,
        }

    def withdraw_announcement(
        self, announcement_id: int, data: dict[str, Any], *, key: str
    ) -> dict[str, Any]:
        self._permission("engagement:announcement_manage")
        row = self.repo.announcement(announcement_id, for_update=True)
        if row is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        event_key = f"announcement-withdrawn:{row.id}:{self._key(key)}"
        if self.repo.business_event_by_key(event_key) is not None:
            return self._announcement_dict(row)
        require_version(row.lock_version, data["expected_version"])
        row.status = announcement_transition(row.status, "WITHDRAWN")
        row.lock_version += 1
        version = self.repo.announcement_version(
            row.id, row.published_version or row.current_version, for_update=True
        )
        if version is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        if version.status != "DRAFT":
            version.status = "RETIRED"
            self.repo.save(version)
        self.repo.save(row)
        self.repo.create(
            "business_event",
            park_id=row.park_id,
            event_type="ENGAGEMENT_ANNOUNCEMENT_WITHDRAWN",
            source_type="ENGAGEMENT_ANNOUNCEMENT",
            source_id=str(row.id),
            idempotency_key=event_key,
            schema_version=1,
            payload_json=json.dumps(
                {
                    "announcement_id": int(row.id),
                    "checksum": version.checksum,
                    "reason": clean_text(data["reason"], field="reason", maximum=1000),
                },
                sort_keys=True,
            ),
            occurred_at=utc_now(),
        )
        self.audit.record(
            action="withdraw",
            resource_type="ENGAGEMENT_ANNOUNCEMENT",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"version": int(version.version), "checksum": version.checksum},
        )
        self._commit("公告撤回冲突", "ANNOUNCEMENT_WITHDRAW_CONFLICT")
        return self._announcement_dict(row)

    def fanout_announcements(self, *, limit: int) -> dict[str, Any]:
        self._permission("engagement:announcement_manage")
        delivered = failed = 0
        for delivery in self.repo.pending_deliveries(limit):
            target = self.repo.target(delivery.target_id)
            if target is None:
                delivery.status = "FAILED"
                delivery.last_error = "TARGET_MISSING"
                delivery.attempt_count += 1
                self.repo.save(delivery)
                failed += 1
                continue
            announcement = self.repo.announcement(target.announcement_id)
            if (
                announcement is None
                or announcement.published_version is None
                or announcement.status in {"EXPIRED", "WITHDRAWN"}
            ):
                delivery.status = "SKIPPED"
                delivery.last_error = "ANNOUNCEMENT_NOT_PUBLISHED"
                delivery.attempt_count += 1
                target.status = "SKIPPED"
                self.repo.save(delivery)
                self.repo.save(target)
                failed += 1
                continue
            version = self.repo.announcement_version(
                target.announcement_id,
                announcement.published_version or 0,
            )
            if version is None:
                delivery.status = "FAILED"
                delivery.last_error = "VERSION_MISSING"
                delivery.attempt_count += 1
                self.repo.save(delivery)
                failed += 1
                continue
            notification = self.repo.notification_by_key(delivery.idempotency_key)
            if notification is None:
                notification = self.repo.create(
                    "notification",
                    park_id=target.park_id,
                    recipient_user_id=target.recipient_user_id,
                    event_id=delivery.event_id,
                    idempotency_key=delivery.idempotency_key,
                    category="ENGAGEMENT_ANNOUNCEMENT",
                    channel="IN_APP",
                    title=version.title,
                    content=version.content_text[:4000],
                    deep_link=f"/engagement/announcements/{target.announcement_id}",
                    status="UNREAD",
                    delivered_at=utc_now(),
                )
            delivery.notification_id = notification.id
            delivery.status = "DELIVERED"
            delivery.attempt_count += 1
            delivery.last_error = None
            delivery.delivered_at = utc_now()
            target.status = "DELIVERED"
            self.repo.save(delivery)
            self.repo.save(target)
            delivered += 1
        self._commit("公告站内信分发冲突", "ANNOUNCEMENT_FANOUT_CONFLICT")
        return {
            "delivered": delivered,
            "failed": failed,
            "channel": "IN_APP",
            "external_delivery": "NOT_CONNECTED",
            "production_contacted": False,
        }

    def inbox(self) -> list[dict[str, Any]]:
        self._permission("engagement:read")
        self._principal()
        return [
            {
                "delivery_id": int(delivery.id),
                "announcement_id": int(announcement.id),
                "version": int(version.version),
                "title": version.title,
                "content_text": version.content_text,
                "priority": version.priority,
                "status": delivery.status,
                "delivered_at": (
                    delivery.delivered_at.isoformat() if delivery.delivered_at else None
                ),
                "read_at": delivery.read_at.isoformat() if delivery.read_at else None,
                "audience_snapshot": target.audience_snapshot_json,
            }
            for delivery, target, version, announcement in self.repo.inbox(self.ctx.user_id)
        ]

    def read_delivery(self, delivery_id: int) -> dict[str, Any]:
        self._permission("engagement:read")
        self._principal()
        pair = self.repo.delivery_for_user(delivery_id, self.ctx.user_id, for_update=True)
        if pair is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        delivery, target = pair
        if delivery.status not in {"DELIVERED", "READ"}:
            raise AppError("公告尚未送达", code="ANNOUNCEMENT_NOT_DELIVERED", status_code=409)
        now = utc_now()
        delivery.status = "READ"
        delivery.read_at = delivery.read_at or now
        target.status = "READ"
        notification = self.repo.notification_by_key(delivery.idempotency_key)
        if notification is not None:
            notification.status = "READ"
            notification.read_at = notification.read_at or now
            self.repo.save(notification)
        self.repo.save(delivery)
        self.repo.save(target)
        self._commit("公告已读状态冲突", "ANNOUNCEMENT_READ_CONFLICT")
        return {
            "delivery_id": int(delivery.id),
            "status": delivery.status,
            "read_at": now.isoformat(),
        }

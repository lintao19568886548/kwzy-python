"""Application services for event-driven workbench automation."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.modules.park_property.infrastructure.park_repository import ParkRepository
from app.modules.workbench.application.summary_service import WorkbenchSummaryService
from app.modules.workbench.application.work_item_service import WorkItemService
from app.modules.workbench.domain.registry import (
    DEFAULT_WIDGETS,
    REGISTERED_ACTIONS,
    REGISTERED_COMPARATORS,
    REGISTERED_CONSUMERS,
    REGISTERED_EVENTS,
    REGISTERED_HANDLERS,
    WIDGET_REGISTRY,
    is_safe_deep_link,
)
from app.modules.workbench.infrastructure.automation_repository import AutomationRepository
from app.shared.tenant_context import TenantContext

_TEMPLATE = re.compile(r"\$\{payload\.([a-zA-Z][a-zA-Z0-9_]*)\}")
_BLOCKED_KEYS = frozenset(
    {"password", "secret", "token", "api_key", "access_key", "private_key", "phone", "id_card"}
)
_MAX_JSON_BYTES = 16 * 1024
_MAX_ERROR = 500
_NOTIFICATION_STATUSES = frozenset({"UNREAD", "READ", "ARCHIVED"})


def _json_dump(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(text.encode("utf-8")) > _MAX_JSON_BYTES:
        raise AppError("JSON 内容超过 16KB 限制", code="PAYLOAD_TOO_LARGE", status_code=413)
    return text


def _json_load(value: Optional[str], fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _reject_sensitive(value: Any, *, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in _BLOCKED_KEYS:
                raise AppError(
                    f"{path}.{key} 不允许保存敏感字段",
                    code="SENSITIVE_FIELD_BLOCKED",
                    status_code=400,
                )
            _reject_sensitive(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_sensitive(child, path=f"{path}[{index}]")


class WorkbenchAutomationService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.repo = AutomationRepository(session, ctx)
        self.parks = ParkRepository(session, ctx)
        self.work_items = WorkItemService(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def _require(self, permission: str) -> None:
        if not self.ctx.has_permission(permission):
            raise AppError("无操作权限", code="PERMISSION_DENIED", status_code=403)

    def _assert_park(self, park_id: Optional[int]) -> Optional[int]:
        if park_id is None:
            return None
        value = int(park_id)
        if not self.parks.exists_in_tenant(value):
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        if not self.ctx.allows_park(value):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        return value

    @staticmethod
    def _dt(value: Any, *, default: Optional[datetime] = None) -> Optional[datetime]:
        if value is None or value == "":
            return default
        if isinstance(value, datetime):
            return value.replace(tzinfo=None) if value.tzinfo else value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError as exc:
            raise AppError("时间格式无效", code="VALIDATION_ERROR", status_code=400) from exc

    # Event outbox ---------------------------------------------------------

    def _event_dict(
        self,
        row,
        *,
        include_consumers: bool = True,
        consumers: Optional[Sequence[Any]] = None,
    ) -> dict[str, Any]:
        data = {
            "id": int(row.id),
            "tenant_id": int(row.tenant_id),
            "park_id": int(row.park_id) if row.park_id is not None else None,
            "event_type": row.event_type,
            "source_type": row.source_type,
            "source_id": row.source_id,
            "idempotency_key": row.idempotency_key,
            "schema_version": int(row.schema_version),
            "payload": _json_load(row.payload_json, {}),
            "occurred_at": row.occurred_at.isoformat(),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        if include_consumers:
            selected = consumers if consumers is not None else self.repo.consumers_for_event(row.id)
            data["consumers"] = [self._consumer_dict(item) for item in selected]
        return data

    @staticmethod
    def _consumer_dict(row) -> dict[str, Any]:
        return {
            "id": int(row.id),
            "event_id": int(row.event_id),
            "consumer_name": row.consumer_name,
            "generation": int(row.generation),
            "status": row.status,
            "attempt_count": int(row.attempt_count),
            "max_attempts": int(row.max_attempts),
            "next_attempt_at": row.next_attempt_at.isoformat() if row.next_attempt_at else None,
            "claimed_by": row.claimed_by,
            "last_error": row.last_error,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        }

    def emit_event(
        self,
        *,
        event_type: str,
        source_type: str,
        source_id: str,
        idempotency_key: str,
        payload: dict[str, Any],
        park_id: Optional[int] = None,
        schema_version: int = 1,
        commit: bool = True,
        enforce_permission: bool = True,
    ) -> dict[str, Any]:
        if enforce_permission:
            self._require("event.emit")
        event_type = str(event_type).strip().upper()
        if event_type not in REGISTERED_EVENTS:
            raise AppError("未注册事件类型", code="EVENT_TYPE_NOT_REGISTERED", status_code=400)
        if event_type == "TEST_AUTOMATION_EVENT" and enforce_permission:
            self._require("automation.rule.write")
        source_type = str(source_type).strip().upper()
        source_id = str(source_id).strip()
        idempotency_key = str(idempotency_key).strip()
        if not source_type or not source_id or len(idempotency_key) < 8:
            raise AppError("事件来源或幂等键无效", code="VALIDATION_ERROR", status_code=400)
        allowed_fields = REGISTERED_EVENTS[event_type]
        unknown = sorted(set(payload) - allowed_fields)
        if unknown:
            raise AppError(
                f"事件载荷包含未注册字段: {', '.join(unknown)}",
                code="EVENT_PAYLOAD_FIELD_NOT_REGISTERED",
                status_code=400,
            )
        _reject_sensitive(payload)
        park_id = self._assert_park(park_id)
        if payload.get("park_id") is not None and int(payload["park_id"]) != int(park_id or 0):
            raise AppError("载荷园区与事件园区不一致", code="PARK_MISMATCH", status_code=400)
        existing = self.repo.event_by_key(idempotency_key)
        if existing is not None:
            if (
                existing.event_type != event_type
                or existing.source_type != source_type
                or existing.source_id != source_id
            ):
                raise AppError("幂等键已用于其他事件", code="IDEMPOTENCY_CONFLICT", status_code=409)
            return self._event_dict(existing)
        try:
            row = self.repo.create_event(
                park_id=park_id,
                event_type=event_type,
                source_type=source_type,
                source_id=source_id,
                idempotency_key=idempotency_key,
                schema_version=int(schema_version),
                payload_json=_json_dump(payload),
                occurred_at=utc_now(),
                consumers=sorted(REGISTERED_CONSUMERS),
                max_attempts=3,
            )
            if commit:
                self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            existing = self.repo.event_by_key(idempotency_key)
            if existing is None:
                raise AppError("事件幂等冲突", code="IDEMPOTENCY_CONFLICT", status_code=409) from exc
            return self._event_dict(existing)
        return self._event_dict(row)

    def list_events(
        self,
        *,
        page: int,
        page_size: int,
        event_type: Optional[str],
        park_id: Optional[int],
    ) -> dict[str, Any]:
        self._require("event.read")
        if park_id is not None:
            self._assert_park(park_id)
        total, rows = self.repo.list_events(
            offset=(page - 1) * page_size,
            limit=page_size,
            event_type=event_type.upper() if event_type else None,
            park_id=park_id,
        )
        consumers = self.repo.consumers_for_events([int(row.id) for row in rows])
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [self._event_dict(row, consumers=consumers.get(int(row.id), [])) for row in rows],
        }

    def dispatch(
        self,
        *,
        limit: int = 100,
        worker_id: Optional[str] = None,
        commit: bool = True,
        enforce_permission: bool = True,
    ) -> dict[str, Any]:
        if enforce_permission:
            self._require("event.dispatch")
        worker = str(worker_id or f"worker-{uuid.uuid4().hex[:12]}")[:96]
        rows = self.repo.claim_consumers(
            consumer_name="WORKBENCH_AUTOMATION",
            worker_id=worker,
            limit=min(max(int(limit), 1), 500),
            now=utc_now(),
        )
        succeeded = retried = dead = 0
        results: list[dict[str, Any]] = []
        for row in rows:
            try:
                with self.session.begin_nested():
                    event = self.repo.event_by_id(row.event_id)
                    if event is None:
                        raise AppError("事件不存在或不可见", code="EVENT_NOT_FOUND", status_code=404)
                    detail = self._consume_automation_event(event)
                row.status = "SUCCEEDED"
                row.completed_at = utc_now()
                row.last_error = None
                succeeded += 1
                results.append({"consumer_id": int(row.id), "status": row.status, "detail": detail})
            except Exception as exc:  # failure becomes durable retry/dead evidence
                message = str(exc).replace("\n", " ")[:_MAX_ERROR]
                row.last_error = message
                row.claimed_at = None
                row.claimed_by = None
                if int(row.attempt_count) >= int(row.max_attempts):
                    row.status = "DEAD"
                    row.completed_at = utc_now()
                    dead += 1
                else:
                    row.status = "RETRY"
                    delay_seconds = min(300, 2 ** max(int(row.attempt_count), 1))
                    row.next_attempt_at = utc_now() + timedelta(seconds=delay_seconds)
                    retried += 1
                results.append({"consumer_id": int(row.id), "status": row.status, "error": message})
            self.session.add(row)
        if rows and enforce_permission:
            self.audit.record(
                action="dispatch",
                resource_type="BUSINESS_EVENT",
                resource_id=None,
                detail={"claimed": len(rows), "succeeded": succeeded, "retry": retried, "dead": dead},
            )
        if commit:
            self.session.commit()
        return {
            "worker_id": worker,
            "claimed": len(rows),
            "succeeded": succeeded,
            "retry": retried,
            "dead": dead,
            "results": results,
        }

    def replay_consumer(self, consumer_id: int, *, reason: str) -> dict[str, Any]:
        self._require("event.replay")
        row = self.repo.consumer_by_id(consumer_id, for_update=True)
        if row is None:
            raise AppError("消费记录不存在", code="EVENT_CONSUMER_NOT_FOUND", status_code=404)
        if row.status != "DEAD":
            raise AppError("仅 DEAD 记录可重放", code="EVENT_REPLAY_STATUS_INVALID", status_code=409)
        generation = self.repo.next_consumer_generation(row)
        replay = self.repo.add_consumer_generation(row, generation)
        self.audit.record(
            action="replay",
            resource_type="EVENT_CONSUMER",
            resource_id=row.id,
            detail={"reason": str(reason)[:200], "new_generation": generation},
        )
        self.session.commit()
        return self._consumer_dict(replay)

    # Rules ---------------------------------------------------------------

    def _validate_rule_document(
        self,
        *,
        event_type: str,
        conditions: Sequence[dict[str, Any]],
        actions: Sequence[dict[str, Any]],
    ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
        event_type = str(event_type).strip().upper()
        allowed_fields = REGISTERED_EVENTS.get(event_type)
        if allowed_fields is None:
            raise AppError("未注册事件类型", code="EVENT_TYPE_NOT_REGISTERED", status_code=400)
        normalized_conditions: list[dict[str, Any]] = []
        for raw in conditions:
            if set(raw) != {"field", "operator", "value"}:
                raise AppError("规则条件字段无效", code="RULE_GRAMMAR_INVALID", status_code=400)
            field = str(raw["field"]).strip()
            operator = str(raw["operator"]).strip().upper()
            value = raw["value"]
            if field not in allowed_fields or operator not in REGISTERED_COMPARATORS:
                raise AppError("规则字段或比较符未注册", code="RULE_GRAMMAR_INVALID", status_code=400)
            if isinstance(value, (dict, list)) and operator != "IN":
                raise AppError("比较值必须为标量", code="RULE_GRAMMAR_INVALID", status_code=400)
            if operator == "IN" and (not isinstance(value, list) or len(value) > 50):
                raise AppError("IN 必须使用不超过 50 项的数组", code="RULE_GRAMMAR_INVALID", status_code=400)
            _reject_sensitive(value, path=f"condition.{field}")
            normalized_conditions.append({"field": field, "operator": operator, "value": value})
        if not actions:
            raise AppError("规则至少包含一个动作", code="RULE_ACTION_REQUIRED", status_code=400)
        normalized_actions: list[dict[str, Any]] = []
        allowed_action_fields = {
            "CREATE_WORK_ITEM": {
                "type",
                "title",
                "description",
                "item_type",
                "priority",
                "assignee_user_id",
                "due_at",
                "deep_link",
            },
            "CREATE_NOTIFICATION": {
                "type",
                "title",
                "content",
                "recipient_user_id",
                "category",
                "deep_link",
            },
        }
        for raw in actions:
            action_type = str(raw.get("type") or "").strip().upper()
            if action_type not in REGISTERED_ACTIONS:
                raise AppError("规则动作未注册", code="RULE_ACTION_NOT_REGISTERED", status_code=400)
            unknown = set(raw) - allowed_action_fields[action_type]
            if unknown:
                raise AppError("规则动作字段无效", code="RULE_GRAMMAR_INVALID", status_code=400)
            required = {"title"}
            if action_type == "CREATE_NOTIFICATION":
                required |= {"content", "recipient_user_id"}
            if any(raw.get(field) in (None, "") for field in required):
                raise AppError("规则动作缺少必填字段", code="RULE_ACTION_INVALID", status_code=400)
            for value in raw.values():
                if isinstance(value, str):
                    for field in _TEMPLATE.findall(value):
                        if field not in allowed_fields:
                            raise AppError("模板引用未注册字段", code="RULE_TEMPLATE_INVALID", status_code=400)
                    lowered = value.lower()
                    if "http://" in lowered or "https://" in lowered or "javascript:" in lowered:
                        raise AppError("规则动作禁止 URL 或脚本", code="RULE_UNSAFE_CONTENT", status_code=400)
            _reject_sensitive(raw, path="action")
            normalized_actions.append({**raw, "type": action_type})
        _json_dump(normalized_conditions)
        _json_dump(normalized_actions)
        return event_type, normalized_conditions, normalized_actions

    @staticmethod
    def _rule_dict(row, versions: Sequence[Any]) -> dict[str, Any]:
        return {
            "id": int(row.id),
            "park_id": int(row.park_id) if row.park_id is not None else None,
            "code": row.code,
            "name": row.name,
            "description": row.description,
            "status": row.status,
            "current_version": int(row.current_version),
            "lock_version": int(row.lock_version),
            "versions": [
                {
                    "id": int(version.id),
                    "version": int(version.version),
                    "status": version.status,
                    "event_type": version.event_type,
                    "priority": int(version.priority),
                    "conditions": _json_load(version.conditions_json, []),
                    "actions": _json_load(version.actions_json, []),
                    "published_at": version.published_at.isoformat() if version.published_at else None,
                }
                for version in versions
            ],
        }

    def list_rules(self) -> list[dict[str, Any]]:
        self._require("automation.rule.read")
        return [self._rule_dict(row, self.repo.rule_versions(row.id)) for row in self.repo.list_rules()]

    def create_rule(self, data: dict[str, Any]) -> dict[str, Any]:
        self._require("automation.rule.write")
        code = str(data["code"]).strip().upper()
        if self.repo.rule_by_code(code) is not None:
            raise AppError("规则编码已存在", code="RULE_CODE_CONFLICT", status_code=409)
        park_id = self._assert_park(data.get("park_id"))
        event_type, conditions, actions = self._validate_rule_document(
            event_type=data["event_type"], conditions=data.get("conditions") or [], actions=data["actions"]
        )
        try:
            row = self.repo.create_rule(
                park_id=park_id,
                code=code,
                name=str(data["name"]).strip(),
                description=data.get("description"),
                status="ACTIVE",
                current_version=0,
                lock_version=1,
                created_by=self.ctx.user_id,
                updated_by=self.ctx.user_id,
            )
            self.repo.add_rule_version(
                rule_id=row.id,
                version=1,
                status="DRAFT",
                event_type=event_type,
                priority=int(data.get("priority") or 100),
                conditions_json=_json_dump(conditions),
                actions_json=_json_dump(actions),
                created_by=self.ctx.user_id,
            )
            self.audit.record(
                action="create",
                resource_type="AUTOMATION_RULE",
                resource_id=row.id,
                park_id=park_id,
                detail={"code": code},
            )
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError("规则编码冲突", code="RULE_CODE_CONFLICT", status_code=409) from exc
        return self._rule_dict(row, self.repo.rule_versions(row.id))

    def update_rule_draft(self, rule_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._require("automation.rule.write")
        row = self.repo.rule_by_id(rule_id, for_update=True)
        if row is None:
            raise AppError("规则不存在", code="RULE_NOT_FOUND", status_code=404)
        if int(row.lock_version) != int(data["expected_version"]):
            raise AppError(
                "规则版本冲突",
                code="RULE_VERSION_CONFLICT",
                status_code=409,
                data={"current_version": int(row.lock_version)},
            )
        draft = self.repo.draft_for_rule(row.id)
        if draft is None:
            raise AppError("规则没有可编辑草稿", code="RULE_DRAFT_NOT_FOUND", status_code=409)
        event_type = str(data.get("event_type") or draft.event_type)
        conditions = data.get("conditions")
        if conditions is None:
            conditions = _json_load(draft.conditions_json, [])
        actions = data.get("actions")
        if actions is None:
            actions = _json_load(draft.actions_json, [])
        event_type, conditions, actions = self._validate_rule_document(
            event_type=event_type, conditions=conditions, actions=actions
        )
        if "name" in data:
            row.name = str(data["name"]).strip()
        if "description" in data:
            row.description = data["description"]
        if "park_id" in data:
            row.park_id = self._assert_park(data.get("park_id"))
        draft.event_type = event_type
        draft.conditions_json = _json_dump(conditions)
        draft.actions_json = _json_dump(actions)
        if data.get("priority") is not None:
            draft.priority = int(data["priority"])
        row.lock_version = int(row.lock_version) + 1
        row.updated_by = self.ctx.user_id
        self.session.add_all([row, draft])
        self.audit.record(
            action="update_draft",
            resource_type="AUTOMATION_RULE",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"draft_version": int(draft.version)},
        )
        self.session.commit()
        return self._rule_dict(row, self.repo.rule_versions(row.id))

    def publish_rule(self, rule_id: int, *, expected_version: int) -> dict[str, Any]:
        self._require("automation.rule.write")
        row = self.repo.rule_by_id(rule_id, for_update=True)
        if row is None:
            raise AppError("规则不存在", code="RULE_NOT_FOUND", status_code=404)
        if int(row.lock_version) != int(expected_version):
            raise AppError(
                "规则版本冲突",
                code="RULE_VERSION_CONFLICT",
                status_code=409,
                data={"current_version": int(row.lock_version)},
            )
        draft = self.repo.draft_for_rule(row.id)
        if draft is None:
            raise AppError("规则没有可发布草稿", code="RULE_DRAFT_NOT_FOUND", status_code=409)
        self._validate_rule_document(
            event_type=draft.event_type,
            conditions=_json_load(draft.conditions_json, []),
            actions=_json_load(draft.actions_json, []),
        )
        for version in self.repo.rule_versions(row.id):
            if version.status == "PUBLISHED":
                version.status = "RETIRED"
                self.session.add(version)
        draft.status = "PUBLISHED"
        draft.published_by = self.ctx.user_id
        draft.published_at = utc_now()
        row.current_version = int(draft.version)
        row.lock_version = int(row.lock_version) + 1
        self.session.add_all([row, draft])
        self.audit.record(
            action="publish",
            resource_type="AUTOMATION_RULE",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"version": int(draft.version)},
        )
        self.session.commit()
        return self._rule_dict(row, self.repo.rule_versions(row.id))

    def create_rule_draft(self, rule_id: int, *, expected_version: int) -> dict[str, Any]:
        self._require("automation.rule.write")
        row = self.repo.rule_by_id(rule_id, for_update=True)
        if row is None:
            raise AppError("规则不存在", code="RULE_NOT_FOUND", status_code=404)
        if int(row.lock_version) != int(expected_version):
            raise AppError("规则版本冲突", code="RULE_VERSION_CONFLICT", status_code=409)
        if self.repo.draft_for_rule(row.id) is not None:
            raise AppError("已存在草稿", code="RULE_DRAFT_EXISTS", status_code=409)
        versions = self.repo.rule_versions(row.id)
        source = next((item for item in versions if item.status == "PUBLISHED"), None)
        if source is None:
            raise AppError("没有已发布版本可复制", code="RULE_PUBLISHED_NOT_FOUND", status_code=409)
        next_version = max(int(item.version) for item in versions) + 1
        self.repo.add_rule_version(
            rule_id=row.id,
            version=next_version,
            status="DRAFT",
            event_type=source.event_type,
            priority=source.priority,
            conditions_json=source.conditions_json,
            actions_json=source.actions_json,
            created_by=self.ctx.user_id,
        )
        row.lock_version = int(row.lock_version) + 1
        self.session.add(row)
        self.session.commit()
        return self._rule_dict(row, self.repo.rule_versions(row.id))

    def retire_rule(self, rule_id: int, *, expected_version: int) -> dict[str, Any]:
        self._require("automation.rule.write")
        row = self.repo.rule_by_id(rule_id, for_update=True)
        if row is None:
            raise AppError("规则不存在", code="RULE_NOT_FOUND", status_code=404)
        if int(row.lock_version) != int(expected_version):
            raise AppError("规则版本冲突", code="RULE_VERSION_CONFLICT", status_code=409)
        row.status = "RETIRED"
        row.lock_version = int(row.lock_version) + 1
        for version in self.repo.rule_versions(row.id):
            if version.status == "PUBLISHED":
                version.status = "RETIRED"
                self.session.add(version)
        self.session.add(row)
        self.audit.record(
            action="retire",
            resource_type="AUTOMATION_RULE",
            resource_id=row.id,
            park_id=row.park_id,
            detail={},
        )
        self.session.commit()
        return self._rule_dict(row, self.repo.rule_versions(row.id))

    @staticmethod
    def _compare(actual: Any, operator: str, expected: Any) -> bool:
        if operator == "EQ":
            return actual == expected
        if operator == "NE":
            return actual != expected
        if operator == "IN":
            return actual in expected
        try:
            left = Decimal(str(actual))
            right = Decimal(str(expected))
        except (InvalidOperation, TypeError, ValueError):
            left = str(actual)
            right = str(expected)
        if operator == "GT":
            return left > right
        if operator == "GTE":
            return left >= right
        if operator == "LT":
            return left < right
        if operator == "LTE":
            return left <= right
        return False

    @staticmethod
    def _render(value: Any, payload: dict[str, Any], *, max_length: int) -> Any:
        if not isinstance(value, str):
            return value

        def replace(match: re.Match[str]) -> str:
            raw = payload.get(match.group(1), "")
            if isinstance(raw, (dict, list)):
                return ""
            return str(raw)

        rendered = _TEMPLATE.sub(replace, value).strip()
        return rendered[:max_length]

    def _consume_automation_event(self, event) -> dict[str, Any]:
        payload = _json_load(event.payload_json, {})
        matched_count = action_count = 0
        for version in self.repo.matching_versions(event_type=event.event_type, park_id=event.park_id):
            existing = self.repo.execution_for(event_id=event.id, version_id=version.id)
            if existing is not None and existing.status in {"SUCCEEDED", "NOT_MATCHED"}:
                continue
            conditions = _json_load(version.conditions_json, [])
            matched = all(
                self._compare(payload.get(item["field"]), item["operator"], item["value"])
                for item in conditions
            )
            execution = existing or self.repo.add_execution(
                event_id=event.id,
                rule_version_id=version.id,
                status="MATCHED" if matched else "NOT_MATCHED",
                matched=matched,
                completed_at=utc_now() if not matched else None,
            )
            if not matched:
                continue
            matched_count += 1
            action_results: list[dict[str, Any]] = []
            try:
                for index, action in enumerate(_json_load(version.actions_json, [])):
                    if action["type"] == "CREATE_WORK_ITEM":
                        title = self._render(action["title"], payload, max_length=255)
                        deep_link = self._render(action.get("deep_link"), payload, max_length=512)
                        if not is_safe_deep_link(deep_link):
                            raise AppError("渲染后的 deep_link 无效", code="RULE_ACTION_INVALID")
                        assignee = self._render(action.get("assignee_user_id"), payload, max_length=32)
                        result = self.work_items.ensure_from_source(
                            source_type="EVENT_RULE",
                            source_id=f"{event.id}:{version.id}:{index}",
                            item_type=str(action.get("item_type") or "AUTOMATION")[:64],
                            title=str(title),
                            description=self._render(action.get("description"), payload, max_length=2000),
                            park_id=int(event.park_id) if event.park_id is not None else None,
                            priority=str(self._render(action.get("priority") or "MEDIUM", payload, max_length=16)),
                            assignee_user_id=int(assignee) if assignee not in (None, "") else None,
                            due_at=self._render(action.get("due_at"), payload, max_length=64),
                            deep_link=deep_link,
                            last_event_id=int(event.id),
                            commit=False,
                        )
                        action_results.append({"type": action["type"], "id": result["id"]})
                    else:
                        recipient = self._render(action["recipient_user_id"], payload, max_length=32)
                        notification = self._deliver_notification(
                            recipient_user_id=int(recipient),
                            park_id=int(event.park_id) if event.park_id is not None else None,
                            event_id=int(event.id),
                            idempotency_key=f"rule:{event.id}:{version.id}:{index}",
                            category=str(self._render(action.get("category") or "AUTOMATION", payload, max_length=64)),
                            title=str(self._render(action["title"], payload, max_length=255)),
                            content=str(self._render(action["content"], payload, max_length=2000)),
                            deep_link=self._render(action.get("deep_link"), payload, max_length=512),
                        )
                        action_results.append({"type": action["type"], "id": notification["id"]})
                    action_count += 1
                execution.status = "SUCCEEDED"
                execution.action_results_json = _json_dump(action_results)
                execution.completed_at = utc_now()
            except Exception as exc:
                execution.status = "FAILED"
                execution.error_message = str(exc).replace("\n", " ")[:_MAX_ERROR]
                execution.completed_at = utc_now()
                self.session.add(execution)
                raise
            self.session.add(execution)
        return {"matched_rules": matched_count, "actions": action_count}

    def list_executions(self) -> list[dict[str, Any]]:
        self._require("automation.rule.read")
        return [
            {
                "id": int(row.id),
                "event_id": int(row.event_id),
                "rule_version_id": int(row.rule_version_id),
                "status": row.status,
                "matched": bool(row.matched),
                "action_results": _json_load(row.action_results_json, []),
                "error_message": row.error_message,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            }
            for row in self.repo.list_executions()
        ]

    # Notifications -------------------------------------------------------

    @staticmethod
    def _notification_dict(row) -> dict[str, Any]:
        return {
            "id": int(row.id),
            "park_id": int(row.park_id) if row.park_id is not None else None,
            "recipient_user_id": int(row.recipient_user_id),
            "event_id": int(row.event_id) if row.event_id is not None else None,
            "category": row.category,
            "channel": row.channel,
            "title": row.title,
            "content": row.content,
            "deep_link": row.deep_link,
            "status": row.status,
            "delivered_at": row.delivered_at.isoformat(),
            "read_at": row.read_at.isoformat() if row.read_at else None,
            "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        }

    def _deliver_notification(
        self,
        *,
        recipient_user_id: int,
        park_id: Optional[int],
        event_id: Optional[int],
        idempotency_key: str,
        category: str,
        title: str,
        content: str,
        deep_link: Optional[str],
    ) -> dict[str, Any]:
        if not self.repo.user_exists(recipient_user_id):
            raise AppError("通知接收人不存在", code="RECIPIENT_NOT_FOUND", status_code=400)
        if not title or len(title) > 255 or len(content) > 4000:
            raise AppError("通知内容无效", code="NOTIFICATION_INVALID", status_code=400)
        if not is_safe_deep_link(deep_link):
            raise AppError("通知 deep_link 无效", code="NOTIFICATION_INVALID", status_code=400)
        existing = self.repo.notification_by_key(idempotency_key)
        if existing is not None:
            return self._notification_dict(existing)
        row = self.repo.add_notification(
            park_id=park_id,
            recipient_user_id=int(recipient_user_id),
            event_id=event_id,
            idempotency_key=idempotency_key,
            category=category[:64],
            channel="IN_APP",
            title=title,
            content=content,
            deep_link=deep_link,
            status="UNREAD",
            delivered_at=utc_now(),
        )
        return self._notification_dict(row)

    def list_notifications(self, *, page: int, page_size: int, status: Optional[str]) -> dict[str, Any]:
        self._require("notification.read")
        normalized = status.upper() if status else None
        if normalized and normalized not in _NOTIFICATION_STATUSES:
            raise AppError("通知状态无效", code="VALIDATION_ERROR", status_code=400)
        total, unread_count, rows = self.repo.list_notifications(
            offset=(page - 1) * page_size, limit=page_size, status=normalized
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "unread_count": unread_count,
            "items": [self._notification_dict(row) for row in rows],
        }

    def mark_notification(self, notification_id: int, *, archive: bool = False) -> dict[str, Any]:
        self._require("notification.write")
        row = self.repo.notification_by_id(notification_id, for_update=True)
        if row is None:
            raise AppError("通知不存在", code="NOTIFICATION_NOT_FOUND", status_code=404)
        now = utc_now()
        if archive:
            row.status = "ARCHIVED"
            row.archived_at = row.archived_at or now
        elif row.status == "UNREAD":
            row.status = "READ"
            row.read_at = row.read_at or now
        self.session.add(row)
        self.session.commit()
        return self._notification_dict(row)

    def bulk_read(self, ids: Sequence[int]) -> dict[str, Any]:
        self._require("notification.write")
        unique_ids = sorted({int(value) for value in ids})
        if len(unique_ids) != len(ids) or not unique_ids or len(unique_ids) > 100:
            raise AppError("通知 id 列表无效", code="VALIDATION_ERROR", status_code=400)
        rows = self.repo.notifications_by_ids(unique_ids, for_update=True)
        if len(rows) != len(unique_ids):
            raise AppError("通知不存在", code="NOTIFICATION_NOT_FOUND", status_code=404)
        now = utc_now()
        changed = 0
        for row in rows:
            if row.status == "UNREAD":
                row.status = "READ"
                row.read_at = now
                changed += 1
                self.session.add(row)
        self.session.commit()
        return {"requested": len(unique_ids), "changed": changed, "unread_count": self.repo.unread_count()}

    # Scheduler -----------------------------------------------------------

    def _validate_schedule_parameters(self, handler_key: str, parameters: dict[str, Any]) -> None:
        if handler_key not in REGISTERED_HANDLERS:
            raise AppError("调度处理器未注册", code="SCHEDULER_HANDLER_NOT_REGISTERED", status_code=400)
        _reject_sensitive(parameters, path="parameters")
        allowed = {
            "OUTBOX_DISPATCH": {"limit"},
            "LEASE_TODO_SYNC": {"within_days"},
            "APPROVAL_OVERDUE_SWEEP": {"limit"},
        }[handler_key]
        if set(parameters) - allowed:
            raise AppError("调度参数字段无效", code="SCHEDULER_PARAMETERS_INVALID", status_code=400)
        _json_dump(parameters)

    @staticmethod
    def _schedule_dict(row) -> dict[str, Any]:
        return {
            "id": int(row.id),
            "code": row.code,
            "name": row.name,
            "handler_key": row.handler_key,
            "parameters": _json_load(row.parameters_json, {}),
            "cadence_seconds": int(row.cadence_seconds),
            "enabled": bool(row.enabled),
            "concurrency_policy": row.concurrency_policy,
            "next_run_at": row.next_run_at.isoformat() if row.next_run_at else None,
            "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
            "timeout_seconds": int(row.timeout_seconds),
            "max_attempts": int(row.max_attempts),
            "lock_version": int(row.lock_version),
        }

    @staticmethod
    def _run_dict(row) -> dict[str, Any]:
        return {
            "id": int(row.id),
            "schedule_id": int(row.schedule_id),
            "fire_at": row.fire_at.isoformat(),
            "generation": int(row.generation),
            "idempotency_key": row.idempotency_key,
            "status": row.status,
            "claimed_by": row.claimed_by,
            "attempt_no": int(row.attempt_no),
            "started_at": row.started_at.isoformat(),
            "heartbeat_at": row.heartbeat_at.isoformat(),
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "result": _json_load(row.result_json, None),
            "error_message": row.error_message,
        }

    def list_schedules(self) -> list[dict[str, Any]]:
        self._require("scheduler.read")
        return [self._schedule_dict(row) for row in self.repo.list_schedules()]

    def create_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        self._require("scheduler.write")
        code = str(data["code"]).strip().upper()
        handler = str(data["handler_key"]).strip().upper()
        params = data.get("parameters") or {}
        self._validate_schedule_parameters(handler, params)
        if self.repo.schedule_by_code(code) is not None:
            raise AppError("调度编码已存在", code="SCHEDULER_CODE_CONFLICT", status_code=409)
        next_run = self._dt(data.get("next_run_at"))
        if data.get("enabled") and next_run is None:
            next_run = utc_now()
        row = self.repo.add_schedule(
            code=code,
            name=str(data["name"]).strip(),
            handler_key=handler,
            parameters_json=_json_dump(params),
            cadence_seconds=int(data["cadence_seconds"]),
            enabled=bool(data.get("enabled")),
            concurrency_policy=str(data.get("concurrency_policy") or "FORBID"),
            next_run_at=next_run,
            timeout_seconds=int(data.get("timeout_seconds") or 300),
            max_attempts=int(data.get("max_attempts") or 3),
            lock_version=1,
            created_by=self.ctx.user_id,
            updated_by=self.ctx.user_id,
        )
        self.audit.record(
            action="create", resource_type="SCHEDULER_DEFINITION", resource_id=row.id, detail={"code": code}
        )
        self.session.commit()
        return self._schedule_dict(row)

    def update_schedule(self, schedule_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._require("scheduler.write")
        row = self.repo.schedule_by_id(schedule_id, for_update=True)
        if row is None:
            raise AppError("调度不存在", code="SCHEDULER_NOT_FOUND", status_code=404)
        if int(row.lock_version) != int(data["expected_version"]):
            raise AppError(
                "调度版本冲突",
                code="SCHEDULER_VERSION_CONFLICT",
                status_code=409,
                data={"current_version": int(row.lock_version)},
            )
        params = data.get("parameters")
        if params is not None:
            self._validate_schedule_parameters(row.handler_key, params)
            row.parameters_json = _json_dump(params)
        for field in ("name", "cadence_seconds", "concurrency_policy", "timeout_seconds", "max_attempts"):
            if data.get(field) is not None:
                setattr(row, field, data[field])
        if "enabled" in data and data["enabled"] is not None:
            row.enabled = bool(data["enabled"])
            if row.enabled and row.next_run_at is None:
                row.next_run_at = utc_now()
        if "next_run_at" in data:
            row.next_run_at = self._dt(data.get("next_run_at"))
        row.lock_version = int(row.lock_version) + 1
        row.updated_by = self.ctx.user_id
        self.session.add(row)
        self.session.commit()
        return self._schedule_dict(row)

    def _execute_handler(self, row) -> dict[str, Any]:
        params = _json_load(row.parameters_json, {})
        if row.handler_key == "OUTBOX_DISPATCH":
            return self.dispatch(
                limit=int(params.get("limit") or 100),
                worker_id=f"schedule-{row.id}",
                enforce_permission=False,
            )
        if row.handler_key == "LEASE_TODO_SYNC":
            return WorkbenchSummaryService(self.session, self.ctx).sync_lease_expiring_todos(
                within_days=int(params.get("within_days") or 90)
            )
        if row.handler_key == "APPROVAL_OVERDUE_SWEEP":
            from app.modules.workflow.application.approval_service import ApprovalService

            return ApprovalService(self.session, self.ctx).sweep_overdue(
                limit=int(params.get("limit") or 200)
            )
        raise AppError("调度处理器未注册", code="SCHEDULER_HANDLER_NOT_REGISTERED", status_code=400)

    def run_schedule(
        self,
        schedule_id: int,
        *,
        idempotency_key: str,
        claimed_by: Optional[str] = None,
    ) -> dict[str, Any]:
        self._require("scheduler.run")
        existing = self.repo.run_by_key(idempotency_key)
        if existing is not None:
            if int(existing.schedule_id) != int(schedule_id):
                raise AppError(
                    "幂等键已用于其他调度",
                    code="IDEMPOTENCY_CONFLICT",
                    status_code=409,
                )
            return self._run_dict(existing)
        row = self.repo.schedule_by_id(schedule_id, for_update=True)
        if row is None:
            raise AppError("调度不存在", code="SCHEDULER_NOT_FOUND", status_code=404)
        # The first lookup may race with another caller. Re-check after locking
        # the definition so the same schedule/key has one durable run.
        existing = self.repo.run_by_key(idempotency_key)
        if existing is not None:
            if int(existing.schedule_id) != int(schedule_id):
                raise AppError(
                    "幂等键已用于其他调度",
                    code="IDEMPOTENCY_CONFLICT",
                    status_code=409,
                )
            return self._run_dict(existing)
        if row.concurrency_policy == "FORBID" and self.repo.active_schedule_run(row.id) is not None:
            raise AppError("调度已有运行实例", code="SCHEDULER_CONCURRENCY_CONFLICT", status_code=409)
        now = utc_now()
        try:
            run = self.repo.add_run(
                schedule_id=row.id,
                fire_at=now,
                generation=1,
                idempotency_key=idempotency_key,
                status="RUNNING",
                claim_token=uuid.uuid4().hex,
                claimed_by=str(claimed_by or self.ctx.username or self.ctx.user_id)[:96],
                attempt_no=1,
                started_at=now,
                heartbeat_at=now,
            )
            row.last_run_at = now
            row.next_run_at = now + timedelta(seconds=int(row.cadence_seconds))
            self.session.add(row)
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            existing = self.repo.run_by_key(idempotency_key)
            if existing is not None and int(existing.schedule_id) == int(schedule_id):
                return self._run_dict(existing)
            raise AppError(
                "调度幂等键冲突", code="IDEMPOTENCY_CONFLICT", status_code=409
            ) from exc
        try:
            result = self._execute_handler(row)
            run.status = "SUCCEEDED"
            run.result_json = _json_dump(result)
        except Exception as exc:
            run.status = "FAILED"
            run.error_message = str(exc).replace("\n", " ")[:_MAX_ERROR]
        run.finished_at = utc_now()
        run.heartbeat_at = run.finished_at
        self.session.add(run)
        self.audit.record(
            action="run",
            resource_type="SCHEDULER_RUN",
            resource_id=run.id,
            detail={"schedule_id": int(row.id), "status": run.status},
        )
        self.session.commit()
        return self._run_dict(run)

    def poll_schedules(self, *, limit: int = 20, worker_id: Optional[str] = None) -> dict[str, Any]:
        self._require("scheduler.run")
        due = list(self.repo.due_schedules(now=utc_now(), limit=min(max(limit, 1), 100)))
        results: list[dict[str, Any]] = []
        for row in due:
            fire = row.next_run_at or utc_now()
            key = f"scheduled:{row.id}:{fire.isoformat()}"
            results.append(
                self.run_schedule(
                    row.id,
                    idempotency_key=key,
                    claimed_by=worker_id or f"poller-{self.ctx.user_id}",
                )
            )
        return {"claimed": len(due), "runs": results}

    def list_runs(self, *, schedule_id: Optional[int], limit: int) -> list[dict[str, Any]]:
        self._require("scheduler.read")
        if schedule_id is not None and self.repo.schedule_by_id(schedule_id) is None:
            raise AppError("调度不存在", code="SCHEDULER_NOT_FOUND", status_code=404)
        return [self._run_dict(row) for row in self.repo.list_runs(schedule_id=schedule_id, limit=limit)]

    def recover_stale_runs(self, *, limit: int = 100) -> dict[str, Any]:
        self._require("scheduler.run")
        now = utc_now()
        rows = self.repo.stale_runs(before=now - timedelta(seconds=10), limit=min(max(limit, 1), 200))
        recovered = 0
        for run in rows:
            schedule = self.repo.schedule_by_id(run.schedule_id)
            if schedule is None or run.heartbeat_at >= now - timedelta(seconds=int(schedule.timeout_seconds)):
                continue
            run.status = "TIMED_OUT"
            run.finished_at = now
            run.error_message = "worker heartbeat timeout"
            self.session.add(run)
            recovered += 1
        if recovered:
            self.audit.record(
                action="recover",
                resource_type="SCHEDULER_RUN",
                resource_id=None,
                detail={"recovered": recovered},
            )
        self.session.commit()
        return {"scanned": len(rows), "recovered": recovered}

    # Layout --------------------------------------------------------------

    def _validate_widgets(self, widgets: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        keys: set[str] = set()
        for raw in widgets:
            key = str(raw["widget_key"]).strip().upper()
            if key not in WIDGET_REGISTRY or key in keys:
                raise AppError("工作台组件未注册或重复", code="WIDGET_INVALID", status_code=400)
            keys.add(key)
            x, y, width, height = (
                int(raw["position_x"]),
                int(raw["position_y"]),
                int(raw["width"]),
                int(raw["height"]),
            )
            if x < 0 or y < 0 or width < 1 or height < 1 or x + width > 12 or y > 99:
                raise AppError("组件超出网格", code="WIDGET_GRID_INVALID", status_code=400)
            config = raw.get("config") or {}
            _reject_sensitive(config, path=f"widget.{key}")
            if set(config) - {"limit", "park_id"}:
                raise AppError("组件配置字段无效", code="WIDGET_CONFIG_INVALID", status_code=400)
            _json_dump(config)
            normalized.append(
                {
                    "widget_key": key,
                    "position_x": x,
                    "position_y": y,
                    "width": width,
                    "height": height,
                    "visible": bool(raw.get("visible", True)),
                    "config_json": _json_dump(config),
                }
            )
        visible = [item for item in normalized if item["visible"]]
        for index, left in enumerate(visible):
            for right in visible[index + 1 :]:
                overlap = not (
                    left["position_x"] + left["width"] <= right["position_x"]
                    or right["position_x"] + right["width"] <= left["position_x"]
                    or left["position_y"] + left["height"] <= right["position_y"]
                    or right["position_y"] + right["height"] <= left["position_y"]
                )
                if overlap:
                    raise AppError("工作台组件重叠", code="WIDGET_GRID_OVERLAP", status_code=400)
        return normalized

    def _widget_data(
        self,
        key: str,
        *,
        park_id: Optional[int],
        summary: Optional[dict[str, Any]] = None,
    ) -> Any:
        if key == "MY_TODOS":
            return self.work_items.list_work_items(
                page=1, page_size=10, status="OPEN", park_id=park_id, mine=True
            )
        if key == "NOTIFICATIONS":
            return self.list_notifications(page=1, page_size=8, status=None)
        if key == "AUTOMATION_HEALTH":
            return self.repo.automation_health()
        if summary is None:
            summary = WorkbenchSummaryService(self.session, self.ctx).summary(
                park_id=park_id, todo_limit=10
            )
        if key == "OPERATIONS_METRICS":
            return summary["metrics"]
        if key == "UNPAID_BILLS":
            return {"value": summary["metrics"]["unpaid_bills"], "deep_link": "/bills"}
        if key == "EXPIRING_CONTRACTS":
            return {"value": summary["metrics"]["expiring_contracts"], "deep_link": "/leases"}
        return None

    def effective_layout(self, *, park_id: Optional[int] = None) -> dict[str, Any]:
        self._require("workbench.layout.read")
        if park_id is not None:
            self._assert_park(park_id)
        layout = self.repo.effective_layout(self.ctx.user_id)
        if layout is None:
            source = "SERVER_DEFAULT"
            layout_id = None
            lock_version = 0
            raw_widgets = [
                {
                    **item,
                    "visible": True,
                    "config_json": "{}",
                    "sort_order": index,
                }
                for index, item in enumerate(DEFAULT_WIDGETS)
            ]
            name = "默认运营工作台"
        else:
            source = "USER" if layout.owner_user_id is not None else "ROLE"
            layout_id = int(layout.id)
            lock_version = int(layout.lock_version)
            raw_widgets = self.repo.widgets(layout.id)
            name = layout.name
        widgets: list[dict[str, Any]] = []
        visible_keys = {
            item["widget_key"] if isinstance(item, dict) else item.widget_key
            for item in raw_widgets
            if bool((item if isinstance(item, dict) else item.__dict__).get("visible", True))
            and self.ctx.has_permission(
                WIDGET_REGISTRY[item["widget_key"] if isinstance(item, dict) else item.widget_key][
                    "permission"
                ]
            )
        }
        summary = None
        if visible_keys & {"OPERATIONS_METRICS", "UNPAID_BILLS", "EXPIRING_CONTRACTS"}:
            summary = WorkbenchSummaryService(self.session, self.ctx).summary(
                park_id=park_id, todo_limit=10
            )
        for item in raw_widgets:
            key = item["widget_key"] if isinstance(item, dict) else item.widget_key
            definition = WIDGET_REGISTRY[key]
            if not self.ctx.has_permission(definition["permission"]):
                continue
            value = item if isinstance(item, dict) else item.__dict__
            visible = bool(value.get("visible", True))
            widgets.append(
                {
                    "widget_key": key,
                    "title": definition["title"],
                    "required_permission": definition["permission"],
                    "position_x": int(value["position_x"]),
                    "position_y": int(value["position_y"]),
                    "width": int(value["width"]),
                    "height": int(value["height"]),
                    "visible": visible,
                    "config": _json_load(value.get("config_json"), {}),
                    "data": self._widget_data(key, park_id=park_id, summary=summary)
                    if visible
                    else None,
                }
            )
        return {
            "id": layout_id,
            "name": name,
            "source": source,
            "lock_version": lock_version,
            "editable": self.ctx.has_permission("workbench.layout.write"),
            "park_id": park_id,
            "widgets": widgets,
            "registry": [
                {"widget_key": key, **value}
                for key, value in WIDGET_REGISTRY.items()
                if self.ctx.has_permission(value["permission"])
            ],
        }

    def save_user_layout(self, data: dict[str, Any]) -> dict[str, Any]:
        self._require("workbench.layout.write")
        widgets = self._validate_widgets(data["widgets"])
        row = self.repo.user_layout(self.ctx.user_id, for_update=True)
        if row is None:
            if int(data["expected_version"]) != 0:
                raise AppError("布局版本冲突", code="LAYOUT_VERSION_CONFLICT", status_code=409)
            row = self.repo.add_layout(
                owner_user_id=self.ctx.user_id,
                role_id=None,
                name=str(data["name"]).strip(),
                is_active=True,
                priority=100,
                lock_version=1,
                created_by=self.ctx.user_id,
                updated_by=self.ctx.user_id,
            )
        else:
            if int(row.lock_version) != int(data["expected_version"]):
                raise AppError(
                    "布局版本冲突",
                    code="LAYOUT_VERSION_CONFLICT",
                    status_code=409,
                    data={"current_version": int(row.lock_version)},
                )
            row.name = str(data["name"]).strip()
            row.lock_version = int(row.lock_version) + 1
            row.updated_by = self.ctx.user_id
            self.session.add(row)
        self.repo.replace_widgets(row.id, widgets)
        self.audit.record(
            action="save",
            resource_type="WORKBENCH_LAYOUT",
            resource_id=row.id,
            detail={"owner": "USER", "widget_count": len(widgets)},
        )
        self.session.commit()
        return self.effective_layout()

    def reset_user_layout(self) -> dict[str, Any]:
        self._require("workbench.layout.write")
        deleted = self.repo.delete_user_layout(self.ctx.user_id)
        if deleted:
            self.audit.record(
                action="reset",
                resource_type="WORKBENCH_LAYOUT",
                resource_id=None,
                detail={"owner_user_id": self.ctx.user_id},
            )
        self.session.commit()
        return self.effective_layout()

    @staticmethod
    def _layout_widget_dict(item: Any) -> dict[str, Any]:
        return {
            "widget_key": item.widget_key,
            "position_x": int(item.position_x),
            "position_y": int(item.position_y),
            "width": int(item.width),
            "height": int(item.height),
            "visible": bool(item.visible),
            "config": _json_load(item.config_json, {}),
        }

    def list_role_layouts(self) -> list[dict[str, Any]]:
        self._require("workbench.layout.admin")
        return [
            {
                "role_id": int(role.id),
                "role_code": role.code,
                "role_name": role.name,
                "layout_id": int(layout.id) if layout is not None else None,
                "layout_name": layout.name if layout is not None else None,
                "priority": int(layout.priority) if layout is not None else 100,
                "lock_version": int(layout.lock_version) if layout is not None else 0,
            }
            for role, layout in self.repo.layout_roles()
        ]

    def get_role_layout(self, role_id: int) -> dict[str, Any]:
        self._require("workbench.layout.admin")
        role = self.repo.role_by_id(role_id)
        if role is None:
            raise AppError("角色不存在", code="ROLE_NOT_FOUND", status_code=404)
        row = self.repo.role_layout(role_id)
        if row is None:
            widgets = [
                {
                    "widget_key": item["widget_key"],
                    "position_x": int(item["position_x"]),
                    "position_y": int(item["position_y"]),
                    "width": int(item["width"]),
                    "height": int(item["height"]),
                    "visible": True,
                    "config": {},
                }
                for item in DEFAULT_WIDGETS
            ]
            return {
                "id": None,
                "role_id": int(role.id),
                "role_code": role.code,
                "role_name": role.name,
                "name": f"{role.name}默认工作台",
                "priority": 100,
                "lock_version": 0,
                "widgets": widgets,
            }
        return {
            "id": int(row.id),
            "role_id": int(role.id),
            "role_code": role.code,
            "role_name": role.name,
            "name": row.name,
            "priority": int(row.priority),
            "lock_version": int(row.lock_version),
            "widgets": [self._layout_widget_dict(item) for item in self.repo.widgets(row.id)],
        }

    def save_role_layout(self, data: dict[str, Any]) -> dict[str, Any]:
        self._require("workbench.layout.admin")
        role_id = int(data["role_id"])
        if not self.repo.role_exists(role_id):
            raise AppError("角色不存在", code="ROLE_NOT_FOUND", status_code=404)
        widgets = self._validate_widgets(data["widgets"])
        row = self.repo.role_layout(role_id, for_update=True)
        if row is None:
            if int(data["expected_version"]) != 0:
                raise AppError("布局版本冲突", code="LAYOUT_VERSION_CONFLICT", status_code=409)
            row = self.repo.add_layout(
                owner_user_id=None,
                role_id=role_id,
                name=str(data["name"]).strip(),
                is_active=True,
                priority=int(data.get("priority") or 100),
                lock_version=1,
                created_by=self.ctx.user_id,
                updated_by=self.ctx.user_id,
            )
        else:
            if int(row.lock_version) != int(data["expected_version"]):
                raise AppError("布局版本冲突", code="LAYOUT_VERSION_CONFLICT", status_code=409)
            row.name = str(data["name"]).strip()
            row.priority = int(data.get("priority") or row.priority)
            row.lock_version = int(row.lock_version) + 1
            row.updated_by = self.ctx.user_id
            self.session.add(row)
        self.repo.replace_widgets(row.id, widgets)
        self.audit.record(
            action="save_role",
            resource_type="WORKBENCH_LAYOUT",
            resource_id=row.id,
            detail={"role_id": role_id, "widget_count": len(widgets)},
        )
        self.session.commit()
        return {
            "id": int(row.id),
            "role_id": role_id,
            "name": row.name,
            "priority": int(row.priority),
            "lock_version": int(row.lock_version),
            "widgets": [self._layout_widget_dict(item) for item in self.repo.widgets(row.id)],
        }

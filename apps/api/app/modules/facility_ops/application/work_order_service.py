"""Tenant-service and governed work-order application service."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.business_logging import log_business_success
from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.modules.facility_ops.domain.work_order import (
    LINE_TYPES,
    PRIORITIES,
    assert_version,
    bounded_text,
    calculate_lines,
    mask_phone,
    money,
    quantity,
    sla_status,
    transition,
)
from app.modules.facility_ops.infrastructure.work_order_repository import (
    ServiceLifecycleRepository,
    WorkOrderRepository,
)
from app.modules.park_property.infrastructure.park_repository import ParkRepository
from app.modules.workbench.application.automation_service import WorkbenchAutomationService
from app.modules.workbench.application.work_item_service import WorkItemService
from app.shared.tenant_context import TenantContext

logger = logging.getLogger(__name__)

FIELD_ITEM_TYPE = "WORK_ORDER_FOLLOW"
ACCEPTANCE_ITEM_TYPE = "WORK_ORDER_ACCEPTANCE"


class WorkOrderService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.orders = WorkOrderRepository(session, ctx)
        self.lifecycle = ServiceLifecycleRepository(session, ctx)
        self.parks = ParkRepository(session, ctx)
        self.work_items = WorkItemService(session, ctx)
        self.events = WorkbenchAutomationService(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def _permission(self, *codes: str) -> None:
        if any(self.ctx.has_permission(code) for code in codes):
            return
        raise AppError("无操作权限", code="PERMISSION_DENIED", status_code=403)

    def _require(self, work_order_id: int, *, for_update: bool = False):
        model = self.orders.get_by_id(work_order_id, for_update=for_update)
        if model is None:
            raise AppError("工单不存在", code="WORK_ORDER_NOT_FOUND", status_code=404)
        return model

    def _assert_park(self, park_id: int) -> int:
        value = int(park_id)
        if not self.parks.exists_in_tenant(value):
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        if not self.ctx.allows_park(value):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        return value

    def _principal(self):
        principal = self.lifecycle.principal_for_user(int(self.ctx.user_id))
        if principal is None:
            raise AppError(
                "未绑定租户服务主体",
                code="TENANT_SERVICE_PRINCIPAL_REQUIRED",
                status_code=403,
            )
        return principal

    def _assert_principal_order(self, order):
        principal, park_ids = self._principal()
        if order.party_id is None or int(order.party_id) != int(principal.party_id):
            raise AppError("工单不存在", code="WORK_ORDER_NOT_FOUND", status_code=404)
        if int(order.park_id) not in park_ids:
            raise AppError("工单不存在", code="WORK_ORDER_NOT_FOUND", status_code=404)
        return principal

    def _order_no(self) -> str:
        return f"WO{utc_now():%Y%m%d}-{uuid4().hex[:10].upper()}"

    def _to_event(self, row, *, tenant_view: bool = False) -> dict[str, Any]:
        result = {
            "id": int(row.id),
            "event_type": row.event_type,
            "actor_type": row.actor_type,
            "from_status": row.from_status,
            "to_status": row.to_status,
            "reason": row.reason,
            "occurred_at": row.occurred_at.isoformat(),
        }
        if tenant_view:
            allowed = {
                "acceptance_id",
                "attempt_no",
                "auto_dispatched",
                "deadline",
                "evidence_count",
                "has_no_evidence_reason",
                "quote_id",
                "rating_id",
                "score",
                "source",
                "total",
                "version_no",
            }
            result["detail"] = {
                key: value for key, value in (row.detail_json or {}).items() if key in allowed
            }
        else:
            result["actor_user_id"] = row.actor_user_id
            result["detail"] = row.detail_json or {}
        return result

    def _to_quote(self, row, *, include_lines: bool = True) -> dict[str, Any]:
        result = {
            "id": int(row.id),
            "version_no": int(row.version_no),
            "status": row.status,
            "currency": row.currency,
            "total_amount": str(row.total_amount),
            "remark": row.remark,
            "lock_version": int(row.lock_version),
            "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
            "decided_at": row.decided_at.isoformat() if row.decided_at else None,
            "decision_remark": row.decision_remark,
        }
        if include_lines:
            result["lines"] = [
                {
                    "id": int(line.id),
                    "line_type": line.line_type,
                    "description": line.description,
                    "quantity": str(line.quantity),
                    "unit": line.unit,
                    "unit_price": str(line.unit_price),
                    "amount": str(line.amount),
                }
                for line in self.lifecycle.quote_lines(int(row.id))
            ]
        return result

    @staticmethod
    def _to_cost(row) -> dict[str, Any]:
        return {
            "id": int(row.id),
            "entry_type": row.entry_type,
            "description": row.description,
            "quantity": str(row.quantity),
            "unit": row.unit,
            "unit_price": str(row.unit_price),
            "amount": str(row.amount),
            "reverses_entry_id": row.reverses_entry_id,
            "reason": row.reason,
            "occurred_at": row.occurred_at.isoformat(),
        }

    @staticmethod
    def _to_acceptance(row) -> dict[str, Any]:
        return {
            "id": int(row.id),
            "attempt_no": int(row.attempt_no),
            "decision": row.decision,
            "comment": row.comment,
            "actor_party_id": int(row.actor_party_id),
            "decided_at": row.decided_at.isoformat(),
        }

    @staticmethod
    def _to_rating(row) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "id": int(row.id),
            "score": int(row.score),
            "tags": list(row.tags_json or []),
            "comment": row.comment,
            "created_at": row.created_at.isoformat(),
        }

    def _to_dict(self, model, *, tenant_view: bool = False, detail: bool = False) -> dict[str, Any]:
        now = utc_now()
        result: dict[str, Any] = {
            "id": int(model.id),
            "order_no": model.order_no,
            "park_id": int(model.park_id),
            "party_id": int(model.party_id) if model.party_id is not None else None,
            "title": model.title,
            "description": model.description,
            "category": model.category,
            "priority": model.priority,
            "status": model.status,
            "request_source": model.source_type,
            "quote_required": bool(model.quote_required),
            "contact_name": model.contact_name,
            "contact_phone_masked": model.contact_phone_masked,
            "unit_id": model.unit_id,
            "response_due_at": model.response_due_at.isoformat() if model.response_due_at else None,
            "resolution_due_at": model.resolution_due_at.isoformat()
            if model.resolution_due_at
            else None,
            "first_responded_at": model.first_responded_at.isoformat()
            if model.first_responded_at
            else None,
            "submitted_for_acceptance_at": model.submitted_for_acceptance_at.isoformat()
            if model.submitted_for_acceptance_at
            else None,
            "completed_at": model.completed_at.isoformat() if model.completed_at else None,
            "sla_status": sla_status(
                now=now,
                status=model.status,
                response_due_at=model.response_due_at,
                resolution_due_at=model.resolution_due_at,
                first_responded_at=model.first_responded_at,
                completed_at=model.completed_at,
            ),
            "lock_version": int(model.lock_version),
            "created_at": model.created_at.isoformat() if model.created_at else None,
        }
        if not tenant_view:
            result.update(
                {
                    "tenant_id": int(model.tenant_id),
                    "reporter_user_id": model.reporter_user_id,
                    "assignee_user_id": model.assignee_user_id,
                    "assignment_rule_id": model.assignment_rule_id,
                    "assignment_rule_version": model.assignment_rule_version,
                    "resolution_summary": model.resolution_summary,
                    "evidence_refs": list(model.evidence_refs_json or []),
                    "no_evidence_reason": model.no_evidence_reason,
                }
            )
        elif detail:
            result.update(
                {
                    "resolution_summary": model.resolution_summary,
                    "evidence_refs": list(model.evidence_refs_json or []),
                }
            )
        if detail:
            quotes = self.lifecycle.quotes(int(model.id))
            costs = self.lifecycle.costs(int(model.id))
            quote_total = next(
                (Decimal(str(row.total_amount)) for row in quotes if row.status == "ACCEPTED"),
                Decimal(0),
            )
            actual_total = sum((Decimal(str(row.amount)) for row in costs), Decimal(0))
            result.update(
                {
                    "timeline": [
                        self._to_event(row, tenant_view=tenant_view)
                        for row in self.lifecycle.events(int(model.id))
                    ],
                    "quotes": [self._to_quote(row) for row in quotes],
                    "acceptances": [
                        self._to_acceptance(row)
                        for row in self.lifecycle.acceptances(int(model.id))
                    ],
                    "rating": self._to_rating(self.lifecycle.rating(int(model.id))),
                    "accepted_quote_total": str(quote_total.quantize(Decimal("0.01"))),
                    "actual_total": str(actual_total.quantize(Decimal("0.01"))),
                    "cost_variance": str((actual_total - quote_total).quantize(Decimal("0.01"))),
                }
            )
            if not tenant_view:
                result["cost_entries"] = [self._to_cost(row) for row in costs]
        return result

    def _event(
        self,
        order,
        *,
        event_type: str,
        actor_type: str,
        from_status: str | None,
        to_status: str | None,
        reason: str | None = None,
        detail: dict[str, Any] | None = None,
        key: str,
        at: datetime | None = None,
    ) -> None:
        self.lifecycle.add_event(
            order=order,
            event_type=event_type,
            actor_type=actor_type,
            actor_user_id=self.ctx.user_id or None,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            detail=detail or {},
            idempotency_key=key,
            occurred_at=at or utc_now(),
        )

    def _bump(self, order) -> None:
        order.lock_version = int(order.lock_version) + 1
        self.orders.save(order)

    def list_orders(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        park_id: int | None = None,
        party_id: int | None = None,
        category: str | None = None,
        assignee_user_id: int | None = None,
    ) -> dict[str, Any]:
        self._permission("work_order:read")
        if park_id is not None:
            self._assert_park(int(park_id))
        page = max(int(page), 1)
        page_size = min(max(int(page_size), 1), 200)
        filters = {
            "status": status,
            "park_id": park_id,
            "party_id": party_id,
            "category": category,
            "assignee_user_id": assignee_user_id,
        }
        rows = self.orders.list(offset=(page - 1) * page_size, limit=page_size, **filters)
        return {
            "total": self.orders.count(**filters),
            "page": page,
            "page_size": page_size,
            "items": [self._to_dict(row) for row in rows],
        }

    def list_tenant_orders(self, *, page: int = 1, page_size: int = 20) -> dict[str, Any]:
        self._permission("tenant_service:read_own", "tenant_service:request")
        principal, park_ids = self._principal()
        visible = [park_id for park_id in park_ids if self.ctx.allows_park(park_id)]
        if not visible:
            return {"total": 0, "page": page, "page_size": page_size, "items": []}
        rows: list[Any] = []
        total = 0
        for park_id in visible:
            total += self.orders.count(party_id=int(principal.party_id), park_id=park_id)
            rows.extend(
                self.orders.list(
                    offset=0,
                    limit=page * page_size,
                    party_id=int(principal.party_id),
                    park_id=park_id,
                )
            )
        rows.sort(key=lambda row: int(row.id), reverse=True)
        start = (page - 1) * page_size
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                self._to_dict(row, tenant_view=True) for row in rows[start : start + page_size]
            ],
        }

    def get_order(self, work_order_id: int) -> dict[str, Any]:
        self._permission("work_order:read")
        return self._to_dict(self._require(work_order_id), detail=True)

    def get_tenant_order(self, work_order_id: int) -> dict[str, Any]:
        self._permission("tenant_service:read_own", "tenant_service:request")
        order = self._require(work_order_id)
        self._assert_principal_order(order)
        return self._to_dict(order, tenant_view=True, detail=True)

    def _validate_intake(self, data: dict[str, Any], *, tenant_party_id: int | None = None):
        park_id = self._assert_park(int(data["park_id"]))
        party_id = tenant_party_id if tenant_party_id is not None else data.get("party_id")
        party = None
        if party_id is not None:
            party = self.lifecycle.party(int(party_id))
            if party is None:
                raise AppError("主体不存在", code="PARTY_NOT_FOUND", status_code=404)
            if not self.lifecycle.party_has_park(int(party.id), park_id):
                raise AppError(
                    "主体未关联该园区", code="PARTY_PARK_RELATION_REQUIRED", status_code=409
                )
        contact = None
        if data.get("contact_id") is not None:
            if party is None:
                raise AppError("contact_id 需要主体", code="VALIDATION_ERROR", status_code=400)
            contact = self.lifecycle.contact(int(party.id), int(data["contact_id"]))
            if contact is None:
                raise AppError("联系人不存在", code="CONTACT_NOT_FOUND", status_code=404)
        if (
            data.get("unit_id") is not None
            and self.lifecycle.unit_in_park(int(data["unit_id"]), park_id) is None
        ):
            raise AppError("出租单元不存在", code="UNIT_NOT_FOUND", status_code=404)
        return park_id, party, contact

    def _create_order(
        self,
        data: dict[str, Any],
        *,
        idempotency_key: str,
        actor_type: str,
        tenant_party_id: int | None = None,
    ) -> dict[str, Any]:
        key = bounded_text(idempotency_key, field="Idempotency-Key", maximum=128, required=True)
        source_type = (
            "TENANT_PORTAL"
            if actor_type == "TENANT"
            else str(data.get("request_source") or "PROPERTY_STAFF").upper()
        )
        title = bounded_text(data.get("title"), field="title", maximum=255, required=True)
        category = bounded_text(
            data.get("category") or "GENERAL", field="category", maximum=64, required=True
        ).upper()
        priority = str(data.get("priority") or "MEDIUM").upper()
        if priority not in PRIORITIES:
            raise AppError("priority 无效", code="VALIDATION_ERROR", status_code=400)
        park_id, party, contact = self._validate_intake(data, tenant_party_id=tenant_party_id)
        description = (
            bounded_text(data.get("description"), field="description", maximum=2000) or None
        )
        contact_name = contact.name if contact is not None else data.get("contact_name")
        contact_name = bounded_text(contact_name, field="contact_name", maximum=64) or None
        contact_phone = contact.phone if contact is not None else data.get("contact_phone")
        contact_phone_masked = mask_phone(contact_phone)
        party_id = int(party.id) if party is not None else None
        contact_id = int(contact.id) if contact is not None else None
        unit_id = int(data["unit_id"]) if data.get("unit_id") is not None else None
        quote_required = bool(data.get("quote_required", False))
        existing = self.orders.get_by_source(source_type, key)
        if existing is not None:
            same_request = (
                int(existing.park_id) == park_id
                and existing.party_id == party_id
                and existing.contact_id == contact_id
                and existing.contact_name == contact_name
                and existing.contact_phone_masked == contact_phone_masked
                and existing.title == title
                and existing.description == description
                and existing.category == category
                and existing.priority == priority
                and existing.unit_id == unit_id
                and bool(existing.quote_required) == quote_required
            )
            if not same_request:
                raise AppError(
                    "Idempotency-Key 已用于不同请求",
                    code="IDEMPOTENCY_KEY_REUSED",
                    status_code=409,
                )
            return self._to_dict(existing, tenant_view=actor_type == "TENANT", detail=True)
        rule = self.lifecycle.match_rule(park_id=park_id, category=category, priority=priority)
        now = utc_now()
        assignee_user_id = int(rule.assignee_user_id) if rule is not None else None
        status = "ASSIGNED" if rule is not None else "SUBMITTED"
        response_due = now + timedelta(minutes=int(rule.response_minutes)) if rule else None
        resolution_due = now + timedelta(minutes=int(rule.resolution_minutes)) if rule else None
        order = self.orders.create(
            park_id=park_id,
            order_no=self._order_no(),
            party_id=party_id,
            contact_id=contact_id,
            contact_name=contact_name,
            contact_phone_masked=contact_phone_masked,
            title=title,
            description=description,
            category=category,
            priority=priority,
            reporter_user_id=self.ctx.user_id or None,
            assignee_user_id=assignee_user_id,
            unit_id=unit_id,
            due_at=resolution_due,
            source_type=source_type,
            source_id=key,
            quote_required=quote_required,
            status=status,
            assignment_rule_id=int(rule.id) if rule is not None else None,
            assignment_rule_version=int(rule.version_no) if rule is not None else None,
            response_due_at=response_due,
            resolution_due_at=resolution_due,
        )
        self._event(
            order,
            event_type="REQUEST_CREATED",
            actor_type=actor_type,
            from_status=None,
            to_status=status,
            detail={
                "source": source_type,
                "auto_dispatched": rule is not None,
                "assignment_rule_id": int(rule.id) if rule is not None else None,
            },
            key=f"work-order-create:{self.ctx.tenant_id}:{source_type}:{key}",
            at=now,
        )
        self.work_items.ensure_from_source(
            source_type="WORK_ORDER",
            source_id=str(order.id),
            item_type=FIELD_ITEM_TYPE,
            title=f"处理工单 {order.order_no}",
            description=title,
            park_id=park_id,
            priority=priority,
            assignee_user_id=assignee_user_id,
            due_at=resolution_due.isoformat() if resolution_due else None,
            deep_link="/work-orders",
            commit=False,
        )
        self.events.emit_event(
            event_type="WORK_ORDER_CREATED",
            source_type="WORK_ORDER",
            source_id=str(order.id),
            idempotency_key=f"work-order-created:{order.id}",
            park_id=park_id,
            payload={
                "title": f"新工单 {order.order_no}",
                "description": title,
                "priority": priority,
                "assignee_user_id": assignee_user_id,
                "due_at": resolution_due.isoformat() if resolution_due else None,
                "deep_link": "/work-orders",
                "park_id": park_id,
            },
            commit=False,
            enforce_permission=False,
        )
        self.audit.record(
            action="create",
            resource_type="WORK_ORDER",
            resource_id=int(order.id),
            park_id=park_id,
            detail={"order_no": order.order_no, "source": source_type},
        )
        self.session.commit()
        log_business_success(
            logger,
            "工单创建成功",
            ctx=self.ctx,
            module="facility_ops",
            action="create_work_order",
            resource_id=int(order.id),
            park_id=park_id,
        )
        return self._to_dict(order, tenant_view=actor_type == "TENANT", detail=True)

    def create_order(self, data: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        self._permission("work_order:write", "work_order:intake")
        return self._create_order(
            data,
            idempotency_key=idempotency_key,
            actor_type="STAFF",
        )

    def create_tenant_order(self, data: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        self._permission("tenant_service:request")
        principal, park_ids = self._principal()
        park_id = int(data["park_id"])
        if park_id not in park_ids or not self.ctx.allows_park(park_id):
            raise AppError("无该园区服务权限", code="PARK_SCOPE_DENIED", status_code=403)
        return self._create_order(
            data,
            idempotency_key=idempotency_key,
            actor_type="TENANT",
            tenant_party_id=int(principal.party_id),
        )

    def grant_principal(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("tenant_service:principal_manage")
        user = self.lifecycle.user(int(data["user_id"]))
        party = self.lifecycle.party(int(data["party_id"]))
        if user is None or party is None:
            raise AppError("用户或主体不存在", code="PRINCIPAL_TARGET_NOT_FOUND", status_code=404)
        park_ids = sorted({self._assert_park(int(value)) for value in data["park_ids"]})
        if not park_ids:
            raise AppError("park_ids 必填", code="VALIDATION_ERROR", status_code=400)
        if any(not self.lifecycle.party_has_park(int(party.id), park_id) for park_id in park_ids):
            raise AppError(
                "主体未关联全部授权园区",
                code="PARTY_PARK_RELATION_REQUIRED",
                status_code=409,
            )
        principal = self.lifecycle.grant_principal(
            user_id=int(user.id),
            party_id=int(party.id),
            park_ids=park_ids,
            created_by=self.ctx.user_id or None,
        )
        self.audit.record(
            action="grant",
            resource_type="TENANT_SERVICE_PRINCIPAL",
            resource_id=int(principal.id),
            park_id=park_ids[0],
            detail={"user_id": int(user.id), "party_id": int(party.id), "park_ids": park_ids},
        )
        self.session.commit()
        return {
            "id": int(principal.id),
            "user_id": int(principal.user_id),
            "party_id": int(principal.party_id),
            "park_ids": park_ids,
            "status": principal.status,
        }

    def list_principals(self) -> list[dict[str, Any]]:
        self._permission("tenant_service:principal_manage")
        return [
            {
                "id": int(row.id),
                "user_id": int(row.user_id),
                "party_id": int(row.party_id),
                "park_ids": parks,
                "status": row.status,
            }
            for row, parks in self.lifecycle.list_principals()
        ]

    def disable_principal(self, principal_id: int) -> dict[str, Any]:
        self._permission("tenant_service:principal_manage")
        row = self.lifecycle.disable_principal(
            principal_id, user_id=self.ctx.user_id or None, at=utc_now()
        )
        if row is None:
            raise AppError("租户服务主体不存在", code="PRINCIPAL_NOT_FOUND", status_code=404)
        self.session.commit()
        return {"id": int(row.id), "status": row.status}

    def create_rule(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("work_order:dispatch_rule_manage")
        code = bounded_text(data.get("code"), field="code", maximum=64, required=True).upper()
        name = bounded_text(data.get("name"), field="name", maximum=128, required=True)
        park_id = self._assert_park(int(data["park_id"])) if data.get("park_id") else None
        priority = str(data.get("priority") or "").upper() or None
        if priority is not None and priority not in PRIORITIES:
            raise AppError("priority 无效", code="VALIDATION_ERROR", status_code=400)
        assignee = self.lifecycle.user(int(data["assignee_user_id"]))
        if assignee is None or (park_id and not self.lifecycle.user_allows_park(assignee, park_id)):
            raise AppError("处理人无效或无园区权限", code="ASSIGNEE_SCOPE_DENIED", status_code=409)
        row = self.lifecycle.create_rule(
            {
                **data,
                "code": code,
                "name": name,
                "park_id": park_id,
                "category": str(data.get("category") or "").upper() or None,
                "priority": priority,
            },
            created_by=self.ctx.user_id or None,
        )
        self.session.commit()
        return self._rule_dict(row)

    @staticmethod
    def _rule_dict(row) -> dict[str, Any]:
        return {
            "id": int(row.id),
            "code": row.code,
            "version_no": int(row.version_no),
            "status": row.status,
            "name": row.name,
            "park_id": row.park_id,
            "category": row.category,
            "priority": row.priority,
            "assignee_user_id": int(row.assignee_user_id),
            "response_minutes": int(row.response_minutes),
            "resolution_minutes": int(row.resolution_minutes),
            "sort_order": int(row.sort_order),
            "published_at": row.published_at.isoformat() if row.published_at else None,
            "retired_at": row.retired_at.isoformat() if row.retired_at else None,
        }

    def list_rules(self) -> list[dict[str, Any]]:
        self._permission("work_order:dispatch_rule_manage", "work_order:dispatch")
        return [self._rule_dict(row) for row in self.lifecycle.list_rules()]

    def publish_rule(self, rule_id: int) -> dict[str, Any]:
        self._permission("work_order:dispatch_rule_manage")
        row = self.lifecycle.get_rule(rule_id, for_update=True)
        if row is None:
            raise AppError("派单规则不存在", code="ASSIGNMENT_RULE_NOT_FOUND", status_code=404)
        if row.status != "DRAFT":
            raise AppError("仅草稿可发布", code="ASSIGNMENT_RULE_STATUS_INVALID", status_code=409)
        self.lifecycle.publish_rule(row, user_id=self.ctx.user_id or None, at=utc_now())
        self.session.commit()
        return self._rule_dict(row)

    def retire_rule(self, rule_id: int, *, reason: str) -> dict[str, Any]:
        self._permission("work_order:dispatch_rule_manage")
        row = self.lifecycle.get_rule(rule_id, for_update=True)
        if row is None:
            raise AppError("派单规则不存在", code="ASSIGNMENT_RULE_NOT_FOUND", status_code=404)
        if row.status != "PUBLISHED":
            raise AppError("仅已发布规则可退役", code="ASSIGNMENT_RULE_STATUS_INVALID", status_code=409)
        normalized_reason = bounded_text(
            reason,
            field="reason",
            maximum=1000,
            required=True,
        )
        self.lifecycle.retire_rule(row, user_id=self.ctx.user_id or None, at=utc_now())
        self.audit.record(
            action="retire",
            resource_type="WORK_ORDER_ASSIGNMENT_RULE",
            resource_id=int(row.id),
            park_id=int(row.park_id) if row.park_id is not None else None,
            detail={
                "code": row.code,
                "version_no": int(row.version_no),
                "reason": normalized_reason,
            },
        )
        self.session.commit()
        return self._rule_dict(row)

    def dispatch(self, work_order_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("work_order:dispatch")
        order = self._require(work_order_id, for_update=True)
        assert_version(int(order.lock_version), int(data["expected_version"]))
        assignee = self.lifecycle.user(int(data["assignee_user_id"]))
        if assignee is None or not self.lifecycle.user_allows_park(assignee, int(order.park_id)):
            raise AppError("处理人无该园区权限", code="ASSIGNEE_SCOPE_DENIED", status_code=409)
        reason = bounded_text(data.get("reason"), field="reason", maximum=1000, required=True)
        previous_status = order.status
        previous_assignee = order.assignee_user_id
        order.status = transition(order.status, "DISPATCH")
        order.assignee_user_id = int(assignee.id)
        if order.response_due_at is None:
            order.response_due_at = utc_now() + timedelta(hours=1)
        if order.resolution_due_at is None:
            order.resolution_due_at = utc_now() + timedelta(hours=24)
        self._bump(order)
        self._event(
            order,
            event_type="ASSIGNED" if previous_assignee is None else "REASSIGNED",
            actor_type="STAFF",
            from_status=previous_status,
            to_status=order.status,
            reason=reason,
            detail={"from_user_id": previous_assignee, "to_user_id": int(assignee.id)},
            key=f"work-order-dispatch:{order.id}:{order.lock_version}",
        )
        self.work_items.ensure_from_source(
            source_type="WORK_ORDER",
            source_id=str(order.id),
            item_type=FIELD_ITEM_TYPE,
            title=f"处理工单 {order.order_no}",
            park_id=int(order.park_id),
            priority=order.priority,
            assignee_user_id=int(assignee.id),
            due_at=order.resolution_due_at.isoformat() if order.resolution_due_at else None,
            deep_link="/work-orders",
            commit=False,
        )
        self.session.commit()
        return self._to_dict(order, detail=True)

    def start_order(self, work_order_id: int, *, expected_version: int) -> dict[str, Any]:
        self._permission("work_order:execute", "work_order:write")
        order = self._require(work_order_id, for_update=True)
        if int(order.assignee_user_id or 0) != int(
            self.ctx.user_id
        ) and not self.ctx.has_permission("work_order:dispatch"):
            raise AppError(
                "仅当前处理人可接单", code="WORK_ORDER_ASSIGNEE_REQUIRED", status_code=403
            )
        assert_version(int(order.lock_version), expected_version)
        previous = order.status
        order.status = transition(order.status, "ACCEPT")
        now = utc_now()
        if order.first_responded_at is None:
            order.first_responded_at = now
        self._bump(order)
        self._event(
            order,
            event_type="WORK_ACCEPTED",
            actor_type="STAFF",
            from_status=previous,
            to_status=order.status,
            key=f"work-order-accept:{order.id}:{order.lock_version}",
            at=now,
        )
        self.session.commit()
        return self._to_dict(order, detail=True)

    def create_quote(self, work_order_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("work_order:quote")
        order = self._require(work_order_id, for_update=True)
        assert_version(int(order.lock_version), int(data["expected_version"]))
        if order.status not in {"IN_PROGRESS", "WAITING_QUOTE_APPROVAL"}:
            raise AppError("当前状态不可报价", code="WORK_ORDER_STATUS_INVALID", status_code=409)
        lines, total = calculate_lines(data["lines"])
        claimed = data.get("total_amount")
        if claimed is not None and money(claimed, field="total_amount") != total:
            raise AppError("报价总额不一致", code="QUOTE_TOTAL_MISMATCH", status_code=400)
        quote = self.lifecycle.create_quote(
            order=order,
            lines=lines,
            total=total,
            currency=str(data.get("currency") or "CNY").upper(),
            remark=bounded_text(data.get("remark"), field="remark", maximum=1000) or None,
            created_by=self.ctx.user_id or None,
        )
        self._event(
            order,
            event_type="QUOTE_DRAFTED",
            actor_type="STAFF",
            from_status=order.status,
            to_status=order.status,
            detail={
                "quote_id": int(quote.id),
                "version_no": int(quote.version_no),
                "total": str(total),
            },
            key=f"work-order-quote-draft:{quote.id}",
        )
        self.session.commit()
        return self._to_quote(quote)

    def submit_quote(
        self, work_order_id: int, quote_id: int, *, expected_version: int
    ) -> dict[str, Any]:
        self._permission("work_order:quote")
        order = self._require(work_order_id, for_update=True)
        assert_version(int(order.lock_version), expected_version)
        quote = self.lifecycle.quote(work_order_id, quote_id, for_update=True)
        if quote is None:
            raise AppError("报价不存在", code="WORK_ORDER_QUOTE_NOT_FOUND", status_code=404)
        if quote.status != "DRAFT":
            raise AppError("仅草稿可提交", code="QUOTE_STATUS_INVALID", status_code=409)
        previous = order.status
        if previous == "IN_PROGRESS":
            order.status = transition(previous, "REQUEST_QUOTE")
        elif previous != "WAITING_QUOTE_APPROVAL":
            raise AppError(
                "当前状态不可提交报价", code="WORK_ORDER_STATUS_INVALID", status_code=409
            )
        now = utc_now()
        quote.status = "SUBMITTED"
        quote.submitted_by = self.ctx.user_id or None
        quote.submitted_at = now
        quote.lock_version = int(quote.lock_version) + 1
        self.session.add(quote)
        self._bump(order)
        self._event(
            order,
            event_type="QUOTE_SUBMITTED",
            actor_type="STAFF",
            from_status=previous,
            to_status=order.status,
            detail={"quote_id": int(quote.id), "version_no": int(quote.version_no)},
            key=f"work-order-quote-submit:{quote.id}:{quote.lock_version}",
            at=now,
        )
        self.session.commit()
        return self._to_dict(order, detail=True)

    def decide_quote(
        self,
        work_order_id: int,
        quote_id: int,
        data: dict[str, Any],
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self._permission("tenant_service:quote_decide")
        principal, _ = self._principal()
        key = bounded_text(idempotency_key, field="Idempotency-Key", maximum=128, required=True)
        order = self._require(work_order_id, for_update=True)
        self._assert_principal_order(order)
        decision = str(data["decision"]).upper()
        if decision not in {"ACCEPT", "REJECT"}:
            raise AppError("decision 无效", code="VALIDATION_ERROR", status_code=400)
        reason = bounded_text(data.get("remark"), field="remark", maximum=1000)
        if decision == "REJECT" and not reason:
            raise AppError("拒绝报价必须填写原因", code="VALIDATION_ERROR", status_code=400)
        replay = self.lifecycle.quote_by_decision_key(key)
        if replay is not None:
            expected_status = "ACCEPTED" if decision == "ACCEPT" else "REJECTED"
            if (
                int(replay.id) != int(quote_id)
                or int(replay.work_order_id) != int(work_order_id)
                or replay.status != expected_status
                or (replay.decision_remark or "") != reason
            ):
                raise AppError(
                    "幂等键已用于不同报价决定",
                    code="IDEMPOTENCY_KEY_REUSED",
                    status_code=409,
                )
            return self._to_dict(order, tenant_view=True, detail=True)
        assert_version(int(order.lock_version), int(data["expected_version"]))
        quote = self.lifecycle.quote(work_order_id, quote_id, for_update=True)
        if quote is None or quote.status != "SUBMITTED":
            raise AppError("报价不存在或不可决定", code="QUOTE_STATUS_INVALID", status_code=409)
        previous = order.status
        order.status = transition(previous, f"QUOTE_{decision}")
        now = utc_now()
        quote.status = "ACCEPTED" if decision == "ACCEPT" else "REJECTED"
        quote.decided_by_user_id = self.ctx.user_id or None
        quote.decided_by_party_id = int(principal.party_id)
        quote.decided_at = now
        quote.decision_remark = reason or None
        quote.decision_key = key
        quote.lock_version = int(quote.lock_version) + 1
        self.session.add(quote)
        self._bump(order)
        self._event(
            order,
            event_type=f"QUOTE_{quote.status}",
            actor_type="TENANT",
            from_status=previous,
            to_status=order.status,
            reason=reason or None,
            detail={"quote_id": int(quote.id), "version_no": int(quote.version_no)},
            key=f"work-order-quote-decision:{self.ctx.tenant_id}:{key}",
            at=now,
        )
        self.session.commit()
        return self._to_dict(order, tenant_view=True, detail=True)

    def _assert_executor(self, order) -> None:
        if int(order.assignee_user_id or 0) == int(self.ctx.user_id):
            return
        if self.ctx.has_permission("work_order:dispatch"):
            return
        raise AppError("仅当前处理人可操作", code="WORK_ORDER_ASSIGNEE_REQUIRED", status_code=403)

    def add_cost(
        self, work_order_id: int, data: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
        self._permission("work_order:execute")
        order = self._require(work_order_id, for_update=True)
        self._assert_executor(order)
        assert_version(int(order.lock_version), int(data["expected_version"]))
        if order.status not in {"IN_PROGRESS", "IN_PROGRESS_AFTER_QUOTE"}:
            raise AppError(
                "当前状态不可登记执行成本", code="WORK_ORDER_STATUS_INVALID", status_code=409
            )
        if order.quote_required and self.lifecycle.accepted_quote(int(order.id)) is None:
            raise AppError("报价未获租户同意", code="QUOTE_ACCEPTANCE_REQUIRED", status_code=409)
        entry_type = str(data["entry_type"]).upper()
        if entry_type not in LINE_TYPES:
            raise AppError("entry_type 无效", code="VALIDATION_ERROR", status_code=400)
        qty = quantity(data["quantity"])
        price = money(data["unit_price"], field="unit_price")
        amount = (qty * price).quantize(Decimal("0.01"))
        key = bounded_text(idempotency_key, field="Idempotency-Key", maximum=128, required=True)
        existing = self.lifecycle.cost_by_key(key)
        if existing is not None:
            if (
                int(existing.work_order_id) != int(order.id)
                or existing.entry_type != entry_type
                or existing.description
                != bounded_text(
                    data.get("description"),
                    field="description",
                    maximum=255,
                    required=True,
                )
                or Decimal(str(existing.quantity)) != qty
                or existing.unit
                != bounded_text(data.get("unit"), field="unit", maximum=32, required=True)
                or Decimal(str(existing.unit_price)) != price
            ):
                raise AppError(
                    "幂等键已用于不同成本条目",
                    code="IDEMPOTENCY_KEY_REUSED",
                    status_code=409,
                )
            return self._to_cost(existing)
        row = self.lifecycle.add_cost(
            {
                "park_id": int(order.park_id),
                "work_order_id": int(order.id),
                "entry_type": entry_type,
                "description": bounded_text(
                    data.get("description"), field="description", maximum=255, required=True
                ),
                "quantity": qty,
                "unit": bounded_text(data.get("unit"), field="unit", maximum=32, required=True),
                "unit_price": price,
                "amount": amount,
                "reverses_entry_id": None,
                "reason": None,
                "idempotency_key": key,
                "created_by": self.ctx.user_id or None,
                "occurred_at": utc_now(),
            }
        )
        self._event(
            order,
            event_type="ACTUAL_COST_ADDED",
            actor_type="STAFF",
            from_status=order.status,
            to_status=order.status,
            detail={"cost_entry_id": int(row.id), "entry_type": entry_type, "amount": str(amount)},
            key=f"work-order-cost-event:{self.ctx.tenant_id}:{key}",
        )
        self.session.commit()
        return self._to_cost(row)

    def reverse_cost(
        self, work_order_id: int, cost_id: int, data: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
        self._permission("work_order:execute")
        order = self._require(work_order_id, for_update=True)
        self._assert_executor(order)
        assert_version(int(order.lock_version), int(data["expected_version"]))
        original = self.lifecycle.cost(work_order_id, cost_id)
        if original is None:
            raise AppError("成本条目不存在", code="WORK_ORDER_COST_NOT_FOUND", status_code=404)
        reason = bounded_text(data.get("reason"), field="reason", maximum=1000, required=True)
        key = bounded_text(idempotency_key, field="Idempotency-Key", maximum=128, required=True)
        existing = self.lifecycle.cost_by_key(key)
        if existing is not None:
            if (
                int(existing.work_order_id) != int(order.id)
                or int(existing.reverses_entry_id or 0) != int(original.id)
                or existing.reason != reason
            ):
                raise AppError(
                    "幂等键已用于不同冲正条目",
                    code="IDEMPOTENCY_KEY_REUSED",
                    status_code=409,
                )
            return self._to_cost(existing)
        row = self.lifecycle.add_cost(
            {
                "park_id": int(order.park_id),
                "work_order_id": int(order.id),
                "entry_type": original.entry_type,
                "description": f"冲正：{original.description}"[:255],
                "quantity": original.quantity,
                "unit": original.unit,
                "unit_price": original.unit_price,
                "amount": -abs(Decimal(str(original.amount))),
                "reverses_entry_id": int(original.id),
                "reason": reason,
                "idempotency_key": key,
                "created_by": self.ctx.user_id or None,
                "occurred_at": utc_now(),
            }
        )
        self._event(
            order,
            event_type="ACTUAL_COST_REVERSED",
            actor_type="STAFF",
            from_status=order.status,
            to_status=order.status,
            reason=reason,
            detail={"cost_entry_id": int(row.id), "reverses_entry_id": int(original.id)},
            key=f"work-order-cost-event:{self.ctx.tenant_id}:{key}",
        )
        self.session.commit()
        return self._to_cost(row)

    def submit_completion(self, work_order_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("work_order:execute", "work_order:write")
        order = self._require(work_order_id, for_update=True)
        self._assert_executor(order)
        assert_version(int(order.lock_version), int(data["expected_version"]))
        if order.quote_required and self.lifecycle.accepted_quote(int(order.id)) is None:
            raise AppError("报价未获租户同意", code="QUOTE_ACCEPTANCE_REQUIRED", status_code=409)
        summary = bounded_text(
            data.get("resolution_summary"),
            field="resolution_summary",
            maximum=2000,
            required=True,
        )
        evidence = [
            bounded_text(value, field="evidence_ref", maximum=256, required=True)
            for value in data.get("evidence_refs", [])
        ]
        no_evidence_reason = bounded_text(
            data.get("no_evidence_reason"), field="no_evidence_reason", maximum=512
        )
        if not evidence and not no_evidence_reason:
            raise AppError(
                "必须提供处理证据或无证据原因",
                code="COMPLETION_EVIDENCE_REQUIRED",
                status_code=400,
            )
        previous = order.status
        order.status = transition(previous, "SUBMIT_COMPLETION")
        now = utc_now()
        order.resolution_summary = summary
        order.evidence_refs_json = evidence
        order.no_evidence_reason = no_evidence_reason or None
        order.submitted_for_acceptance_at = now
        self._bump(order)
        self._event(
            order,
            event_type="COMPLETION_SUBMITTED",
            actor_type="STAFF",
            from_status=previous,
            to_status=order.status,
            detail={
                "evidence_count": len(evidence),
                "has_no_evidence_reason": bool(no_evidence_reason),
            },
            key=f"work-order-completion:{order.id}:{order.lock_version}",
            at=now,
        )
        self.work_items.complete_by_source(
            source_type="WORK_ORDER",
            source_id=str(order.id),
            item_type=FIELD_ITEM_TYPE,
            commit=False,
        )
        self.work_items.ensure_from_source(
            source_type="WORK_ORDER",
            source_id=str(order.id),
            item_type=ACCEPTANCE_ITEM_TYPE,
            title=f"验收工单 {order.order_no}",
            park_id=int(order.park_id),
            priority=order.priority,
            due_at=None,
            deep_link="/work-orders",
            commit=False,
        )
        self.session.commit()
        return self._to_dict(order, detail=True)

    def decide_acceptance(
        self, work_order_id: int, data: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
        self._permission("tenant_service:accept")
        principal, _ = self._principal()
        key = bounded_text(idempotency_key, field="Idempotency-Key", maximum=128, required=True)
        order = self._require(work_order_id, for_update=True)
        self._assert_principal_order(order)
        decision = str(data["decision"]).upper()
        if decision not in {"ACCEPTED", "REWORK"}:
            raise AppError("decision 无效", code="VALIDATION_ERROR", status_code=400)
        comment = bounded_text(data.get("comment"), field="comment", maximum=1000)
        if decision == "REWORK" and not comment:
            raise AppError("返工必须填写原因", code="VALIDATION_ERROR", status_code=400)
        replay = self.lifecycle.acceptance_by_key(key)
        if replay is not None:
            if (
                int(replay.work_order_id) != int(work_order_id)
                or replay.decision != decision
                or (replay.comment or "") != comment
            ):
                raise AppError(
                    "幂等键已用于不同验收决定",
                    code="IDEMPOTENCY_KEY_REUSED",
                    status_code=409,
                )
            return self._to_dict(order, tenant_view=True, detail=True)
        assert_version(int(order.lock_version), int(data["expected_version"]))
        previous = order.status
        accepted_quote = self.lifecycle.accepted_quote(int(order.id)) is not None
        order.status = transition(
            previous,
            "ACCEPT_WORK" if decision == "ACCEPTED" else "REWORK",
            has_accepted_quote=accepted_quote,
        )
        now = utc_now()
        acceptance = self.lifecycle.add_acceptance(
            {
                "park_id": int(order.park_id),
                "work_order_id": int(order.id),
                "attempt_no": self.lifecycle.next_acceptance_attempt(int(order.id)),
                "decision": decision,
                "comment": comment or None,
                "actor_user_id": self.ctx.user_id or None,
                "actor_party_id": int(principal.party_id),
                "idempotency_key": key,
                "decided_at": now,
            }
        )
        if decision == "ACCEPTED":
            order.completed_at = now
            order.closed_at = now
            self.work_items.complete_by_source(
                source_type="WORK_ORDER",
                source_id=str(order.id),
                item_type=ACCEPTANCE_ITEM_TYPE,
                commit=False,
            )
        else:
            order.completed_at = None
            order.closed_at = None
            self.work_items.complete_by_source(
                source_type="WORK_ORDER",
                source_id=str(order.id),
                item_type=ACCEPTANCE_ITEM_TYPE,
                commit=False,
            )
            self.work_items.ensure_from_source(
                source_type="WORK_ORDER",
                source_id=str(order.id),
                item_type=FIELD_ITEM_TYPE,
                title=f"返工 {order.order_no}",
                description=comment,
                park_id=int(order.park_id),
                priority=order.priority,
                assignee_user_id=order.assignee_user_id,
                due_at=order.resolution_due_at.isoformat() if order.resolution_due_at else None,
                deep_link="/work-orders",
                commit=False,
            )
        self._bump(order)
        self._event(
            order,
            event_type=f"WORK_{decision}",
            actor_type="TENANT",
            from_status=previous,
            to_status=order.status,
            reason=comment or None,
            detail={"acceptance_id": int(acceptance.id), "attempt_no": int(acceptance.attempt_no)},
            key=f"work-order-acceptance-event:{self.ctx.tenant_id}:{key}",
            at=now,
        )
        if decision == "ACCEPTED":
            self.events.emit_event(
                event_type="WORK_ORDER_COMPLETED",
                source_type="WORK_ORDER",
                source_id=str(order.id),
                idempotency_key=f"work-order-completed:{order.id}:{acceptance.id}",
                park_id=int(order.park_id),
                payload={
                    "title": f"工单已验收 {order.order_no}",
                    "description": "租户已验收",
                    "deep_link": "/work-orders",
                    "park_id": int(order.park_id),
                },
                commit=False,
                enforce_permission=False,
            )
        self.session.commit()
        return self._to_dict(order, tenant_view=True, detail=True)

    def rate_order(
        self, work_order_id: int, data: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
        self._permission("tenant_service:rate")
        principal, _ = self._principal()
        order = self._require(work_order_id, for_update=True)
        self._assert_principal_order(order)
        if order.status != "COMPLETED":
            raise AppError("仅已验收工单可评价", code="WORK_ORDER_STATUS_INVALID", status_code=409)
        key = bounded_text(idempotency_key, field="Idempotency-Key", maximum=128, required=True)
        existing = self.lifecycle.rating(int(order.id))
        score = int(data["score"])
        if score < 1 or score > 5:
            raise AppError("score 必须为 1 至 5", code="VALIDATION_ERROR", status_code=400)
        tags = sorted(
            {
                bounded_text(value, field="tag", maximum=32, required=True)
                for value in data.get("tags", [])
            }
        )
        comment = bounded_text(data.get("comment"), field="comment", maximum=1000)
        if existing is not None:
            if (
                existing.idempotency_key == key
                and int(existing.score) == score
                and list(existing.tags_json or []) == tags
                and (existing.comment or "") == comment
            ):
                return self._to_rating(existing) or {}
            raise AppError("工单已评价", code="WORK_ORDER_ALREADY_RATED", status_code=409)
        row = self.lifecycle.add_rating(
            {
                "park_id": int(order.park_id),
                "work_order_id": int(order.id),
                "score": score,
                "tags_json": tags,
                "comment": comment or None,
                "actor_user_id": self.ctx.user_id or None,
                "actor_party_id": int(principal.party_id),
                "idempotency_key": key,
                "created_at": utc_now(),
            }
        )
        self._event(
            order,
            event_type="RATED",
            actor_type="TENANT",
            from_status=order.status,
            to_status=order.status,
            detail={"rating_id": int(row.id), "score": score},
            key=f"work-order-rating-event:{self.ctx.tenant_id}:{key}",
        )
        self.session.commit()
        return self._to_rating(row) or {}

    def cancel_order(
        self, work_order_id: int, *, expected_version: int, reason: str
    ) -> dict[str, Any]:
        self._permission("work_order:write", "work_order:dispatch")
        order = self._require(work_order_id, for_update=True)
        assert_version(int(order.lock_version), expected_version)
        bounded_reason = bounded_text(reason, field="reason", maximum=1000, required=True)
        previous = order.status
        order.status = transition(previous, "CANCEL")
        order.closed_at = utc_now()
        self._bump(order)
        self._event(
            order,
            event_type="CANCELLED",
            actor_type="STAFF",
            from_status=previous,
            to_status=order.status,
            reason=bounded_reason,
            key=f"work-order-cancel:{order.id}:{order.lock_version}",
        )
        self.work_items.cancel_by_source(
            source_type="WORK_ORDER",
            source_id=str(order.id),
            item_type=FIELD_ITEM_TYPE,
            commit=False,
        )
        self.work_items.cancel_by_source(
            source_type="WORK_ORDER",
            source_id=str(order.id),
            item_type=ACCEPTANCE_ITEM_TYPE,
            commit=False,
        )
        self.session.commit()
        return self._to_dict(order, detail=True)

    def sweep_sla(self, *, as_of: datetime | None = None) -> dict[str, Any]:
        self._permission("work_order:sla_sweep")
        now = as_of or utc_now()
        if now.tzinfo is not None:
            now = now.astimezone(timezone.utc).replace(tzinfo=None)
        response_breaches = 0
        resolution_breaches = 0
        for order in self.lifecycle.sla_candidates(now):
            if (
                order.response_due_at
                and order.response_due_at < now
                and order.first_responded_at is None
            ):
                key = f"work-order-sla-response:{order.id}:{order.response_due_at.isoformat()}"
                if self.lifecycle.event_by_key(key) is None:
                    self._event(
                        order,
                        event_type="RESPONSE_SLA_BREACHED",
                        actor_type="SYSTEM",
                        from_status=order.status,
                        to_status=order.status,
                        detail={"deadline": order.response_due_at.isoformat()},
                        key=key,
                        at=now,
                    )
                    response_breaches += 1
            if order.resolution_due_at and order.resolution_due_at < now:
                key = f"work-order-sla-resolution:{order.id}:{order.resolution_due_at.isoformat()}"
                if self.lifecycle.event_by_key(key) is None:
                    self._event(
                        order,
                        event_type="RESOLUTION_SLA_BREACHED",
                        actor_type="SYSTEM",
                        from_status=order.status,
                        to_status=order.status,
                        detail={"deadline": order.resolution_due_at.isoformat()},
                        key=key,
                        at=now,
                    )
                    resolution_breaches += 1
            self.work_items.ensure_from_source(
                source_type="WORK_ORDER",
                source_id=str(order.id),
                item_type=FIELD_ITEM_TYPE,
                title=f"SLA 处理工单 {order.order_no}",
                park_id=int(order.park_id),
                priority="URGENT" if order.priority in {"HIGH", "URGENT"} else "HIGH",
                assignee_user_id=order.assignee_user_id,
                due_at=order.resolution_due_at.isoformat() if order.resolution_due_at else None,
                deep_link="/work-orders",
                commit=False,
            )
        self.session.commit()
        return {
            "as_of": now.isoformat(),
            "response_breaches_created": response_breaches,
            "resolution_breaches_created": resolution_breaches,
        }

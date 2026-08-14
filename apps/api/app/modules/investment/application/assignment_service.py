"""Versioned, deterministic Investment Lead assignment orchestration."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder, bounded_audit_detail
from app.infrastructure.database.base import utc_now
from app.modules.identity.infrastructure.authorization_repository import AuthorizationRepository
from app.modules.investment.domain.entities import (
    AssignmentMemberSpec,
    LeadAssignmentEventEntity,
)
from app.modules.investment.domain.rules import (
    choose_assignment_member,
    normalize_assignment_trigger,
    validate_assignment_members,
)
from app.modules.investment.infrastructure.completion_repository import AssignmentRuleRepository
from app.modules.investment.infrastructure.crm_repository import LeadAssignmentRepository
from app.modules.investment.infrastructure.mappers import LeadAssignmentEventMapper
from app.modules.park_property.infrastructure.park_repository import ParkRepository
from app.modules.workbench.application.work_item_service import WorkItemService
from app.shared.tenant_context import ParkScopeMode, TenantContext


class AssignmentRuleService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.rules = AssignmentRuleRepository(session, ctx)
        self.assignments = LeadAssignmentRepository(session, ctx)
        self.parks = ParkRepository(session, ctx)
        self.authorization = AuthorizationRepository(session)
        self.work_items = WorkItemService(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def _require(self, permission: str) -> None:
        if not self.ctx.has_permission(permission):
            raise AppError("无招商分配规则权限", code="PERMISSION_DENIED", status_code=403)

    def _assert_park(self, park_id: int) -> int:
        park_id = int(park_id)
        if not self.ctx.allows_park(park_id) or not self.parks.exists_in_tenant(park_id):
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        return park_id

    @staticmethod
    def _normalize_members(raw: Any) -> tuple[AssignmentMemberSpec, ...]:
        if not isinstance(raw, list):
            raise AppError("members 必须为数组", code="VALIDATION_ERROR", status_code=400)
        try:
            return validate_assignment_members(
                AssignmentMemberSpec(
                    user_id=int(item["user_id"]),
                    capacity=int(item["capacity"]),
                    weight=int(item.get("weight", 1)),
                    member_order=int(item.get("member_order", index + 1)),
                )
                for index, item in enumerate(raw)
                if isinstance(item, dict)
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AppError(str(exc), code="VALIDATION_ERROR", status_code=400) from exc

    def _member_specs(self, version, park_id: int) -> tuple[list[AssignmentMemberSpec], list[dict]]:
        rows = list(self.rules.members(int(version.id)))
        counts = self.rules.open_counts(int(park_id), [int(row.user_id) for row in rows])
        specs: list[AssignmentMemberSpec] = []
        details: list[dict] = []
        for row in rows:
            user = self.rules.user(int(row.user_id))
            eligible = user is not None and user.status == "ACTIVE"
            exclusion = None if eligible else "USER_INACTIVE_OR_MISSING"
            if eligible and user is not None:
                _, park_ids, mode = self.authorization.resolve_authorization(user)
                eligible = mode == ParkScopeMode.ALL or (
                    mode == ParkScopeMode.LIST and int(park_id) in park_ids
                )
                if not eligible:
                    exclusion = "PARK_SCOPE_REVOKED"
            spec = AssignmentMemberSpec(
                user_id=int(row.user_id),
                capacity=int(row.capacity),
                weight=int(row.weight),
                member_order=int(row.member_order),
                open_count=counts.get(int(row.user_id), 0),
                last_assigned_at=row.last_assigned_at,
                eligible=eligible,
                exclusion_reason=exclusion,
            )
            specs.append(spec)
            details.append(
                {
                    "user_id": spec.user_id,
                    "capacity": spec.capacity,
                    "weight": spec.weight,
                    "member_order": spec.member_order,
                    "open_count": spec.open_count,
                    "workload_ratio": round(spec.open_count / spec.capacity, 6),
                    "last_assigned_at": (
                        spec.last_assigned_at.isoformat() if spec.last_assigned_at else None
                    ),
                    "eligible": spec.eligible and spec.open_count < spec.capacity,
                    "exclusion_reason": (
                        spec.exclusion_reason
                        if spec.exclusion_reason
                        else ("AT_CAPACITY" if spec.open_count >= spec.capacity else None)
                    ),
                }
            )
        return specs, details

    def _version_dict(self, row) -> dict[str, Any]:
        members = self.rules.members(int(row.id))
        return {
            "id": int(row.id),
            "version": int(row.version),
            "status": row.status,
            "strategy": row.strategy,
            "recycle_after_hours": int(row.recycle_after_hours),
            "published_at": row.published_at.isoformat() if row.published_at else None,
            "members": [
                {
                    "id": int(member.id),
                    "user_id": int(member.user_id),
                    "capacity": int(member.capacity),
                    "weight": int(member.weight),
                    "member_order": int(member.member_order),
                    "last_assigned_at": (
                        member.last_assigned_at.isoformat() if member.last_assigned_at else None
                    ),
                }
                for member in members
            ],
        }

    def _rule_dict(self, row, *, include_versions: bool = True) -> dict[str, Any]:
        result = {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "code": row.code,
            "name": row.name,
            "trigger": row.trigger,
            "status": row.status,
            "current_version": int(row.current_version),
            "lock_version": int(row.lock_version),
            "description": row.description,
        }
        if include_versions:
            result["versions"] = [self._version_dict(version) for version in self.rules.versions(int(row.id))]
        return result

    def list_rules(self, *, park_id: int | None = None) -> list[dict[str, Any]]:
        self._require("lead.assignment_rule.read")
        if park_id is not None:
            self._assert_park(park_id)
        return [self._rule_dict(row, include_versions=False) for row in self.rules.list(park_id=park_id)]

    def get_rule(self, rule_id: int) -> dict[str, Any]:
        self._require("lead.assignment_rule.read")
        row = self.rules.get(rule_id)
        if row is None:
            raise AppError("分配规则不存在", code="ASSIGNMENT_RULE_NOT_FOUND", status_code=404)
        return self._rule_dict(row)

    def create_rule(self, data: dict[str, Any]) -> dict[str, Any]:
        self._require("lead.assignment_rule.write")
        park_id = self._assert_park(int(data["park_id"]))
        code = str(data.get("code") or "").strip().upper()
        name = str(data.get("name") or "").strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_.-]{1,63}", code) or not name:
            raise AppError("规则 code/name 无效", code="VALIDATION_ERROR", status_code=400)
        trigger = normalize_assignment_trigger(str(data.get("trigger") or ""))
        members = self._normalize_members(data.get("members"))
        recycle_hours = int(data.get("recycle_after_hours", 72))
        if recycle_hours < 1 or recycle_hours > 24 * 365:
            raise AppError("recycle_after_hours 无效", code="VALIDATION_ERROR", status_code=400)
        try:
            row = self.rules.create_rule(
                park_id=park_id,
                code=code,
                name=name,
                trigger=trigger,
                status="ACTIVE",
                current_version=0,
                lock_version=0,
                description=(str(data.get("description") or "").strip() or None),
                created_by=self.ctx.user_id or None,
                updated_by=self.ctx.user_id or None,
            )
            version = self.rules.create_version(
                rule_id=int(row.id),
                version=1,
                status="DRAFT",
                strategy="LEAST_LOAD",
                recycle_after_hours=recycle_hours,
                created_by=self.ctx.user_id or None,
            )
            for member in members:
                self.rules.create_member(
                    version_id=int(version.id),
                    user_id=member.user_id,
                    capacity=member.capacity,
                    weight=member.weight,
                    member_order=member.member_order,
                )
            self.audit.record(
                action="create",
                resource_type="LEAD_ASSIGNMENT_RULE",
                resource_id=row.id,
                park_id=park_id,
                detail={"code": code, "trigger": trigger, "member_count": len(members)},
            )
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(
                "园区触发器已存在分配规则", code="ASSIGNMENT_RULE_CONFLICT", status_code=409
            ) from exc
        return self._rule_dict(row)

    def update_draft(self, rule_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._require("lead.assignment_rule.write")
        row = self.rules.get(rule_id, for_update=True)
        if row is None:
            raise AppError("分配规则不存在", code="ASSIGNMENT_RULE_NOT_FOUND", status_code=404)
        if int(row.lock_version) != int(data["expected_lock_version"]):
            raise AppError("分配规则版本冲突", code="VERSION_CONFLICT", status_code=409)
        draft = self.rules.draft(rule_id)
        if draft is None:
            raise AppError("规则没有草稿", code="ASSIGNMENT_RULE_DRAFT_NOT_FOUND", status_code=409)
        if "members" in data:
            members = self._normalize_members(data["members"])
            self.rules.delete_members(int(draft.id))
            self.session.flush()
            for member in members:
                self.rules.create_member(
                    version_id=int(draft.id),
                    user_id=member.user_id,
                    capacity=member.capacity,
                    weight=member.weight,
                    member_order=member.member_order,
                )
        if data.get("name") is not None:
            name = str(data["name"]).strip()
            if not name:
                raise AppError("name 无效", code="VALIDATION_ERROR", status_code=400)
            row.name = name
        if "description" in data:
            row.description = str(data.get("description") or "").strip() or None
        if data.get("recycle_after_hours") is not None:
            hours = int(data["recycle_after_hours"])
            if hours < 1 or hours > 24 * 365:
                raise AppError("recycle_after_hours 无效", code="VALIDATION_ERROR", status_code=400)
            draft.recycle_after_hours = hours
            self.rules.save(draft)
        row.lock_version += 1
        row.updated_by = self.ctx.user_id or None
        self.rules.save(row)
        self.audit.record(
            action="update_draft",
            resource_type="LEAD_ASSIGNMENT_RULE",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"draft_version": int(draft.version)},
        )
        self.session.commit()
        return self._rule_dict(row)

    def create_draft(self, rule_id: int, *, expected_lock_version: int) -> dict[str, Any]:
        self._require("lead.assignment_rule.write")
        row = self.rules.get(rule_id, for_update=True)
        if row is None:
            raise AppError("分配规则不存在", code="ASSIGNMENT_RULE_NOT_FOUND", status_code=404)
        if int(row.lock_version) != int(expected_lock_version):
            raise AppError("分配规则版本冲突", code="VERSION_CONFLICT", status_code=409)
        existing = self.rules.draft(rule_id)
        if existing is not None:
            return self._version_dict(existing)
        source = self.rules.version(rule_id, int(row.current_version))
        if source is None:
            raise AppError("没有已发布版本可复制", code="ASSIGNMENT_RULE_NOT_PUBLISHED", status_code=409)
        draft = self.rules.create_version(
            rule_id=int(row.id),
            version=int(source.version) + 1,
            status="DRAFT",
            strategy=source.strategy,
            recycle_after_hours=int(source.recycle_after_hours),
            created_by=self.ctx.user_id or None,
        )
        for member in self.rules.members(int(source.id)):
            self.rules.create_member(
                version_id=int(draft.id),
                user_id=int(member.user_id),
                capacity=int(member.capacity),
                weight=int(member.weight),
                member_order=int(member.member_order),
            )
        row.lock_version += 1
        self.rules.save(row)
        self.session.commit()
        return self._version_dict(draft)

    def publish(self, rule_id: int, *, expected_lock_version: int) -> dict[str, Any]:
        self._require("lead.assignment_rule.write")
        row = self.rules.get(rule_id, for_update=True)
        if row is None:
            raise AppError("分配规则不存在", code="ASSIGNMENT_RULE_NOT_FOUND", status_code=404)
        if int(row.lock_version) != int(expected_lock_version):
            raise AppError("分配规则版本冲突", code="VERSION_CONFLICT", status_code=409)
        draft = self.rules.draft(rule_id)
        if draft is None:
            raise AppError("规则没有草稿", code="ASSIGNMENT_RULE_DRAFT_NOT_FOUND", status_code=409)
        specs, details = self._member_specs(draft, int(row.park_id))
        validate_assignment_members(specs)
        blocked = [item for item in details if item["exclusion_reason"] not in {None, "AT_CAPACITY"}]
        if blocked:
            raise AppError(
                "规则成员不再具备园区资格",
                code="ASSIGNMENT_MEMBER_INELIGIBLE",
                status_code=409,
                data={"members": blocked},
            )
        previous = self.rules.version(rule_id, int(row.current_version)) if row.current_version else None
        if previous is not None:
            previous.status = "RETIRED"
            self.rules.save(previous)
        now = utc_now()
        draft.status = "PUBLISHED"
        draft.published_at = now
        draft.published_by = self.ctx.user_id or None
        self.rules.save(draft)
        row.current_version = int(draft.version)
        row.lock_version += 1
        row.updated_by = self.ctx.user_id or None
        self.rules.save(row)
        self.audit.record(
            action="publish",
            resource_type="LEAD_ASSIGNMENT_RULE",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"version": int(draft.version), "member_count": len(specs)},
        )
        self.session.commit()
        return self._rule_dict(row)

    def preview(self, *, park_id: int, trigger: str) -> dict[str, Any]:
        self._require("lead.assignment_rule.read")
        park_id = self._assert_park(park_id)
        trigger = normalize_assignment_trigger(trigger)
        rule = self.rules.for_trigger(park_id, trigger)
        if rule is None:
            return {"rule_id": None, "trigger": trigger, "winner_user_id": None, "members": []}
        version = self.rules.version(int(rule.id), int(rule.current_version))
        if version is None or version.status != "PUBLISHED":
            return {"rule_id": int(rule.id), "trigger": trigger, "winner_user_id": None, "members": []}
        specs, details = self._member_specs(version, park_id)
        winner = choose_assignment_member(specs)
        return {
            "rule_id": int(rule.id),
            "rule_version_id": int(version.id),
            "version": int(version.version),
            "trigger": trigger,
            "winner_user_id": winner.user_id if winner else None,
            "fallback_reason": None if winner else "NO_ELIGIBLE_MEMBER",
            "members": details,
        }

    def retire(self, rule_id: int, *, expected_lock_version: int) -> dict[str, Any]:
        self._require("lead.assignment_rule.write")
        row = self.rules.get(rule_id, for_update=True)
        if row is None:
            raise AppError("分配规则不存在", code="ASSIGNMENT_RULE_NOT_FOUND", status_code=404)
        if int(row.lock_version) != int(expected_lock_version):
            raise AppError("分配规则版本冲突", code="VERSION_CONFLICT", status_code=409)
        if row.status == "RETIRED":
            return self._rule_dict(row)
        current = self.rules.version(rule_id, int(row.current_version)) if row.current_version else None
        if current is not None:
            current.status = "RETIRED"
            self.rules.save(current)
        draft = self.rules.draft(rule_id)
        if draft is not None:
            draft.status = "RETIRED"
            self.rules.save(draft)
        row.status = "RETIRED"
        row.lock_version += 1
        row.updated_by = self.ctx.user_id or None
        self.rules.save(row)
        self.audit.record(
            action="retire",
            resource_type="LEAD_ASSIGNMENT_RULE",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"current_version": int(row.current_version)},
        )
        self.session.commit()
        return self._rule_dict(row)

    def execute_for_lead(self, lead, *, trigger: str) -> dict[str, Any] | None:
        trigger = normalize_assignment_trigger(trigger)
        rule = self.rules.for_trigger(int(lead.park_id), trigger, for_update=True)
        if rule is None:
            return None
        version = self.rules.version(int(rule.id), int(rule.current_version), for_update=True)
        if version is None or version.status != "PUBLISHED":
            return None
        specs, details = self._member_specs(version, int(lead.park_id))
        winner = choose_assignment_member(specs)
        previous_owner = int(lead.owner_user_id) if lead.owner_user_id is not None else None
        now = utc_now()
        if winner is None:
            lead.owner_user_id = None
            lead.pool_status = "PUBLIC"
            lead.assigned_at = None
            lead.recycle_due_at = None
            event_type = "AUTO_ASSIGN_FALLBACK"
            reason = "NO_ELIGIBLE_MEMBER"
        else:
            lead.owner_user_id = winner.user_id
            lead.pool_status = "PRIVATE"
            lead.assigned_at = now
            if lead.next_follow_up_at is None:
                lead.next_follow_up_at = now + timedelta(days=3)
            lead.recycle_due_at = now + timedelta(hours=int(version.recycle_after_hours))
            for member in self.rules.members(int(version.id)):
                if int(member.user_id) == winner.user_id:
                    member.last_assigned_at = now
                    self.rules.save(member)
                    break
            event_type = "AUTO_ASSIGN"
            reason = "LEAST_LOAD"
        lead.lock_version = int(lead.lock_version) + 1
        event = LeadAssignmentEventMapper.new_model(
            LeadAssignmentEventEntity(
                tenant_id=self.ctx.tenant_id,
                park_id=int(lead.park_id),
                lead_id=int(lead.id),
                from_owner_user_id=previous_owner,
                to_owner_user_id=winner.user_id if winner else None,
                event_type=event_type,
                reason=reason,
                actor_user_id=self.ctx.user_id or None,
                occurred_at=now,
                rule_version_id=int(version.id),
                trigger=trigger,
                decision_json=bounded_audit_detail(
                    {
                        "winner_user_id": winner.user_id if winner else None,
                        "members": details,
                    }
                ),
            )
        )
        self.assignments.add(event)
        if winner is None:
            self.work_items.cancel_by_source(
                source_type="LEAD",
                source_id=str(lead.id),
                item_type="LEAD_FOLLOW",
                commit=False,
            )
        else:
            self.work_items.ensure_from_source(
                source_type="LEAD",
                source_id=str(lead.id),
                item_type="LEAD_FOLLOW",
                title=f"跟进招商线索 {str(lead.name)[:80]}",
                park_id=int(lead.park_id),
                priority="MEDIUM",
                assignee_user_id=winner.user_id,
                due_at=lead.next_follow_up_at,
                deep_link="/leads",
                commit=False,
            )
        self.audit.record(
            action="auto_assign",
            resource_type="LEAD",
            resource_id=lead.id,
            park_id=lead.park_id,
            detail={
                "rule_id": int(rule.id),
                "rule_version": int(version.version),
                "trigger": trigger,
                "winner_user_id": winner.user_id if winner else None,
                "fallback": winner is None,
            },
        )
        return {
            "rule_id": int(rule.id),
            "rule_version_id": int(version.id),
            "winner_user_id": winner.user_id if winner else None,
            "fallback_reason": None if winner else "NO_ELIGIBLE_MEMBER",
        }

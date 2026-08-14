"""Tenant/park-safe persistence for approval definitions, instances, tasks and delegation."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.identity import Role, User, UserRole
from app.infrastructure.database.models.workbench import WorkItem
from app.infrastructure.database.models.workflow import (
    ApprovalDefinition,
    ApprovalDefinitionStep,
    ApprovalDefinitionVersion,
    ApprovalDelegation,
    ApprovalEvent,
    ApprovalRequest,
    ApprovalStepAssignee,
    ApprovalTask,
)
from app.shared.tenant_context import ParkScopeMode, TenantContext


class ApprovalRepository:
    """All queries are tenant constrained; park-scoped roots are filtered before lookup."""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def _supports_row_lock(self) -> bool:
        return bool(
            self.session.bind is not None and self.session.bind.dialect.name == "postgresql"
        )

    def _scope(self, stmt):
        stmt = stmt.where(ApprovalRequest.tenant_id == self.ctx.tenant_id)
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(
                or_(
                    ApprovalRequest.park_id.is_(None),
                    ApprovalRequest.park_id.in_(list(self.ctx.park_ids)),
                )
            )
        return stmt.where(ApprovalRequest.park_id.is_(None))

    def _definition_scope(self, stmt):
        stmt = stmt.where(ApprovalDefinition.tenant_id == self.ctx.tenant_id)
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(
                or_(
                    ApprovalDefinition.park_id.is_(None),
                    ApprovalDefinition.park_id.in_(list(self.ctx.park_ids)),
                )
            )
        return stmt.where(ApprovalDefinition.park_id.is_(None))

    def _validate_park(self, park_id: int | None) -> None:
        if park_id is not None and not self.ctx.allows_park(int(park_id)):
            raise AppError("园区不可访问", code="PARK_SCOPE_DENIED", status_code=403)

    # Compatibility reads/writes retained for Lease and the previous flat approval API.
    def list(
        self,
        *,
        status: str | None = None,
        biz_type: str | None = None,
        park_id: int | None = None,
        priority: str | None = None,
        applicant_user_id: int | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[ApprovalRequest]:
        stmt = self._scope(select(ApprovalRequest))
        if status:
            stmt = stmt.where(ApprovalRequest.status == status)
        if biz_type:
            stmt = stmt.where(ApprovalRequest.biz_type == biz_type)
        if park_id is not None:
            self._validate_park(park_id)
            stmt = stmt.where(ApprovalRequest.park_id == int(park_id))
        if priority:
            stmt = stmt.where(ApprovalRequest.priority == priority)
        if applicant_user_id is not None:
            stmt = stmt.where(ApprovalRequest.applicant_user_id == int(applicant_user_id))
        if created_from is not None:
            stmt = stmt.where(ApprovalRequest.created_at >= created_from)
        if created_to is not None:
            stmt = stmt.where(ApprovalRequest.created_at <= created_to)
        return list(
            self.session.scalars(
                stmt.order_by(ApprovalRequest.id.desc()).offset(offset).limit(limit)
            ).all()
        )

    def count(
        self,
        *,
        status: str | None = None,
        biz_type: str | None = None,
        park_id: int | None = None,
        priority: str | None = None,
        applicant_user_id: int | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> int:
        visible = self._scope(select(ApprovalRequest.id))
        if status:
            visible = visible.where(ApprovalRequest.status == status)
        if biz_type:
            visible = visible.where(ApprovalRequest.biz_type == biz_type)
        if park_id is not None:
            self._validate_park(park_id)
            visible = visible.where(ApprovalRequest.park_id == int(park_id))
        if priority:
            visible = visible.where(ApprovalRequest.priority == priority)
        if applicant_user_id is not None:
            visible = visible.where(ApprovalRequest.applicant_user_id == int(applicant_user_id))
        if created_from is not None:
            visible = visible.where(ApprovalRequest.created_at >= created_from)
        if created_to is not None:
            visible = visible.where(ApprovalRequest.created_at <= created_to)
        return int(self.session.scalar(select(func.count()).select_from(visible.subquery())) or 0)

    def get_by_id(self, approval_id: int, *, for_update: bool = False) -> ApprovalRequest | None:
        stmt = self._scope(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))
        if for_update and self._supports_row_lock():
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def get_by_biz(self, biz_type: str, biz_id: str) -> ApprovalRequest | None:
        return self.session.scalars(
            select(ApprovalRequest).where(
                ApprovalRequest.tenant_id == self.ctx.tenant_id,
                ApprovalRequest.biz_type == biz_type,
                ApprovalRequest.biz_id == biz_id,
            )
        ).first()

    def get_by_submission_key(self, idempotency_key: str) -> ApprovalRequest | None:
        return self.session.scalars(
            select(ApprovalRequest).where(
                ApprovalRequest.tenant_id == self.ctx.tenant_id,
                ApprovalRequest.idempotency_key == idempotency_key,
            )
        ).first()

    def list_for_lease(
        self, contract_id: int, *, related_approval_ids: set[int]
    ) -> Sequence[ApprovalRequest]:
        conditions = [
            and_(
                ApprovalRequest.biz_type == "LEASE_CONTRACT_VERSION",
                ApprovalRequest.biz_id.like(f"{int(contract_id)}:%"),
            )
        ]
        if related_approval_ids:
            conditions.append(ApprovalRequest.id.in_(sorted(related_approval_ids)))
        stmt = self._scope(select(ApprovalRequest)).where(or_(*conditions))
        return list(self.session.scalars(stmt.order_by(ApprovalRequest.id)).all())

    def create(
        self,
        *,
        park_id: int | None,
        biz_type: str,
        biz_id: str,
        title: str,
        applicant_user_id: int | None,
        remark: str | None,
    ) -> ApprovalRequest:
        self._validate_park(park_id)
        model = ApprovalRequest(
            tenant_id=self.ctx.tenant_id,
            park_id=park_id,
            biz_type=biz_type,
            biz_id=biz_id,
            title=title,
            status="PENDING",
            applicant_user_id=applicant_user_id,
            remark=remark,
            priority="MEDIUM",
            round_no=1,
            lock_version=0,
            submitted_at=utc_now(),
            compatibility_mode="LEGACY_COMPAT",
        )
        self.session.add(model)
        self.session.flush()
        return model

    def create_native_request(
        self,
        *,
        definition_version_id: int,
        request_no: str,
        park_id: int | None,
        biz_type: str,
        biz_id: str,
        title: str,
        applicant_user_id: int,
        remark: str | None,
        priority: str,
        snapshot_json: dict[str, Any] | None,
        idempotency_key: str,
    ) -> ApprovalRequest:
        self._validate_park(park_id)
        now = utc_now()
        model = ApprovalRequest(
            tenant_id=self.ctx.tenant_id,
            definition_version_id=definition_version_id,
            request_no=request_no,
            park_id=park_id,
            biz_type=biz_type,
            biz_id=biz_id,
            title=title,
            status="PENDING",
            applicant_user_id=applicant_user_id,
            remark=remark,
            priority=priority,
            round_no=1,
            submitted_at=now,
            snapshot_json=snapshot_json,
            lock_version=0,
            idempotency_key=idempotency_key,
            compatibility_mode="NATIVE",
        )
        self.session.add(model)
        self.session.flush()
        return model

    def save(self, model: ApprovalRequest) -> ApprovalRequest:
        if int(model.tenant_id) != self.ctx.tenant_id:
            raise AppError("租户不匹配", code="TENANT_MISMATCH", status_code=403)
        self.session.add(model)
        self.session.flush()
        return model

    def add_event(
        self,
        *,
        approval_id: int,
        action: str,
        actor_user_id: int | None,
        remark: str | None,
        round_no: int = 1,
        step_order: int | None = None,
        task_id: int | None = None,
        original_assignee_user_id: int | None = None,
        idempotency_key: str | None = None,
        detail_json: dict[str, Any] | None = None,
    ) -> ApprovalEvent:
        event = ApprovalEvent(
            tenant_id=self.ctx.tenant_id,
            approval_id=approval_id,
            action=action,
            actor_user_id=actor_user_id,
            remark=remark,
            round_no=round_no,
            step_order=step_order,
            task_id=task_id,
            original_assignee_user_id=original_assignee_user_id,
            idempotency_key=idempotency_key,
            detail_json=detail_json,
        )
        self.session.add(event)
        self.session.flush()
        return event

    def list_events(self, approval_id: int) -> Sequence[ApprovalEvent]:
        return list(
            self.session.scalars(
                select(ApprovalEvent)
                .where(
                    ApprovalEvent.tenant_id == self.ctx.tenant_id,
                    ApprovalEvent.approval_id == approval_id,
                )
                .order_by(ApprovalEvent.id.asc())
            ).all()
        )

    def event_by_key(self, idempotency_key: str) -> ApprovalEvent | None:
        return self.session.scalars(
            select(ApprovalEvent).where(
                ApprovalEvent.tenant_id == self.ctx.tenant_id,
                ApprovalEvent.idempotency_key == idempotency_key,
            )
        ).first()

    # Definition governance.
    def list_definitions(
        self,
        *,
        status: str | None,
        biz_type: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[ApprovalDefinition], int]:
        stmt = self._definition_scope(select(ApprovalDefinition))
        count_stmt = self._definition_scope(select(ApprovalDefinition.id))
        if status:
            stmt = stmt.where(ApprovalDefinition.status == status)
            count_stmt = count_stmt.where(ApprovalDefinition.status == status)
        if biz_type:
            stmt = stmt.where(ApprovalDefinition.biz_type == biz_type)
            count_stmt = count_stmt.where(ApprovalDefinition.biz_type == biz_type)
        rows = list(
            self.session.scalars(
                stmt.order_by(ApprovalDefinition.id.desc()).offset(offset).limit(limit)
            ).all()
        )
        total = int(
            self.session.scalar(select(func.count()).select_from(count_stmt.subquery())) or 0
        )
        return rows, total

    def get_definition(
        self, definition_id: int, *, for_update: bool = False
    ) -> ApprovalDefinition | None:
        stmt = self._definition_scope(
            select(ApprovalDefinition).where(ApprovalDefinition.id == definition_id)
        )
        if for_update and self._supports_row_lock():
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def get_definition_by_code(self, code: str) -> ApprovalDefinition | None:
        return self.session.scalars(
            self._definition_scope(
                select(ApprovalDefinition).where(ApprovalDefinition.code == code)
            )
        ).first()

    def get_version(self, version_id: int) -> ApprovalDefinitionVersion | None:
        return self.session.scalars(
            select(ApprovalDefinitionVersion).where(
                ApprovalDefinitionVersion.id == version_id,
                ApprovalDefinitionVersion.tenant_id == self.ctx.tenant_id,
            )
        ).first()

    def list_versions(self, definition_id: int) -> list[ApprovalDefinitionVersion]:
        return list(
            self.session.scalars(
                select(ApprovalDefinitionVersion)
                .where(
                    ApprovalDefinitionVersion.tenant_id == self.ctx.tenant_id,
                    ApprovalDefinitionVersion.definition_id == definition_id,
                )
                .order_by(ApprovalDefinitionVersion.version.desc())
            ).all()
        )

    def get_draft(self, definition_id: int) -> ApprovalDefinitionVersion | None:
        return self.session.scalars(
            select(ApprovalDefinitionVersion).where(
                ApprovalDefinitionVersion.tenant_id == self.ctx.tenant_id,
                ApprovalDefinitionVersion.definition_id == definition_id,
                ApprovalDefinitionVersion.status == "DRAFT",
            )
        ).first()

    def save_definition(self, definition: ApprovalDefinition) -> ApprovalDefinition:
        if int(definition.tenant_id) != self.ctx.tenant_id:
            raise AppError("租户不匹配", code="TENANT_MISMATCH", status_code=403)
        self.session.add(definition)
        self.session.flush()
        return definition

    def definition_steps(self, version_id: int) -> list[ApprovalDefinitionStep]:
        return list(
            self.session.scalars(
                select(ApprovalDefinitionStep)
                .where(
                    ApprovalDefinitionStep.tenant_id == self.ctx.tenant_id,
                    ApprovalDefinitionStep.version_id == version_id,
                )
                .order_by(ApprovalDefinitionStep.step_order)
            ).all()
        )

    def step_assignees(self, step_id: int) -> list[ApprovalStepAssignee]:
        return list(
            self.session.scalars(
                select(ApprovalStepAssignee).where(
                    ApprovalStepAssignee.tenant_id == self.ctx.tenant_id,
                    ApprovalStepAssignee.step_id == step_id,
                )
            ).all()
        )

    def validate_assignee_references(self, steps: list[dict[str, Any]]) -> None:
        user_ids = {
            int(item["user_id"])
            for step in steps
            for item in step.get("assignees", [])
            if item.get("user_id") is not None
        }
        role_ids = {
            int(item["role_id"])
            for step in steps
            for item in step.get("assignees", [])
            if item.get("role_id") is not None
        }
        if user_ids:
            found = set(
                self.session.scalars(
                    select(User.id).where(
                        User.tenant_id == self.ctx.tenant_id,
                        User.status == "ACTIVE",
                        User.id.in_(sorted(user_ids)),
                    )
                ).all()
            )
            if found != user_ids:
                raise AppError(
                    "审批人引用无效",
                    code="APPROVAL_ASSIGNEE_INVALID",
                    status_code=400,
                )
        if role_ids:
            found = set(
                self.session.scalars(
                    select(Role.id).where(
                        Role.tenant_id == self.ctx.tenant_id,
                        Role.status == "ACTIVE",
                        Role.id.in_(sorted(role_ids)),
                    )
                ).all()
            )
            if found != role_ids:
                raise AppError(
                    "审批角色引用无效",
                    code="APPROVAL_ASSIGNEE_INVALID",
                    status_code=400,
                )

    def create_definition(
        self,
        *,
        code: str,
        name: str,
        biz_type: str,
        park_id: int | None,
        description: str | None,
        steps: list[dict[str, Any]],
    ) -> tuple[ApprovalDefinition, ApprovalDefinitionVersion]:
        self._validate_park(park_id)
        self.validate_assignee_references(steps)
        definition = ApprovalDefinition(
            tenant_id=self.ctx.tenant_id,
            park_id=park_id,
            code=code,
            name=name,
            biz_type=biz_type,
            status="ACTIVE",
            current_version=0,
            lock_version=0,
            description=description,
            created_by=self.ctx.user_id or None,
            updated_by=self.ctx.user_id or None,
        )
        self.session.add(definition)
        self.session.flush()
        version = ApprovalDefinitionVersion(
            tenant_id=self.ctx.tenant_id,
            definition_id=int(definition.id),
            version=1,
            status="DRAFT",
            created_by=self.ctx.user_id or None,
        )
        self.session.add(version)
        self.session.flush()
        self.replace_draft_steps(version, steps)
        return definition, version

    def replace_draft_steps(
        self, version: ApprovalDefinitionVersion, steps: list[dict[str, Any]]
    ) -> None:
        if version.status != "DRAFT":
            raise AppError(
                "已发布版本不可修改",
                code="APPROVAL_VERSION_IMMUTABLE",
                status_code=409,
            )
        self.validate_assignee_references(steps)
        existing_step_ids = [int(row.id) for row in self.definition_steps(int(version.id))]
        if existing_step_ids:
            self.session.execute(
                delete(ApprovalStepAssignee).where(
                    ApprovalStepAssignee.tenant_id == self.ctx.tenant_id,
                    ApprovalStepAssignee.step_id.in_(existing_step_ids),
                )
            )
            self.session.execute(
                delete(ApprovalDefinitionStep).where(
                    ApprovalDefinitionStep.tenant_id == self.ctx.tenant_id,
                    ApprovalDefinitionStep.id.in_(existing_step_ids),
                )
            )
            self.session.flush()
        for step_data in steps:
            step = ApprovalDefinitionStep(
                tenant_id=self.ctx.tenant_id,
                version_id=int(version.id),
                step_order=int(step_data["step_order"]),
                name=str(step_data["name"]),
                approval_mode=str(step_data["approval_mode"]),
                min_approvals=int(step_data["min_approvals"]),
                sla_hours=int(step_data["sla_hours"]),
            )
            self.session.add(step)
            self.session.flush()
            for assignee in step_data.get("assignees", []):
                self.session.add(
                    ApprovalStepAssignee(
                        tenant_id=self.ctx.tenant_id,
                        step_id=int(step.id),
                        user_id=assignee.get("user_id"),
                        role_id=assignee.get("role_id"),
                    )
                )
        self.session.flush()

    def create_draft_copy(self, definition: ApprovalDefinition) -> ApprovalDefinitionVersion:
        draft = self.get_draft(int(definition.id))
        if draft is not None:
            return draft
        versions = self.list_versions(int(definition.id))
        next_version = max((int(row.version) for row in versions), default=0) + 1
        draft = ApprovalDefinitionVersion(
            tenant_id=self.ctx.tenant_id,
            definition_id=int(definition.id),
            version=next_version,
            status="DRAFT",
            created_by=self.ctx.user_id or None,
        )
        self.session.add(draft)
        self.session.flush()
        published = next(
            (row for row in versions if int(row.version) == int(definition.current_version)),
            None,
        )
        if published is not None:
            copied_steps: list[dict[str, Any]] = []
            for step in self.definition_steps(int(published.id)):
                copied_steps.append(
                    {
                        "step_order": int(step.step_order),
                        "name": step.name,
                        "approval_mode": step.approval_mode,
                        "min_approvals": int(step.min_approvals),
                        "sla_hours": int(step.sla_hours),
                        "assignees": [
                            {"user_id": row.user_id, "role_id": row.role_id}
                            for row in self.step_assignees(int(step.id))
                        ],
                    }
                )
            self.replace_draft_steps(draft, copied_steps)
        return draft

    def resolve_candidates(self, step_id: int) -> list[int]:
        assignees = self.step_assignees(step_id)
        direct = {int(row.user_id) for row in assignees if row.user_id is not None}
        role_ids = {int(row.role_id) for row in assignees if row.role_id is not None}
        if role_ids:
            direct.update(
                int(user_id)
                for user_id in self.session.scalars(
                    select(UserRole.user_id).where(
                        UserRole.tenant_id == self.ctx.tenant_id,
                        UserRole.role_id.in_(sorted(role_ids)),
                    )
                ).all()
            )
        if not direct:
            return []
        active = self.session.scalars(
            select(User.id).where(
                User.tenant_id == self.ctx.tenant_id,
                User.status == "ACTIVE",
                User.id.in_(sorted(direct)),
            )
        ).all()
        return sorted({int(user_id) for user_id in active})

    def validate_publishable(self, version: ApprovalDefinitionVersion) -> None:
        steps = self.definition_steps(int(version.id))
        if not steps:
            raise AppError(
                "审批版本至少需要一个步骤",
                code="APPROVAL_DEFINITION_INVALID",
                status_code=400,
            )
        if [int(row.step_order) for row in steps] != list(range(1, len(steps) + 1)):
            raise AppError(
                "审批步骤必须从 1 连续编号",
                code="APPROVAL_DEFINITION_INVALID",
                status_code=400,
            )
        for step in steps:
            candidates = self.resolve_candidates(int(step.id))
            if not candidates or len(candidates) > 100:
                raise AppError(
                    f"步骤 {step.step_order} 候选人为空或超过 100 人",
                    code="APPROVAL_CANDIDATE_INVALID",
                    status_code=409,
                )
            if step.approval_mode == "ANY" and int(step.min_approvals) != 1:
                raise AppError(
                    f"步骤 {step.step_order} 的 ANY 模式门槛必须为 1",
                    code="APPROVAL_DEFINITION_INVALID",
                    status_code=400,
                )
            if step.approval_mode == "ALL" and int(step.min_approvals) > len(candidates):
                raise AppError(
                    f"步骤 {step.step_order} 的通过门槛超过候选人数",
                    code="APPROVAL_DEFINITION_INVALID",
                    status_code=400,
                )

    def publish_definition(
        self,
        *,
        definition_id: int,
        version_id: int,
        expected_lock_version: int,
    ) -> tuple[ApprovalDefinition, ApprovalDefinitionVersion]:
        definition = self.get_definition(definition_id, for_update=True)
        if definition is None:
            raise AppError("审批定义不存在", code="APPROVAL_DEFINITION_NOT_FOUND", status_code=404)
        if int(definition.lock_version) != expected_lock_version:
            raise AppError("审批定义已被其他人更新", code="VERSION_CONFLICT", status_code=409)
        version = self.get_version(version_id)
        if (
            version is None
            or int(version.definition_id) != int(definition.id)
            or version.status != "DRAFT"
        ):
            raise AppError("草稿版本不存在", code="APPROVAL_DRAFT_NOT_FOUND", status_code=404)
        self.validate_publishable(version)
        version.status = "PUBLISHED"
        version.published_by = self.ctx.user_id or None
        version.published_at = utc_now()
        definition.current_version = int(version.version)
        definition.lock_version = int(definition.lock_version) + 1
        definition.status = "ACTIVE"
        definition.updated_by = self.ctx.user_id or None
        self.session.add_all([definition, version])
        self.session.flush()
        return definition, version

    def retire_definition(
        self, definition_id: int, expected_lock_version: int
    ) -> ApprovalDefinition:
        definition = self.get_definition(definition_id, for_update=True)
        if definition is None:
            raise AppError("审批定义不存在", code="APPROVAL_DEFINITION_NOT_FOUND", status_code=404)
        if int(definition.lock_version) != expected_lock_version:
            raise AppError("审批定义已被其他人更新", code="VERSION_CONFLICT", status_code=409)
        definition.status = "RETIRED"
        definition.lock_version = int(definition.lock_version) + 1
        definition.updated_by = self.ctx.user_id or None
        self.session.add(definition)
        self.session.flush()
        return definition

    # Runtime task orchestration helpers.
    def published_version_for(
        self, definition: ApprovalDefinition
    ) -> ApprovalDefinitionVersion | None:
        if definition.status != "ACTIVE" or int(definition.current_version) <= 0:
            return None
        return self.session.scalars(
            select(ApprovalDefinitionVersion).where(
                ApprovalDefinitionVersion.tenant_id == self.ctx.tenant_id,
                ApprovalDefinitionVersion.definition_id == definition.id,
                ApprovalDefinitionVersion.version == definition.current_version,
                ApprovalDefinitionVersion.status == "PUBLISHED",
            )
        ).first()

    def next_step(self, *, version_id: int, after_order: int) -> ApprovalDefinitionStep | None:
        return self.session.scalars(
            select(ApprovalDefinitionStep)
            .where(
                ApprovalDefinitionStep.tenant_id == self.ctx.tenant_id,
                ApprovalDefinitionStep.version_id == version_id,
                ApprovalDefinitionStep.step_order > after_order,
            )
            .order_by(ApprovalDefinitionStep.step_order)
        ).first()

    def open_step(self, approval: ApprovalRequest, step_order: int) -> list[ApprovalTask]:
        existing = list(
            self.session.scalars(
                select(ApprovalTask).where(
                    ApprovalTask.tenant_id == self.ctx.tenant_id,
                    ApprovalTask.approval_id == approval.id,
                    ApprovalTask.round_no == approval.round_no,
                    ApprovalTask.step_order == step_order,
                )
            ).all()
        )
        if existing:
            return existing
        step = self.session.scalars(
            select(ApprovalDefinitionStep).where(
                ApprovalDefinitionStep.tenant_id == self.ctx.tenant_id,
                ApprovalDefinitionStep.version_id == approval.definition_version_id,
                ApprovalDefinitionStep.step_order == step_order,
            )
        ).first()
        if step is None:
            raise AppError("审批步骤不存在", code="APPROVAL_STEP_NOT_FOUND", status_code=409)
        candidates = self.resolve_candidates(int(step.id))
        if not candidates:
            raise AppError("审批步骤无有效候选人", code="APPROVAL_STEP_UNASSIGNED", status_code=409)
        due_at = utc_now() + timedelta(hours=int(step.sla_hours))
        tasks: list[ApprovalTask] = []
        for user_id in candidates:
            task = ApprovalTask(
                tenant_id=self.ctx.tenant_id,
                approval_id=int(approval.id),
                step_id=int(step.id),
                round_no=int(approval.round_no),
                step_order=int(step.step_order),
                assignee_user_id=user_id,
                status="PENDING",
                due_at=due_at,
            )
            self.session.add(task)
            self.session.flush()
            self.session.add(
                WorkItem(
                    tenant_id=self.ctx.tenant_id,
                    park_id=approval.park_id,
                    item_type="APPROVAL_TASK",
                    title=approval.title,
                    description=f"审批单 {approval.request_no or approval.id} · 第 {step.step_order} 步",
                    status="OPEN",
                    priority=approval.priority,
                    assignee_user_id=user_id,
                    due_at=due_at,
                    source_type="APPROVAL_TASK",
                    source_id=str(task.id),
                )
            )
            tasks.append(task)
        approval.current_step_order = int(step.step_order)
        approval.due_at = due_at
        self.session.add(approval)
        self.session.flush()
        return tasks

    def get_task(self, task_id: int, *, for_update: bool = False) -> ApprovalTask | None:
        visible_approval_ids = self._scope(select(ApprovalRequest.id))
        stmt = select(ApprovalTask).where(
            ApprovalTask.tenant_id == self.ctx.tenant_id,
            ApprovalTask.id == task_id,
            ApprovalTask.approval_id.in_(visible_approval_ids),
        )
        if for_update and self._supports_row_lock():
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def task_by_decision_key(self, idempotency_key: str) -> ApprovalTask | None:
        return self.session.scalars(
            select(ApprovalTask).where(
                ApprovalTask.tenant_id == self.ctx.tenant_id,
                ApprovalTask.idempotency_key == idempotency_key,
            )
        ).first()

    def step_for_task(self, task: ApprovalTask) -> ApprovalDefinitionStep:
        step = self.session.scalars(
            select(ApprovalDefinitionStep).where(
                ApprovalDefinitionStep.tenant_id == self.ctx.tenant_id,
                ApprovalDefinitionStep.id == task.step_id,
            )
        ).first()
        if step is None:
            raise AppError("审批步骤不存在", code="APPROVAL_STEP_NOT_FOUND", status_code=409)
        return step

    def tasks_for_step(
        self, approval_id: int, round_no: int, step_order: int
    ) -> list[ApprovalTask]:
        return list(
            self.session.scalars(
                select(ApprovalTask).where(
                    ApprovalTask.tenant_id == self.ctx.tenant_id,
                    ApprovalTask.approval_id == approval_id,
                    ApprovalTask.round_no == round_no,
                    ApprovalTask.step_order == step_order,
                )
            ).all()
        )

    def tasks_for_approval(self, approval_id: int) -> list[ApprovalTask]:
        return list(
            self.session.scalars(
                select(ApprovalTask)
                .where(
                    ApprovalTask.tenant_id == self.ctx.tenant_id,
                    ApprovalTask.approval_id == approval_id,
                )
                .order_by(ApprovalTask.round_no, ApprovalTask.step_order, ApprovalTask.id)
            ).all()
        )

    def close_task_projection(self, task: ApprovalTask, *, cancelled: bool = False) -> None:
        item = self.session.scalars(
            select(WorkItem).where(
                WorkItem.tenant_id == self.ctx.tenant_id,
                WorkItem.source_type == "APPROVAL_TASK",
                WorkItem.source_id == str(task.id),
                WorkItem.item_type == "APPROVAL_TASK",
            )
        ).first()
        if item is not None and item.status == "OPEN":
            item.status = "CANCELLED" if cancelled else "DONE"
            item.completed_at = utc_now()
            item.completed_by = self.ctx.user_id or None
            self.session.add(item)

    def active_delegation_for_task(
        self, *, task: ApprovalTask, biz_type: str, actor_user_id: int
    ) -> ApprovalDelegation | None:
        now = utc_now()
        return self.session.scalars(
            select(ApprovalDelegation).where(
                ApprovalDelegation.tenant_id == self.ctx.tenant_id,
                ApprovalDelegation.grantor_user_id == task.assignee_user_id,
                ApprovalDelegation.delegate_user_id == actor_user_id,
                ApprovalDelegation.status == "ACTIVE",
                ApprovalDelegation.starts_at <= now,
                ApprovalDelegation.ends_at >= now,
                or_(
                    ApprovalDelegation.biz_type.is_(None),
                    ApprovalDelegation.biz_type == biz_type,
                ),
            )
        ).first()

    def list_tasks(
        self,
        *,
        processed: bool,
        status: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[ApprovalTask], int]:
        now = utc_now()
        delegated = exists(
            select(ApprovalDelegation.id).where(
                ApprovalDelegation.tenant_id == self.ctx.tenant_id,
                ApprovalDelegation.grantor_user_id == ApprovalTask.assignee_user_id,
                ApprovalDelegation.delegate_user_id == self.ctx.user_id,
                ApprovalDelegation.status == "ACTIVE",
                ApprovalDelegation.starts_at <= now,
                ApprovalDelegation.ends_at >= now,
                or_(
                    ApprovalDelegation.biz_type.is_(None),
                    ApprovalDelegation.biz_type == ApprovalRequest.biz_type,
                ),
            )
        )
        stmt = (
            select(ApprovalTask)
            .join(ApprovalRequest, ApprovalRequest.id == ApprovalTask.approval_id)
            .where(ApprovalTask.tenant_id == self.ctx.tenant_id)
        )
        count_stmt = (
            select(ApprovalTask.id)
            .join(ApprovalRequest, ApprovalRequest.id == ApprovalTask.approval_id)
            .where(ApprovalTask.tenant_id == self.ctx.tenant_id)
        )
        stmt = self._scope(stmt)
        count_stmt = self._scope(count_stmt)
        if processed:
            actor_filter = or_(
                ApprovalTask.acted_by_user_id == self.ctx.user_id,
                and_(
                    ApprovalTask.assignee_user_id == self.ctx.user_id,
                    ApprovalTask.status != "PENDING",
                ),
            )
            stmt = stmt.where(actor_filter, ApprovalTask.status != "PENDING")
            count_stmt = count_stmt.where(actor_filter, ApprovalTask.status != "PENDING")
        else:
            actor_filter = or_(ApprovalTask.assignee_user_id == self.ctx.user_id, delegated)
            stmt = stmt.where(actor_filter, ApprovalTask.status == "PENDING")
            count_stmt = count_stmt.where(actor_filter, ApprovalTask.status == "PENDING")
        if status:
            stmt = stmt.where(ApprovalTask.status == status)
            count_stmt = count_stmt.where(ApprovalTask.status == status)
        rows = list(
            self.session.scalars(
                stmt.order_by(ApprovalTask.due_at, ApprovalTask.id).offset(offset).limit(limit)
            ).all()
        )
        total = int(
            self.session.scalar(select(func.count()).select_from(count_stmt.subquery())) or 0
        )
        return rows, total

    # Delegation.
    def active_user(self, user_id: int) -> User | None:
        return self.session.scalars(
            select(User).where(
                User.id == user_id,
                User.tenant_id == self.ctx.tenant_id,
                User.status == "ACTIVE",
            )
        ).first()

    def list_delegations(self, *, include_revoked: bool = True) -> list[ApprovalDelegation]:
        stmt = select(ApprovalDelegation).where(
            ApprovalDelegation.tenant_id == self.ctx.tenant_id,
            or_(
                ApprovalDelegation.grantor_user_id == self.ctx.user_id,
                ApprovalDelegation.delegate_user_id == self.ctx.user_id,
            ),
        )
        if not include_revoked:
            stmt = stmt.where(ApprovalDelegation.status == "ACTIVE")
        return list(self.session.scalars(stmt.order_by(ApprovalDelegation.id.desc())).all())

    def get_delegation(
        self, delegation_id: int, *, for_update: bool = False
    ) -> ApprovalDelegation | None:
        stmt = select(ApprovalDelegation).where(
            ApprovalDelegation.id == delegation_id,
            ApprovalDelegation.tenant_id == self.ctx.tenant_id,
            ApprovalDelegation.grantor_user_id == self.ctx.user_id,
        )
        if for_update and self._supports_row_lock():
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def validate_delegation_graph(
        self,
        *,
        grantor_user_id: int,
        delegate_user_id: int,
        biz_type: str | None,
        starts_at: datetime,
        ends_at: datetime,
    ) -> None:
        overlapping = list(
            self.session.scalars(
                select(ApprovalDelegation).where(
                    ApprovalDelegation.tenant_id == self.ctx.tenant_id,
                    ApprovalDelegation.status == "ACTIVE",
                    ApprovalDelegation.starts_at < ends_at,
                    ApprovalDelegation.ends_at > starts_at,
                    or_(
                        ApprovalDelegation.biz_type == biz_type,
                        ApprovalDelegation.biz_type.is_(None),
                        biz_type is None,
                    ),
                )
            ).all()
        )
        if any(
            int(row.grantor_user_id) == grantor_user_id
            and int(row.delegate_user_id) == delegate_user_id
            and row.biz_type == biz_type
            for row in overlapping
        ):
            raise AppError(
                "委托时间范围重复",
                code="APPROVAL_DELEGATION_OVERLAP",
                status_code=409,
            )
        graph: dict[int, set[int]] = {}
        for row in overlapping:
            graph.setdefault(int(row.grantor_user_id), set()).add(int(row.delegate_user_id))
        graph.setdefault(grantor_user_id, set()).add(delegate_user_id)
        stack = [delegate_user_id]
        visited: set[int] = set()
        while stack:
            node = stack.pop()
            if node == grantor_user_id:
                raise AppError(
                    "委托关系形成循环",
                    code="APPROVAL_DELEGATION_CYCLE",
                    status_code=409,
                )
            if node in visited:
                continue
            visited.add(node)
            stack.extend(graph.get(node, set()))

    def create_delegation(
        self,
        *,
        delegate_user_id: int,
        biz_type: str | None,
        starts_at: datetime,
        ends_at: datetime,
    ) -> ApprovalDelegation:
        self.validate_delegation_graph(
            grantor_user_id=self.ctx.user_id,
            delegate_user_id=delegate_user_id,
            biz_type=biz_type,
            starts_at=starts_at,
            ends_at=ends_at,
        )
        row = ApprovalDelegation(
            tenant_id=self.ctx.tenant_id,
            grantor_user_id=self.ctx.user_id,
            delegate_user_id=delegate_user_id,
            biz_type=biz_type,
            starts_at=starts_at,
            ends_at=ends_at,
            status="ACTIVE",
        )
        self.session.add(row)
        self.session.flush()
        return row

    def sweep_overdue(self, *, limit: int = 200) -> list[ApprovalTask]:
        now = utc_now()
        stmt = select(ApprovalTask).where(
            ApprovalTask.tenant_id == self.ctx.tenant_id,
            ApprovalTask.status == "PENDING",
            ApprovalTask.due_at < now,
            ApprovalTask.escalated_at.is_(None),
        )
        if self._supports_row_lock():
            stmt = stmt.with_for_update(skip_locked=True)
        tasks = list(self.session.scalars(stmt.order_by(ApprovalTask.due_at).limit(limit)).all())
        for task in tasks:
            task.escalated_at = now
            self.session.add(task)
            item = self.session.scalars(
                select(WorkItem).where(
                    WorkItem.tenant_id == self.ctx.tenant_id,
                    WorkItem.source_type == "APPROVAL_TASK",
                    WorkItem.source_id == str(task.id),
                    WorkItem.item_type == "APPROVAL_TASK",
                )
            ).first()
            if item is not None and item.status == "OPEN":
                item.priority = "URGENT"
                self.session.add(item)
            self.add_event(
                approval_id=int(task.approval_id),
                action="OVERDUE",
                actor_user_id=self.ctx.user_id or None,
                remark="审批任务已逾期升级",
                round_no=int(task.round_no),
                step_order=int(task.step_order),
                task_id=int(task.id),
                original_assignee_user_id=int(task.assignee_user_id),
            )
        self.session.flush()
        return tasks

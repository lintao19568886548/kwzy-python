"""Versioned approval definitions, instances, tasks, delegation and SLA orchestration."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder, bounded_audit_detail
from app.infrastructure.database.base import utc_now
from app.infrastructure.platform.number_sequence import next_number
from app.modules.lease.infrastructure.approval_adapter import LEASE_MANAGED_APPROVAL_TYPES
from app.modules.workbench.application.automation_service import WorkbenchAutomationService
from app.modules.workflow.infrastructure.approval_repository import ApprovalRepository
from app.shared.tenant_context import TenantContext


def bounded_idempotency_key(value: str, *, maximum: int = 64) -> str:
    """Preserve short keys and deterministically fingerprint keys that exceed DB limits."""
    normalized = value.strip()
    if len(normalized) <= maximum:
        return normalized
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"h:{digest[: maximum - 2]}"


class ApprovalService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.repo = ApprovalRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)
        self.events = WorkbenchAutomationService(session, ctx)

    def _has_any(self, *permissions: str) -> bool:
        return any(self.ctx.has_permission(code) for code in permissions)

    def _require_any(self, *permissions: str) -> None:
        if not self._has_any(*permissions):
            raise AppError("无操作权限", code="PERMISSION_DENIED", status_code=403)

    def list_approvals(
        self,
        *,
        status: str | None = None,
        biz_type: str | None = None,
        park_id: int | None = None,
        priority: str | None = None,
        mine: bool = False,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        self._require_any("approval:read", "approval.task.read")
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        applicant_user_id = self.ctx.user_id if mine else None
        query = {
            "status": status,
            "biz_type": biz_type,
            "park_id": park_id,
            "priority": priority,
            "applicant_user_id": applicant_user_id,
            "created_from": created_from,
            "created_to": created_to,
        }
        items = self.repo.list(
            **query,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return {
            "total": self.repo.count(**query),
            "page": page,
            "page_size": page_size,
            "items": [self._approval_dict(item) for item in items],
        }

    def get_approval(self, approval_id: int) -> dict[str, Any]:
        self._require_any("approval:read", "approval.task.read")
        approval = self.repo.get_by_id(approval_id)
        if approval is None:
            raise AppError("审批单不存在", code="APPROVAL_NOT_FOUND", status_code=404)
        result = self._approval_dict(approval)
        result["tasks"] = [
            self._task_dict(task, approval=approval)
            for task in self.repo.tasks_for_approval(approval_id)
        ]
        result["events"] = [self._event_dict(event) for event in self.repo.list_events(approval_id)]
        return result

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        if not self.ctx.has_permission("approval:write"):
            raise AppError("无审批申请权限", code="PERMISSION_DENIED", status_code=403)
        biz_type = str(data.get("biz_type") or "").strip().upper()
        if biz_type in LEASE_MANAGED_APPROVAL_TYPES:
            raise AppError(
                "租赁域审批须使用对应业务命令",
                code="APPROVAL_DOMAIN_COMMAND_REQUIRED",
                status_code=409,
            )
        biz_id = str(data.get("biz_id") or "").strip()
        title = str(data.get("title") or "").strip()
        if not biz_type or not biz_id or not title:
            raise AppError("biz_type/biz_id/title 必填", code="VALIDATION_ERROR", status_code=400)
        definition_code = str(data.get("definition_code") or "").strip().upper()
        if not definition_code:
            return self._create_legacy(data, biz_type=biz_type, biz_id=biz_id, title=title)
        supplied_idempotency_key = str(data.get("idempotency_key") or "").strip()
        if not supplied_idempotency_key:
            raise AppError("幂等键必填", code="IDEMPOTENCY_KEY_REQUIRED", status_code=400)
        idempotency_key = bounded_idempotency_key(supplied_idempotency_key)
        previous = self.repo.get_by_submission_key(idempotency_key)
        if previous is not None:
            if previous.biz_type == biz_type and previous.biz_id == biz_id:
                return self._approval_dict(previous)
            raise AppError("幂等键已用于其他申请", code="IDEMPOTENCY_CONFLICT", status_code=409)
        duplicate = self.repo.get_by_biz(biz_type, biz_id)
        if duplicate is not None:
            raise AppError("该业务已存在审批单", code="APPROVAL_DUPLICATE", status_code=409)
        definition = self.repo.get_definition_by_code(definition_code)
        if definition is None or definition.status != "ACTIVE":
            raise AppError(
                "可用审批定义不存在", code="APPROVAL_DEFINITION_NOT_FOUND", status_code=404
            )
        if definition.biz_type != biz_type:
            raise AppError(
                "审批定义与业务类型不匹配", code="APPROVAL_BIZ_TYPE_INVALID", status_code=400
            )
        requested_park = int(data["park_id"]) if data.get("park_id") is not None else None
        if definition.park_id is not None:
            if requested_park is not None and requested_park != int(definition.park_id):
                raise AppError(
                    "审批定义不适用于该园区", code="APPROVAL_PARK_INVALID", status_code=400
                )
            requested_park = int(definition.park_id)
        version = self.repo.published_version_for(definition)
        if version is None:
            raise AppError(
                "审批定义尚未发布", code="APPROVAL_DEFINITION_UNPUBLISHED", status_code=409
            )
        sequence = next_number(
            self.session,
            tenant_id=self.ctx.tenant_id,
            biz_type="APPROVAL",
            period_key=utc_now().strftime("%Y%m"),
        )
        request_no = f"AP-{utc_now():%Y%m}-{sequence:06d}"
        try:
            model = self.repo.create_native_request(
                definition_version_id=int(version.id),
                request_no=request_no,
                park_id=requested_park,
                biz_type=biz_type,
                biz_id=biz_id,
                title=title,
                applicant_user_id=self.ctx.user_id,
                remark=data.get("remark"),
                priority=str(data.get("priority") or "MEDIUM").upper(),
                snapshot_json=bounded_audit_detail(data.get("snapshot")),
                idempotency_key=idempotency_key,
            )
            self.repo.add_event(
                approval_id=int(model.id),
                action="SUBMIT",
                actor_user_id=self.ctx.user_id,
                remark=data.get("remark"),
                round_no=1,
                idempotency_key=bounded_idempotency_key(f"submit:{idempotency_key}"),
                detail_json={"definition_version_id": int(version.id)},
            )
            self.repo.open_step(model, 1)
            self.audit.record(
                action="submit",
                resource_type="APPROVAL",
                resource_id=model.id,
                park_id=model.park_id,
                detail={
                    "request_no": request_no,
                    "biz_type": biz_type,
                    "biz_id": biz_id,
                    "definition_code": definition.code,
                },
            )
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            existing = self.repo.get_by_submission_key(idempotency_key)
            if existing is not None and existing.biz_type == biz_type and existing.biz_id == biz_id:
                return self._approval_dict(existing)
            raise AppError("审批申请并发冲突", code="APPROVAL_CONFLICT", status_code=409) from exc
        return self._approval_dict(model)

    def _create_legacy(
        self, data: dict[str, Any], *, biz_type: str, biz_id: str, title: str
    ) -> dict[str, Any]:
        if self.repo.get_by_biz(biz_type, biz_id) is not None:
            raise AppError("该业务已存在审批单", code="APPROVAL_DUPLICATE", status_code=409)
        try:
            model = self.repo.create(
                park_id=int(data["park_id"]) if data.get("park_id") is not None else None,
                biz_type=biz_type,
                biz_id=biz_id,
                title=title,
                applicant_user_id=self.ctx.user_id or None,
                remark=data.get("remark"),
            )
            self.repo.add_event(
                approval_id=int(model.id),
                action="SUBMIT",
                actor_user_id=self.ctx.user_id or None,
                remark=data.get("remark"),
            )
            self.audit.record(
                action="create",
                resource_type="APPROVAL",
                resource_id=model.id,
                park_id=model.park_id,
                detail={"biz_type": biz_type, "biz_id": biz_id, "mode": "LEGACY_COMPAT"},
            )
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(
                "该业务已存在审批单", code="APPROVAL_DUPLICATE", status_code=409
            ) from exc
        return self._approval_dict(model)

    def decide(self, approval_id: int, *, approve: bool, remark: str | None = None) -> dict:
        """Compatibility decision command for versionless approvals only."""

        if not self.ctx.has_permission("approval:decide"):
            raise AppError("无审批决定权限", code="PERMISSION_DENIED", status_code=403)
        model = self.repo.get_by_id(approval_id, for_update=True)
        if model is None:
            raise AppError("审批单不存在", code="APPROVAL_NOT_FOUND", status_code=404)
        if model.biz_type in LEASE_MANAGED_APPROVAL_TYPES or model.compatibility_mode == "NATIVE":
            raise AppError(
                "该审批须使用对应业务或任务命令",
                code="APPROVAL_DOMAIN_COMMAND_REQUIRED",
                status_code=409,
            )
        if model.status != "PENDING":
            raise AppError("非待审状态", code="APPROVAL_STATUS_INVALID", status_code=400)
        model.status = "APPROVED" if approve else "REJECTED"
        model.approver_user_id = self.ctx.user_id or None
        model.decision_remark = remark
        model.completed_at = utc_now()
        model.lock_version = int(model.lock_version) + 1
        self.repo.save(model)
        self.repo.add_event(
            approval_id=int(model.id),
            action="APPROVE" if approve else "REJECT",
            actor_user_id=self.ctx.user_id or None,
            remark=remark,
        )
        self.audit.record(
            action="approve" if approve else "reject",
            resource_type="APPROVAL",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"mode": "LEGACY_COMPAT"},
        )
        self.session.commit()
        return self._approval_dict(model)

    def decide_task(
        self,
        task_id: int,
        *,
        action: str,
        remark: str | None,
        idempotency_key: str,
        expected_version: int,
        override_reason: str | None,
    ) -> dict[str, Any]:
        if not self.ctx.has_permission("approval.task.decide"):
            raise AppError("无审批任务决定权限", code="PERMISSION_DENIED", status_code=403)
        normalized_action = action.strip().upper()
        if normalized_action not in {"APPROVE", "REJECT", "RETURN"}:
            raise AppError("审批动作无效", code="APPROVAL_ACTION_INVALID", status_code=400)
        if normalized_action in {"REJECT", "RETURN"} and not (remark or "").strip():
            raise AppError(
                "驳回或退回必须填写原因", code="APPROVAL_REASON_REQUIRED", status_code=400
            )
        key = idempotency_key.strip()
        if not key:
            raise AppError("幂等键必填", code="IDEMPOTENCY_KEY_REQUIRED", status_code=400)
        previous = self.repo.task_by_decision_key(key)
        expected_status = {"APPROVE": "APPROVED", "REJECT": "REJECTED", "RETURN": "RETURNED"}[
            normalized_action
        ]
        if previous is not None:
            if int(previous.id) != int(task_id) or previous.status != expected_status:
                raise AppError("幂等键已用于其他决定", code="IDEMPOTENCY_CONFLICT", status_code=409)
            approval = self.repo.get_by_id(int(previous.approval_id))
            if approval is None:
                raise AppError("审批单不存在", code="APPROVAL_NOT_FOUND", status_code=404)
            return self._approval_dict(approval)

        initial_task = self.repo.get_task(task_id)
        if initial_task is None:
            raise AppError("审批任务不存在", code="APPROVAL_TASK_NOT_FOUND", status_code=404)
        approval = self.repo.get_by_id(int(initial_task.approval_id), for_update=True)
        if approval is None:
            raise AppError("审批单不存在", code="APPROVAL_NOT_FOUND", status_code=404)
        if int(approval.lock_version) != int(expected_version):
            raise AppError("审批状态已变化，请刷新", code="VERSION_CONFLICT", status_code=409)
        task = self.repo.get_task(task_id, for_update=True)
        if task is None or task.status != "PENDING":
            raise AppError("任务已被处理", code="APPROVAL_TASK_CONFLICT", status_code=409)
        if (
            approval.status != "PENDING"
            or int(task.round_no) != int(approval.round_no)
            or int(task.step_order) != int(approval.current_step_order or 0)
        ):
            raise AppError("审批状态已变化，请刷新", code="APPROVAL_TASK_CONFLICT", status_code=409)
        delegation = None
        if int(task.assignee_user_id) != int(self.ctx.user_id):
            delegation = self.repo.active_delegation_for_task(
                task=task,
                biz_type=approval.biz_type,
                actor_user_id=self.ctx.user_id,
            )
            if delegation is None:
                raise AppError("该任务不可处理", code="PERMISSION_DENIED", status_code=403)
        self_approval = int(approval.applicant_user_id or 0) == int(self.ctx.user_id)
        if self_approval:
            if not self.ctx.has_permission("approval.task.override_self"):
                raise AppError(
                    "申请人与审批人必须分离", code="SELF_APPROVAL_FORBIDDEN", status_code=403
                )
            if not (override_reason or "").strip():
                raise AppError(
                    "自审批越权必须填写原因",
                    code="APPROVAL_OVERRIDE_REASON_REQUIRED",
                    status_code=400,
                )

        now = utc_now()
        task.status = expected_status
        task.decided_at = now
        task.decision_remark = remark
        task.acted_by_user_id = self.ctx.user_id
        task.delegation_id = int(delegation.id) if delegation is not None else None
        task.idempotency_key = key
        self.session.add(task)
        self.repo.close_task_projection(task)
        self.repo.add_event(
            approval_id=int(approval.id),
            action=normalized_action,
            actor_user_id=self.ctx.user_id,
            remark=remark,
            round_no=int(task.round_no),
            step_order=int(task.step_order),
            task_id=int(task.id),
            original_assignee_user_id=int(task.assignee_user_id),
            idempotency_key=key,
            detail_json={
                "delegation_id": int(delegation.id) if delegation is not None else None,
                "override_reason": override_reason if self_approval else None,
            },
        )

        if normalized_action == "APPROVE":
            step = self.repo.step_for_task(task)
            step_tasks = self.repo.tasks_for_step(
                int(approval.id), int(task.round_no), int(task.step_order)
            )
            approved_count = sum(1 for row in step_tasks if row.status == "APPROVED")
            if approved_count >= int(step.min_approvals):
                for sibling in step_tasks:
                    if sibling.status == "PENDING":
                        sibling.status = "SKIPPED"
                        sibling.decided_at = now
                        self.session.add(sibling)
                        self.repo.close_task_projection(sibling, cancelled=True)
                next_step = self.repo.next_step(
                    version_id=int(approval.definition_version_id),
                    after_order=int(step.step_order),
                )
                if next_step is None:
                    approval.status = "APPROVED"
                    approval.completed_at = now
                    approval.due_at = None
                    approval.approver_user_id = self.ctx.user_id
                    approval.decision_remark = remark
                else:
                    self.repo.open_step(approval, int(next_step.step_order))
        else:
            approval.status = "REJECTED" if normalized_action == "REJECT" else "RETURNED"
            approval.completed_at = now if normalized_action == "REJECT" else None
            approval.due_at = None
            approval.approver_user_id = self.ctx.user_id
            approval.decision_remark = remark
            for pending in self.repo.tasks_for_approval(int(approval.id)):
                if pending.status == "PENDING":
                    pending.status = "CANCELLED"
                    pending.decided_at = now
                    self.session.add(pending)
                    self.repo.close_task_projection(pending, cancelled=True)

        approval.lock_version = int(approval.lock_version) + 1
        self.repo.save(approval)
        audit_detail = {
            "task_id": int(task.id),
            "action": normalized_action,
            "round_no": int(task.round_no),
            "step_order": int(task.step_order),
            "original_assignee_user_id": int(task.assignee_user_id),
            "delegated": delegation is not None,
        }
        self.audit.record(
            action="decision",
            resource_type="APPROVAL",
            resource_id=approval.id,
            park_id=approval.park_id,
            detail=audit_detail,
        )
        if self_approval:
            self.audit.record(
                action="approval_override",
                resource_type="APPROVAL",
                resource_id=approval.id,
                park_id=approval.park_id,
                detail={"task_id": int(task.id), "reason": override_reason},
            )
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(
                "审批决定并发冲突", code="APPROVAL_TASK_CONFLICT", status_code=409
            ) from exc
        return self._approval_dict(approval)

    def withdraw(
        self,
        approval_id: int,
        *,
        remark: str | None = None,
        expected_version: int | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        if not self.ctx.has_permission("approval:write"):
            raise AppError("无审批撤回权限", code="PERMISSION_DENIED", status_code=403)
        if idempotency_key:
            idempotency_key = bounded_idempotency_key(idempotency_key)
            previous = self.repo.event_by_key(idempotency_key)
            if previous is not None:
                if int(previous.approval_id) != approval_id or previous.action != "WITHDRAW":
                    raise AppError(
                        "幂等键已用于其他命令", code="IDEMPOTENCY_CONFLICT", status_code=409
                    )
                model = self.repo.get_by_id(approval_id)
                if model is None:
                    raise AppError("审批单不存在", code="APPROVAL_NOT_FOUND", status_code=404)
                return self._approval_dict(model)
        model = self.repo.get_by_id(approval_id, for_update=True)
        if model is None:
            raise AppError("审批单不存在", code="APPROVAL_NOT_FOUND", status_code=404)
        if model.biz_type in LEASE_MANAGED_APPROVAL_TYPES:
            raise AppError(
                "租赁域审批须使用对应业务命令",
                code="APPROVAL_DOMAIN_COMMAND_REQUIRED",
                status_code=409,
            )
        if model.status != "PENDING":
            raise AppError("仅待审可撤回", code="APPROVAL_STATUS_INVALID", status_code=400)
        if expected_version is not None and int(model.lock_version) != int(expected_version):
            raise AppError("审批状态已变化，请刷新", code="VERSION_CONFLICT", status_code=409)
        if int(model.applicant_user_id or 0) != int(self.ctx.user_id or 0) and (
            model.compatibility_mode == "NATIVE" or not self.ctx.has_permission("approval:decide")
        ):
            raise AppError("仅申请人可撤回", code="PERMISSION_DENIED", status_code=403)
        now = utc_now()
        model.status = "WITHDRAWN"
        model.completed_at = now
        model.due_at = None
        model.lock_version = int(model.lock_version) + 1
        self.repo.save(model)
        for task in self.repo.tasks_for_approval(int(model.id)):
            if task.status == "PENDING":
                task.status = "CANCELLED"
                task.decided_at = now
                self.session.add(task)
                self.repo.close_task_projection(task, cancelled=True)
        self.repo.add_event(
            approval_id=int(model.id),
            action="WITHDRAW",
            actor_user_id=self.ctx.user_id or None,
            remark=remark,
            round_no=int(model.round_no),
            idempotency_key=idempotency_key,
        )
        self.audit.record(
            action="withdraw",
            resource_type="APPROVAL",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"round_no": int(model.round_no)},
        )
        self.session.commit()
        return self._approval_dict(model)

    def resubmit(
        self,
        approval_id: int,
        *,
        remark: str | None,
        expected_version: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if not self.ctx.has_permission("approval:write"):
            raise AppError("无审批申请权限", code="PERMISSION_DENIED", status_code=403)
        previous = self.repo.event_by_key(idempotency_key)
        if previous is not None:
            if int(previous.approval_id) != approval_id or previous.action != "RESUBMIT":
                raise AppError("幂等键已用于其他命令", code="IDEMPOTENCY_CONFLICT", status_code=409)
            current = self.repo.get_by_id(approval_id)
            if current is None:
                raise AppError("审批单不存在", code="APPROVAL_NOT_FOUND", status_code=404)
            return self._approval_dict(current)
        approval = self.repo.get_by_id(approval_id, for_update=True)
        if approval is None:
            raise AppError("审批单不存在", code="APPROVAL_NOT_FOUND", status_code=404)
        if approval.compatibility_mode != "NATIVE":
            raise AppError(
                "兼容审批不支持重新提交", code="APPROVAL_COMMAND_UNSUPPORTED", status_code=409
            )
        if approval.status != "RETURNED":
            raise AppError(
                "仅已退回审批可重新提交", code="APPROVAL_STATUS_INVALID", status_code=409
            )
        if int(approval.applicant_user_id or 0) != self.ctx.user_id:
            raise AppError("仅申请人可重新提交", code="PERMISSION_DENIED", status_code=403)
        if int(approval.lock_version) != int(expected_version):
            raise AppError("审批状态已变化，请刷新", code="VERSION_CONFLICT", status_code=409)
        approval.status = "PENDING"
        approval.round_no = int(approval.round_no) + 1
        approval.current_step_order = None
        approval.completed_at = None
        approval.decision_remark = None
        approval.lock_version = int(approval.lock_version) + 1
        approval.submitted_at = utc_now()
        self.repo.save(approval)
        self.repo.add_event(
            approval_id=int(approval.id),
            action="RESUBMIT",
            actor_user_id=self.ctx.user_id,
            remark=remark,
            round_no=int(approval.round_no),
            idempotency_key=idempotency_key,
        )
        self.repo.open_step(approval, 1)
        self.audit.record(
            action="resubmit",
            resource_type="APPROVAL",
            resource_id=approval.id,
            park_id=approval.park_id,
            detail={"round_no": int(approval.round_no)},
        )
        self.session.commit()
        return self._approval_dict(approval)

    def history(self, approval_id: int) -> list[dict]:
        self._require_any("approval:read", "approval.task.read")
        model = self.repo.get_by_id(approval_id)
        if model is None:
            raise AppError("审批单不存在", code="APPROVAL_NOT_FOUND", status_code=404)
        return [self._event_dict(event) for event in self.repo.list_events(approval_id)]

    # Definition commands.
    def list_definitions(
        self,
        *,
        status: str | None,
        biz_type: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        self._require_any("approval.definition.read", "approval.definition.write")
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        rows, total = self.repo.list_definitions(
            status=status,
            biz_type=biz_type,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return {
            "items": [self._definition_dict(row, include_versions=False) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_definition(self, definition_id: int) -> dict[str, Any]:
        self._require_any("approval.definition.read", "approval.definition.write")
        row = self.repo.get_definition(definition_id)
        if row is None:
            raise AppError("审批定义不存在", code="APPROVAL_DEFINITION_NOT_FOUND", status_code=404)
        return self._definition_dict(row, include_versions=True)

    def create_definition(self, data: dict[str, Any]) -> dict[str, Any]:
        if not self.ctx.has_permission("approval.definition.write"):
            raise AppError("无审批定义管理权限", code="PERMISSION_DENIED", status_code=403)
        code = str(data.get("code") or "").strip().upper()
        name = str(data.get("name") or "").strip()
        biz_type = str(data.get("biz_type") or "").strip().upper()
        if not code or not name or not biz_type:
            raise AppError("code/name/biz_type 必填", code="VALIDATION_ERROR", status_code=400)
        try:
            definition, version = self.repo.create_definition(
                code=code,
                name=name,
                biz_type=biz_type,
                park_id=data.get("park_id"),
                description=data.get("description"),
                steps=data.get("steps") or [],
            )
            self.audit.record(
                action="create",
                resource_type="APPROVAL_DEFINITION",
                resource_id=definition.id,
                park_id=definition.park_id,
                detail={"code": code, "version": int(version.version)},
            )
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(
                "审批定义编码已存在", code="APPROVAL_DEFINITION_DUPLICATE", status_code=409
            ) from exc
        return self._definition_dict(definition, include_versions=True)

    def create_draft(self, definition_id: int, *, expected_lock_version: int) -> dict[str, Any]:
        if not self.ctx.has_permission("approval.definition.write"):
            raise AppError("无审批定义管理权限", code="PERMISSION_DENIED", status_code=403)
        definition = self.repo.get_definition(definition_id, for_update=True)
        if definition is None:
            raise AppError("审批定义不存在", code="APPROVAL_DEFINITION_NOT_FOUND", status_code=404)
        if int(definition.lock_version) != expected_lock_version:
            raise AppError("审批定义已被其他人更新", code="VERSION_CONFLICT", status_code=409)
        draft = self.repo.create_draft_copy(definition)
        definition.lock_version = int(definition.lock_version) + 1
        definition.updated_by = self.ctx.user_id
        self.repo.save_definition(definition)
        self.audit.record(
            action="draft",
            resource_type="APPROVAL_DEFINITION",
            resource_id=definition.id,
            park_id=definition.park_id,
            detail={"version": int(draft.version)},
        )
        self.session.commit()
        return self._definition_dict(definition, include_versions=True)

    def update_definition(self, definition_id: int, data: dict[str, Any]) -> dict[str, Any]:
        if not self.ctx.has_permission("approval.definition.write"):
            raise AppError("无审批定义管理权限", code="PERMISSION_DENIED", status_code=403)
        definition = self.repo.get_definition(definition_id, for_update=True)
        if definition is None:
            raise AppError("审批定义不存在", code="APPROVAL_DEFINITION_NOT_FOUND", status_code=404)
        if int(definition.lock_version) != int(data["expected_lock_version"]):
            raise AppError("审批定义已被其他人更新", code="VERSION_CONFLICT", status_code=409)
        draft = self.repo.get_draft(definition_id)
        if draft is None:
            raise AppError("请先创建草稿版本", code="APPROVAL_DRAFT_NOT_FOUND", status_code=409)
        if data.get("name") is not None:
            definition.name = str(data["name"]).strip()
        if "description" in data:
            definition.description = data.get("description")
        if data.get("steps") is not None:
            self.repo.replace_draft_steps(draft, data["steps"])
        definition.lock_version = int(definition.lock_version) + 1
        definition.updated_by = self.ctx.user_id
        self.repo.save_definition(definition)
        self.audit.record(
            action="update_draft",
            resource_type="APPROVAL_DEFINITION",
            resource_id=definition.id,
            park_id=definition.park_id,
            detail={"version": int(draft.version)},
        )
        self.session.commit()
        return self._definition_dict(definition, include_versions=True)

    def publish_definition(
        self,
        definition_id: int,
        *,
        version_id: int,
        expected_lock_version: int,
    ) -> dict[str, Any]:
        if not self.ctx.has_permission("approval.definition.write"):
            raise AppError("无审批定义管理权限", code="PERMISSION_DENIED", status_code=403)
        definition, version = self.repo.publish_definition(
            definition_id=definition_id,
            version_id=version_id,
            expected_lock_version=expected_lock_version,
        )
        self.audit.record(
            action="publish",
            resource_type="APPROVAL_DEFINITION",
            resource_id=definition.id,
            park_id=definition.park_id,
            detail={"version": int(version.version)},
        )
        self.session.commit()
        return self._definition_dict(definition, include_versions=True)

    def retire_definition(
        self, definition_id: int, *, expected_lock_version: int
    ) -> dict[str, Any]:
        if not self.ctx.has_permission("approval.definition.write"):
            raise AppError("无审批定义管理权限", code="PERMISSION_DENIED", status_code=403)
        definition = self.repo.retire_definition(definition_id, expected_lock_version)
        self.audit.record(
            action="retire",
            resource_type="APPROVAL_DEFINITION",
            resource_id=definition.id,
            park_id=definition.park_id,
            detail={"code": definition.code},
        )
        self.session.commit()
        return self._definition_dict(definition, include_versions=True)

    # Tasks, delegation and SLA.
    def list_tasks(
        self,
        *,
        processed: bool,
        status: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        if not self.ctx.has_permission("approval.task.read"):
            raise AppError("无审批任务查看权限", code="PERMISSION_DENIED", status_code=403)
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        rows, total = self.repo.list_tasks(
            processed=processed,
            status=status,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return {
            "items": [self._task_dict(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def list_delegations(self) -> list[dict[str, Any]]:
        if not self.ctx.has_permission("approval.delegation.manage"):
            raise AppError("无审批委托权限", code="PERMISSION_DENIED", status_code=403)
        return [self._delegation_dict(row) for row in self.repo.list_delegations()]

    def create_delegation(self, data: dict[str, Any]) -> dict[str, Any]:
        if not self.ctx.has_permission("approval.delegation.manage"):
            raise AppError("无审批委托权限", code="PERMISSION_DENIED", status_code=403)
        delegate_user_id = int(data["delegate_user_id"])
        if delegate_user_id == self.ctx.user_id:
            raise AppError("不可委托给自己", code="APPROVAL_DELEGATION_SELF", status_code=400)
        if self.repo.active_user(delegate_user_id) is None:
            raise AppError("受托人无效", code="APPROVAL_DELEGATE_INVALID", status_code=400)
        starts_at = data["starts_at"]
        ends_at = data["ends_at"]
        if ends_at <= starts_at:
            raise AppError("委托结束时间必须晚于开始时间", code="VALIDATION_ERROR", status_code=400)
        row = self.repo.create_delegation(
            delegate_user_id=delegate_user_id,
            biz_type=(str(data.get("biz_type") or "").strip().upper() or None),
            starts_at=starts_at,
            ends_at=ends_at,
        )
        self.audit.record(
            action="create",
            resource_type="APPROVAL_DELEGATION",
            resource_id=row.id,
            detail={
                "delegate_user_id": delegate_user_id,
                "biz_type": row.biz_type,
                "starts_at": starts_at,
                "ends_at": ends_at,
            },
        )
        self.session.commit()
        return self._delegation_dict(row)

    def revoke_delegation(self, delegation_id: int) -> dict[str, Any]:
        if not self.ctx.has_permission("approval.delegation.manage"):
            raise AppError("无审批委托权限", code="PERMISSION_DENIED", status_code=403)
        row = self.repo.get_delegation(delegation_id, for_update=True)
        if row is None:
            raise AppError("委托不存在", code="APPROVAL_DELEGATION_NOT_FOUND", status_code=404)
        if row.status == "ACTIVE":
            row.status = "REVOKED"
            row.revoked_at = utc_now()
            row.revoked_by = self.ctx.user_id
            self.session.add(row)
            self.audit.record(
                action="revoke",
                resource_type="APPROVAL_DELEGATION",
                resource_id=row.id,
                detail={"delegate_user_id": int(row.delegate_user_id)},
            )
            self.session.commit()
        return self._delegation_dict(row)

    def sweep_overdue(self, *, limit: int) -> dict[str, Any]:
        if not self.ctx.has_permission("approval.definition.write"):
            raise AppError("无审批超时处理权限", code="PERMISSION_DENIED", status_code=403)
        tasks = self.repo.sweep_overdue(limit=min(max(limit, 1), 500))
        for task in tasks:
            approval = self.repo.get_by_id(task.approval_id)
            park_id = (
                int(approval.park_id)
                if approval is not None and approval.park_id is not None
                else None
            )
            self.events.emit_event(
                event_type="APPROVAL_TASK_OVERDUE",
                source_type="APPROVAL_TASK",
                source_id=str(task.id),
                idempotency_key=f"approval-task-overdue:{task.id}",
                park_id=park_id,
                payload={
                    "title": "审批任务已超时",
                    "description": "审批任务需要及时处理",
                    "priority": "URGENT",
                    "assignee_user_id": int(task.assignee_user_id),
                    "deep_link": "/approvals",
                    "park_id": park_id,
                },
                commit=False,
                enforce_permission=False,
            )
        if tasks:
            self.audit.record(
                action="sweep_overdue",
                resource_type="APPROVAL_TASK",
                resource_id=None,
                detail={"count": len(tasks), "task_ids": [int(row.id) for row in tasks]},
            )
        self.session.commit()
        return {"escalated": len(tasks), "task_ids": [int(row.id) for row in tasks]}

    def _approval_dict(self, model) -> dict[str, Any]:
        return {
            "id": int(model.id),
            "request_no": model.request_no,
            "park_id": model.park_id,
            "biz_type": model.biz_type,
            "biz_id": model.biz_id,
            "title": model.title,
            "status": model.status,
            "priority": model.priority,
            "applicant_user_id": model.applicant_user_id,
            "approver_user_id": model.approver_user_id,
            "remark": model.remark,
            "decision_remark": model.decision_remark,
            "definition_version_id": model.definition_version_id,
            "current_step_order": model.current_step_order,
            "round_no": int(model.round_no),
            "due_at": model.due_at.isoformat() if model.due_at else None,
            "submitted_at": model.submitted_at.isoformat() if model.submitted_at else None,
            "completed_at": model.completed_at.isoformat() if model.completed_at else None,
            "snapshot": model.snapshot_json,
            "lock_version": int(model.lock_version),
            "compatibility_mode": model.compatibility_mode,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        }

    def _event_dict(self, event) -> dict[str, Any]:
        return {
            "id": int(event.id),
            "action": event.action,
            "actor_user_id": event.actor_user_id,
            "remark": event.remark,
            "round_no": int(event.round_no),
            "step_order": event.step_order,
            "task_id": event.task_id,
            "original_assignee_user_id": event.original_assignee_user_id,
            "detail": event.detail_json,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }

    def _task_dict(self, task, *, approval=None) -> dict[str, Any]:
        approval = approval or self.repo.get_by_id(int(task.approval_id))
        if approval is None:
            raise AppError("审批单不存在", code="APPROVAL_NOT_FOUND", status_code=404)
        return {
            "id": int(task.id),
            "approval_id": int(task.approval_id),
            "request_no": approval.request_no,
            "title": approval.title,
            "biz_type": approval.biz_type,
            "biz_id": approval.biz_id,
            "park_id": approval.park_id,
            "priority": approval.priority,
            "approval_status": approval.status,
            "approval_lock_version": int(approval.lock_version),
            "round_no": int(task.round_no),
            "step_order": int(task.step_order),
            "assignee_user_id": int(task.assignee_user_id),
            "status": task.status,
            "due_at": task.due_at.isoformat() if task.due_at else None,
            "decided_at": task.decided_at.isoformat() if task.decided_at else None,
            "acted_by_user_id": task.acted_by_user_id,
            "delegation_id": task.delegation_id,
            "escalated_at": task.escalated_at.isoformat() if task.escalated_at else None,
        }

    def _definition_dict(self, definition, *, include_versions: bool) -> dict[str, Any]:
        result = {
            "id": int(definition.id),
            "code": definition.code,
            "name": definition.name,
            "biz_type": definition.biz_type,
            "park_id": definition.park_id,
            "status": definition.status,
            "current_version": int(definition.current_version),
            "lock_version": int(definition.lock_version),
            "description": definition.description,
            "created_at": definition.created_at.isoformat() if definition.created_at else None,
            "updated_at": definition.updated_at.isoformat() if definition.updated_at else None,
        }
        if include_versions:
            versions = []
            for version in self.repo.list_versions(int(definition.id)):
                steps = []
                for step in self.repo.definition_steps(int(version.id)):
                    steps.append(
                        {
                            "id": int(step.id),
                            "step_order": int(step.step_order),
                            "name": step.name,
                            "approval_mode": step.approval_mode,
                            "min_approvals": int(step.min_approvals),
                            "sla_hours": int(step.sla_hours),
                            "assignees": [
                                {
                                    "user_id": row.user_id,
                                    "role_id": row.role_id,
                                }
                                for row in self.repo.step_assignees(int(step.id))
                            ],
                        }
                    )
                versions.append(
                    {
                        "id": int(version.id),
                        "version": int(version.version),
                        "status": version.status,
                        "published_at": version.published_at.isoformat()
                        if version.published_at
                        else None,
                        "steps": steps,
                    }
                )
            result["versions"] = versions
        return result

    @staticmethod
    def _delegation_dict(row) -> dict[str, Any]:
        return {
            "id": int(row.id),
            "grantor_user_id": int(row.grantor_user_id),
            "delegate_user_id": int(row.delegate_user_id),
            "biz_type": row.biz_type,
            "starts_at": row.starts_at.isoformat(),
            "ends_at": row.ends_at.isoformat(),
            "status": row.status,
            "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        }

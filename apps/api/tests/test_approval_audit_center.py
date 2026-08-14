"""Approval/audit-center lifecycle, security and integrity regression tests."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.audit import AuditLog
from app.infrastructure.database.models.identity import Tenant, User
from app.infrastructure.database.models.workbench import WorkItem
from app.infrastructure.database.models.workflow import ApprovalTask
from app.shared.tenant_context import ParkScopeMode, TenantContext


def _headers(user_id: int, username: str, permissions: list[str]) -> dict[str, str]:
    token = create_access_token(
        subject=username,
        claims={
            "uid": user_id,
            "tenant_id": 1,
            "permissions": permissions,
            "park_ids": [],
            "park_scope_mode": "ALL",
            "tv": 0,
        },
    )
    return {"Authorization": f"Bearer {token}"}


def _seed_users(db_session: Session) -> tuple[User, User]:
    admin = db_session.get(User, 1)
    assert admin is not None
    approver = User(
        tenant_id=1,
        username="approval-one",
        password_hash=admin.password_hash,
        real_name="审批人一",
        status="ACTIVE",
    )
    delegate_source = User(
        tenant_id=1,
        username="approval-two",
        password_hash=admin.password_hash,
        real_name="审批人二",
        status="ACTIVE",
    )
    db_session.add_all([approver, delegate_source])
    db_session.commit()
    db_session.refresh(approver)
    db_session.refresh(delegate_source)
    return approver, delegate_source


def _publish_definition(client, headers, *, code: str, biz_type: str, steps: list[dict]):
    created = client.post(
        "/api/v1/approval-definitions",
        headers=headers,
        json={
            "code": code,
            "name": f"{code} 审批",
            "biz_type": biz_type,
            "steps": steps,
        },
    )
    assert created.status_code == 200, created.text
    definition = created.json()["data"]
    draft = next(row for row in definition["versions"] if row["status"] == "DRAFT")
    published = client.post(
        f"/api/v1/approval-definitions/{definition['id']}/publish",
        headers=headers,
        json={"version_id": draft["id"], "expected_lock_version": 0},
    )
    assert published.status_code == 200, published.text
    return published.json()["data"]


def test_multistep_delegated_decision_and_idempotent_retry(client, db_session: Session) -> None:
    first, second = _seed_users(db_session)
    admin_headers = _headers(1, "admin", ["*"])
    first_headers = _headers(
        int(first.id), first.username, ["approval.task.read", "approval.task.decide"]
    )
    second_headers = _headers(
        int(second.id),
        second.username,
        ["approval.task.read", "approval.task.decide", "approval.delegation.manage"],
    )
    _publish_definition(
        client,
        admin_headers,
        code="EXPENSE_TWO_STEP",
        biz_type="EXPENSE",
        steps=[
            {
                "step_order": 1,
                "name": "园区复核",
                "approval_mode": "ANY",
                "min_approvals": 1,
                "sla_hours": 24,
                "assignees": [{"user_id": int(first.id)}],
            },
            {
                "step_order": 2,
                "name": "财务复核",
                "approval_mode": "ANY",
                "min_approvals": 1,
                "sla_hours": 24,
                "assignees": [{"user_id": int(second.id)}],
            },
        ],
    )
    submitted = client.post(
        "/api/v1/approvals",
        headers=admin_headers,
        json={
            "definition_code": "EXPENSE_TWO_STEP",
            "biz_type": "EXPENSE",
            "biz_id": "EXP-1001",
            "title": "费用审批 1001",
            "priority": "HIGH",
            "snapshot": {"amount": "1200.00", "phone": "13800138000", "password": "never"},
            "idempotency_key": "submit-expense-1001",
        },
    )
    assert submitted.status_code == 200, submitted.text
    approval = submitted.json()["data"]
    assert approval["status"] == "PENDING"
    assert approval["current_step_order"] == 1

    first_inbox = client.get("/api/v1/approval-tasks", headers=first_headers)
    assert first_inbox.status_code == 200, first_inbox.text
    first_task = first_inbox.json()["data"]["items"][0]
    first_decision = client.post(
        f"/api/v1/approval-tasks/{first_task['id']}/decide",
        headers=first_headers,
        json={
            "action": "APPROVE",
            "remark": "园区通过",
            "expected_version": 0,
            "idempotency_key": "decision-expense-1001-step1",
        },
    )
    assert first_decision.status_code == 200, first_decision.text
    assert first_decision.json()["data"]["current_step_order"] == 2
    assert first_decision.json()["data"]["lock_version"] == 1

    delegated = client.post(
        "/api/v1/approval-delegations",
        headers=second_headers,
        json={
            "delegate_user_id": int(first.id),
            "biz_type": "EXPENSE",
            "starts_at": (utc_now() - timedelta(minutes=1)).isoformat(),
            "ends_at": (utc_now() + timedelta(days=1)).isoformat(),
        },
    )
    assert delegated.status_code == 200, delegated.text

    delegated_inbox = client.get("/api/v1/approval-tasks", headers=first_headers)
    assert delegated_inbox.status_code == 200, delegated_inbox.text
    second_task = next(
        row
        for row in delegated_inbox.json()["data"]["items"]
        if row["step_order"] == 2
    )
    final = client.post(
        f"/api/v1/approval-tasks/{second_task['id']}/decide",
        headers=first_headers,
        json={
            "action": "APPROVE",
            "remark": "受托通过",
            "expected_version": 1,
            "idempotency_key": "decision-expense-1001-step2",
        },
    )
    assert final.status_code == 200, final.text
    assert final.json()["data"]["status"] == "APPROVED"
    assert final.json()["data"]["lock_version"] == 2

    future_filtered = client.get(
        "/api/v1/approvals",
        headers=admin_headers,
        params={"created_from": "2099-01-01T00:00:00Z", "biz_type": "EXPENSE"},
    )
    assert future_filtered.status_code == 200, future_filtered.text
    assert future_filtered.json()["data"]["total"] == 0

    retry = client.post(
        f"/api/v1/approval-tasks/{second_task['id']}/decide",
        headers=first_headers,
        json={
            "action": "APPROVE",
            "remark": "受托通过",
            "expected_version": 1,
            "idempotency_key": "decision-expense-1001-step2",
        },
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["data"]["lock_version"] == 2

    detail = client.get(f"/api/v1/approvals/{approval['id']}", headers=admin_headers)
    assert detail.status_code == 200
    task = next(row for row in detail.json()["data"]["tasks"] if row["step_order"] == 2)
    assert task["acted_by_user_id"] == int(first.id)
    assert task["assignee_user_id"] == int(second.id)
    assert task["delegation_id"] == delegated.json()["data"]["id"]


def test_self_approval_requires_permission_and_reason(client) -> None:
    headers = _headers(1, "admin", ["*"])
    _publish_definition(
        client,
        headers,
        code="SELF_GUARD",
        biz_type="SELF_TEST",
        steps=[
            {
                "step_order": 1,
                "name": "负责人审批",
                "approval_mode": "ANY",
                "min_approvals": 1,
                "sla_hours": 4,
                "assignees": [{"user_id": 1}],
            }
        ],
    )
    submitted = client.post(
        "/api/v1/approvals",
        headers=headers,
        json={
            "definition_code": "SELF_GUARD",
            "biz_type": "SELF_TEST",
            "biz_id": "SELF-1",
            "title": "自审批门禁",
            "idempotency_key": "submit-self-guard-1",
        },
    )
    assert submitted.status_code == 200, submitted.text
    task = client.get("/api/v1/approval-tasks", headers=headers).json()["data"]["items"][0]
    denied = client.post(
        f"/api/v1/approval-tasks/{task['id']}/decide",
        headers=headers,
        json={
            "action": "APPROVE",
            "expected_version": 0,
            "idempotency_key": "decision-self-guard-1",
        },
    )
    assert denied.status_code == 400, denied.text
    assert denied.json()["code"] == "APPROVAL_OVERRIDE_REASON_REQUIRED"
    accepted = client.post(
        f"/api/v1/approval-tasks/{task['id']}/decide",
        headers=headers,
        json={
            "action": "APPROVE",
            "expected_version": 0,
            "idempotency_key": "decision-self-guard-1",
            "override_reason": "仅测试单用户职责分离门禁",
        },
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["data"]["status"] == "APPROVED"


def test_all_threshold_return_resubmit_and_sla_escalation(
    client, db_session: Session
) -> None:
    """Exercise state-machine branches that a straight-through happy path cannot cover."""

    first, second = _seed_users(db_session)
    admin_headers = _headers(1, "admin", ["*"])
    first_headers = _headers(
        int(first.id), first.username, ["approval.task.read", "approval.task.decide"]
    )
    second_headers = _headers(
        int(second.id), second.username, ["approval.task.read", "approval.task.decide"]
    )
    _publish_definition(
        client,
        admin_headers,
        code="ALL_THRESHOLD",
        biz_type="BUDGET",
        steps=[
            {
                "step_order": 1,
                "name": "双人会签",
                "approval_mode": "ALL",
                "min_approvals": 2,
                "sla_hours": 1,
                "assignees": [
                    {"user_id": int(first.id)},
                    {"user_id": int(second.id)},
                ],
            }
        ],
    )
    submitted = client.post(
        "/api/v1/approvals",
        headers=admin_headers,
        json={
            "definition_code": "ALL_THRESHOLD",
            "biz_type": "BUDGET",
            "biz_id": "BUDGET-ALL-1",
            "title": "年度预算双人会签",
            "idempotency_key": "submit-budget-all-threshold-1",
        },
    )
    assert submitted.status_code == 200, submitted.text
    approval = submitted.json()["data"]
    tasks = client.get("/api/v1/approval-tasks", headers=first_headers).json()["data"][
        "items"
    ]
    first_task = next(row for row in tasks if row["approval_id"] == approval["id"])
    first_decision = client.post(
        f"/api/v1/approval-tasks/{first_task['id']}/decide",
        headers=first_headers,
        json={
            "action": "APPROVE",
            "expected_version": 0,
            "idempotency_key": "decision-budget-all-first",
        },
    )
    assert first_decision.status_code == 200, first_decision.text
    assert first_decision.json()["data"]["status"] == "PENDING"
    assert first_decision.json()["data"]["lock_version"] == 1
    second_task = next(
        row
        for row in client.get("/api/v1/approval-tasks", headers=second_headers).json()[
            "data"
        ]["items"]
        if row["approval_id"] == approval["id"]
    )
    completed = client.post(
        f"/api/v1/approval-tasks/{second_task['id']}/decide",
        headers=second_headers,
        json={
            "action": "APPROVE",
            "expected_version": 1,
            "idempotency_key": "decision-budget-all-second",
        },
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["data"]["status"] == "APPROVED"

    _publish_definition(
        client,
        admin_headers,
        code="RETURN_AND_SLA",
        biz_type="REFUND",
        steps=[
            {
                "step_order": 1,
                "name": "退款复核",
                "approval_mode": "ANY",
                "min_approvals": 1,
                "sla_hours": 1,
                "assignees": [{"user_id": int(first.id)}],
            }
        ],
    )
    submitted = client.post(
        "/api/v1/approvals",
        headers=admin_headers,
        json={
            "definition_code": "RETURN_AND_SLA",
            "biz_type": "REFUND",
            "biz_id": "REFUND-RETURN-1",
            "title": "退款退回重提",
            "idempotency_key": "submit-refund-return-1",
        },
    )
    assert submitted.status_code == 200, submitted.text
    approval = submitted.json()["data"]
    task = next(
        row
        for row in client.get("/api/v1/approval-tasks", headers=first_headers).json()[
            "data"
        ]["items"]
        if row["approval_id"] == approval["id"]
    )
    returned = client.post(
        f"/api/v1/approval-tasks/{task['id']}/decide",
        headers=first_headers,
        json={
            "action": "RETURN",
            "remark": "补充付款凭证",
            "expected_version": 0,
            "idempotency_key": "decision-refund-return-1",
        },
    )
    assert returned.status_code == 200, returned.text
    assert returned.json()["data"]["status"] == "RETURNED"
    resubmitted = client.post(
        f"/api/v1/approvals/{approval['id']}/resubmit",
        headers=admin_headers,
        json={
            "remark": "凭证已补充",
            "expected_version": 1,
            "idempotency_key": "resubmit-refund-return-1",
        },
    )
    assert resubmitted.status_code == 200, resubmitted.text
    assert resubmitted.json()["data"]["status"] == "PENDING"
    assert resubmitted.json()["data"]["round_no"] == 2
    assert resubmitted.json()["data"]["lock_version"] == 2

    round_two_task = next(
        row
        for row in client.get("/api/v1/approval-tasks", headers=first_headers).json()[
            "data"
        ]["items"]
        if row["approval_id"] == approval["id"] and row["round_no"] == 2
    )
    stored_task = db_session.get(ApprovalTask, round_two_task["id"])
    assert stored_task is not None
    stored_task.due_at = utc_now() - timedelta(minutes=1)
    db_session.commit()
    swept = client.post(
        "/api/v1/approval-tasks/sweep-overdue?limit=10", headers=admin_headers
    )
    assert swept.status_code == 200, swept.text
    assert round_two_task["id"] in swept.json()["data"]["task_ids"]
    db_session.expire_all()
    stored_task = db_session.get(ApprovalTask, round_two_task["id"])
    assert stored_task is not None and stored_task.escalated_at is not None
    work_item = db_session.scalar(
        select(WorkItem).where(
            WorkItem.tenant_id == 1,
            WorkItem.source_type == "APPROVAL_TASK",
            WorkItem.source_id == str(round_two_task["id"]),
        )
    )
    assert work_item is not None
    assert work_item.priority == "URGENT"


def test_audit_redaction_chain_tamper_export_and_cross_tenant_idor(
    client, db_session: Session
) -> None:
    admin_headers = _headers(1, "admin", ["*"])
    ctx = TenantContext(
        tenant_id=1,
        user_id=1,
        permissions=["*"],
        park_scope_mode=ParkScopeMode.ALL,
        request_id="audit-test-1",
    )
    first = AuditRecorder(db_session, ctx).record(
        action="=FORMULA",
        resource_type="TEST",
        resource_id="=2+2",
        detail={
            "password": "plain-secret",
            "access_token": "plain-token",
            "phone": "13800138000",
            "email": "owner@example.com",
        },
    )
    second = AuditRecorder(db_session, ctx).record(
        action="update",
        resource_type="TEST",
        resource_id="2",
        detail={"safe": "value"},
    )
    legacy = AuditLog(
        tenant_id=1,
        user_id=1,
        request_id="legacy",
        action="legacy",
        resource_type="TEST",
        resource_id="legacy",
        detail_json={"legacy": True},
    )
    db_session.add(legacy)
    other = Tenant(code="audit-other", name="其他租户", status="ACTIVE", db_strategy="SHARED")
    db_session.add(other)
    db_session.flush()
    foreign = AuditLog(
        tenant_id=int(other.id),
        request_id="foreign",
        action="foreign",
        resource_type="TEST",
        resource_id="foreign",
        detail_json={},
    )
    db_session.add(foreign)
    db_session.commit()
    db_session.refresh(first)
    db_session.refresh(second)
    db_session.refresh(legacy)
    db_session.refresh(foreign)

    detail = client.get(f"/api/v1/audit-logs/{first.id}", headers=admin_headers)
    assert detail.status_code == 200, detail.text
    evidence = detail.json()["data"]
    assert evidence["integrity_state"] == "VERIFIED"
    assert evidence["detail"]["password"] == "[REDACTED]"
    assert evidence["detail"]["access_token"] == "[REDACTED]"
    assert evidence["detail"]["phone"] == "138****8000"
    assert evidence["detail"]["email"] == "o***@example.com"
    assert "plain-secret" not in detail.text
    assert "plain-token" not in detail.text

    legacy_detail = client.get(f"/api/v1/audit-logs/{legacy.id}", headers=admin_headers)
    assert legacy_detail.status_code == 200
    assert legacy_detail.json()["data"]["integrity_state"] == "LEGACY_UNVERIFIED"
    foreign_detail = client.get(f"/api/v1/audit-logs/{foreign.id}", headers=admin_headers)
    assert foreign_detail.status_code == 404

    exported = client.get("/api/v1/audit-logs/export", headers=admin_headers)
    assert exported.status_code == 200, exported.text
    assert "'=FORMULA" in exported.text
    assert "'=2+2" in exported.text
    assert "plain-secret" not in exported.text

    stored = db_session.get(AuditLog, int(first.id))
    assert stored is not None
    stored.record_hash = "0" * 64
    db_session.commit()
    verified = client.get("/api/v1/audit-logs/verify", headers=admin_headers)
    assert verified.status_code == 200
    assert verified.json()["data"]["state"] == "FAILED"
    assert verified.json()["data"]["failed_count"] >= 2


def test_audit_export_requires_separate_permission(client, db_session: Session) -> None:
    admin = db_session.get(User, 1)
    assert admin is not None
    viewer = User(
        tenant_id=1,
        username="audit-viewer",
        password_hash=admin.password_hash,
        real_name="审计查看者",
        status="ACTIVE",
    )
    db_session.add(viewer)
    db_session.commit()
    db_session.refresh(viewer)
    headers = _headers(int(viewer.id), viewer.username, ["audit.read"])
    listed = client.get("/api/v1/audit-logs", headers=headers)
    assert listed.status_code == 200, listed.text
    exported = client.get("/api/v1/audit-logs/export", headers=headers)
    assert exported.status_code == 403
    assert exported.json()["code"] == "PERMISSION_DENIED"


def test_definition_rejects_cross_tenant_assignee_and_parameter_pollution(
    client, db_session: Session
) -> None:
    tenant = Tenant(code="workflow-other", name="其他审批租户", status="ACTIVE", db_strategy="SHARED")
    db_session.add(tenant)
    db_session.flush()
    admin = db_session.get(User, 1)
    assert admin is not None
    foreign_user = User(
        tenant_id=int(tenant.id),
        username="foreign-approver",
        password_hash=admin.password_hash,
        real_name="外租户审批人",
        status="ACTIVE",
    )
    db_session.add(foreign_user)
    db_session.commit()
    db_session.refresh(foreign_user)
    headers = _headers(1, "admin", ["*"])
    rejected = client.post(
        "/api/v1/approval-definitions",
        headers=headers,
        json={
            "code": "CROSS_TENANT",
            "name": "跨租户",
            "biz_type": "SECURITY",
            "client_permissions": ["*"],
            "steps": [
                {
                    "step_order": 1,
                    "name": "错误审批人",
                    "approval_mode": "ANY",
                    "min_approvals": 1,
                    "sla_hours": 24,
                    "assignees": [{"user_id": int(foreign_user.id)}],
                }
            ],
        },
    )
    assert rejected.status_code == 422
    without_pollution = client.post(
        "/api/v1/approval-definitions",
        headers=headers,
        json={
            "code": "CROSS_TENANT",
            "name": "跨租户",
            "biz_type": "SECURITY",
            "steps": [
                {
                    "step_order": 1,
                    "name": "错误审批人",
                    "approval_mode": "ANY",
                    "min_approvals": 1,
                    "sla_hours": 24,
                    "assignees": [{"user_id": int(foreign_user.id)}],
                }
            ],
        },
    )
    assert without_pollution.status_code == 400, without_pollution.text
    assert without_pollution.json()["code"] == "APPROVAL_ASSIGNEE_INVALID"
    assert db_session.scalar(
        select(AuditLog).where(
            AuditLog.tenant_id == 1,
            AuditLog.resource_type == "APPROVAL_DEFINITION",
        )
    ) is None

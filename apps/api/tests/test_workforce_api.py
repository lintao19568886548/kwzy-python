"""Workforce API lifecycle, privacy, isolation and conflict acceptance."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.infrastructure.database.models.workforce import AttendancePunch, WorkforceEmployee

TODAY = datetime.now(timezone.utc).date()


def _headers(
    uid: int = 1,
    *,
    permissions: list[str] | None = None,
    park_ids: list[int] | None = None,
    mode: str = "ALL",
) -> dict[str, str]:
    token = create_access_token(
        subject=f"workforce-{uid}",
        claims={
            "uid": uid,
            "tenant_id": 1,
            "permissions": permissions or ["*"],
            "park_ids": park_ids or [],
            "park_scope_mode": mode,
            "tv": 0,
        },
    )
    return {"Authorization": f"Bearer {token}"}


def _key(headers: dict[str, str], value: str) -> dict[str, str]:
    return {**headers, "Idempotency-Key": value}


def _park(client, headers: dict[str, str], label: str) -> dict:
    response = client.post(
        "/api/v1/parks",
        headers=headers,
        json={"name": f"{label}-{uuid4().hex[:8]}", "address": "合成验收地址"},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _employee(
    client, headers: dict[str, str], park_id: int, *, user_id: int | None = None, suffix: str = "A"
) -> dict:
    payload = {
        "park_id": park_id,
        "employee_no": f"EMP_{suffix}_{uuid4().hex[:6]}",
        "display_name": f"验收员工{suffix}",
        "department_name": "园区运营",
        "position_name": "运营专员",
        "mobile": "13800138000",
        "identity_number": "110101199001011234",
        "start_date": TODAY.isoformat(),
    }
    if user_id is not None:
        payload["user_id"] = user_id
    response = client.post("/api/v1/workforce/employees", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _publish_leave_definition(client, headers: dict[str, str]) -> str:
    code = f"workforce_leave_case_{uuid4().hex[:4]}"
    created = client.post(
        "/api/v1/approval-definitions",
        headers=headers,
        json={
            "code": code,
            "name": "员工请假审批",
            "biz_type": "WORKFORCE_LEAVE",
            "steps": [
                {
                    "step_order": 1,
                    "name": "直属经理复核",
                    "approval_mode": "ANY",
                    "min_approvals": 1,
                    "sla_hours": 24,
                    "assignees": [{"user_id": 1}],
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    definition = created.json()["data"]
    draft = next(item for item in definition["versions"] if item["status"] == "DRAFT")
    published = client.post(
        f"/api/v1/approval-definitions/{definition['id']}/publish",
        headers=headers,
        json={"version_id": draft["id"], "expected_lock_version": 0},
    )
    assert published.status_code == 200, published.text
    fetched = client.get(f"/api/v1/approval-definitions/{definition['id']}", headers=headers)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["data"]["status"] == "ACTIVE"
    assert fetched.json()["data"]["code"] == code.upper()
    return code


def test_employee_privacy_scope_roster_punch_and_anomaly(client, db_session: Session) -> None:
    admin = _headers()
    park = _park(client, admin, "人力园")
    other = _park(client, admin, "隔离园")
    employee = _employee(client, admin, park["id"], user_id=1)
    rendered = str(employee)
    assert "13800138000" not in rendered
    assert "110101199001011234" not in rendered
    assert employee["mobile_masked"] == "***8000"
    stored = db_session.scalar(
        select(WorkforceEmployee).where(WorkforceEmployee.id == employee["id"])
    )
    assert stored is not None
    assert not hasattr(stored, "mobile") and not hasattr(stored, "identity_number")
    assert stored.mobile_fingerprint and stored.identity_fingerprint

    scoped = _headers(permissions=["workforce:read"], park_ids=[other["id"]], mode="LIST")
    denied = client.get(f"/api/v1/workforce/employees/{employee['id']}", headers=scoped)
    assert denied.status_code == 404

    shift_response = client.post(
        "/api/v1/workforce/shifts",
        headers=admin,
        json={
            "park_id": park["id"],
            "code": f"DAY_{uuid4().hex[:5]}",
            "name": "日班",
            "start_time": "09:00:00",
            "end_time": "18:00:00",
            "cross_day": False,
            "break_minutes": 60,
            "late_grace_minutes": 5,
            "early_grace_minutes": 5,
        },
    )
    assert shift_response.status_code == 200, shift_response.text
    shift = shift_response.json()["data"]
    assignment_response = client.post(
        "/api/v1/workforce/assignments",
        headers=admin,
        json={
            "employee_id": employee["id"],
            "shift_version_id": shift["versions"][0]["id"],
            "work_date": TODAY.isoformat(),
            "reason": "独立验收排班",
        },
    )
    assert assignment_response.status_code == 200, assignment_response.text
    duplicate = client.post(
        "/api/v1/workforce/assignments",
        headers=admin,
        json={
            "employee_id": employee["id"],
            "shift_version_id": shift["versions"][0]["id"],
            "work_date": TODAY.isoformat(),
        },
    )
    assert duplicate.status_code == 409

    location_response = client.post(
        "/api/v1/workforce/attendance/locations",
        headers=admin,
        json={
            "park_id": park["id"],
            "code": f"GATE_{uuid4().hex[:5]}",
            "name": "东门",
            "config_ref": "secret://attendance/east-gate",
            "radius_m": 300,
        },
    )
    assert location_response.status_code == 200, location_response.text
    location = location_response.json()["data"]
    punch_payload = {
        "employee_id": employee["id"],
        "punch_type": "IN",
        "punched_at": datetime.now(timezone.utc).isoformat(),
        "source": "MOBILE",
        "location_id": location["id"],
        "distance_m": 80,
        "device_id": "synthetic-device-1",
        "latitude": 31.2304,
        "longitude": 121.4737,
    }
    first = client.post(
        "/api/v1/workforce/attendance/punches",
        headers=_key(admin, "workforce-punch-1"),
        json=punch_payload,
    )
    assert first.status_code == 200, first.text
    replay = client.post(
        "/api/v1/workforce/attendance/punches",
        headers=_key(admin, "workforce-punch-1"),
        json=punch_payload,
    )
    assert replay.status_code == 200 and replay.json()["data"]["id"] == first.json()["data"]["id"]
    changed = client.post(
        "/api/v1/workforce/attendance/punches",
        headers=_key(admin, "workforce-punch-1"),
        json={**punch_payload, "punch_type": "OUT"},
    )
    assert changed.status_code == 409
    stored_punch = db_session.get(AttendancePunch, first.json()["data"]["id"])
    assert stored_punch is not None
    assert not hasattr(stored_punch, "latitude") and not hasattr(stored_punch, "longitude")

    summary = client.post(
        "/api/v1/workforce/attendance/summaries/generate",
        headers=admin,
        json={"employee_id": employee["id"], "work_date": TODAY.isoformat()},
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["data"]["status"] == "ANOMALY"
    assert summary.json()["data"]["anomaly_code"] == "MISSING_OUT"


def test_performance_qualification_and_validation_gates(client) -> None:
    admin = _headers()
    park = _park(client, admin, "绩效园")
    linked = _employee(client, admin, park["id"], user_id=1, suffix="SELF")
    subject = _employee(client, admin, park["id"], suffix="SUBJECT")
    cycle_response = client.post(
        "/api/v1/workforce/performance/cycles",
        headers=admin,
        json={
            "park_id": park["id"],
            "code": f"CYCLE_{uuid4().hex[:5]}",
            "name": "季度绩效",
            "start_date": TODAY.isoformat(),
            "end_date": (TODAY + timedelta(days=90)).isoformat(),
        },
    )
    assert cycle_response.status_code == 200, cycle_response.text
    cycle = cycle_response.json()["data"]
    for employee in (linked, subject):
        goal = client.post(
            f"/api/v1/workforce/performance/cycles/{cycle['id']}/goals",
            headers=admin,
            json={
                "employee_id": employee["id"],
                "code": f"GOAL_{employee['id']}",
                "title": "园区任务闭环",
                "weight": 100,
                "target_value": "100%",
            },
        )
        assert goal.status_code == 200, goal.text
    active_response = client.post(
        f"/api/v1/workforce/performance/cycles/{cycle['id']}/status",
        headers=admin,
        json={
            "expected_version": cycle["lock_version"],
            "status": "ACTIVE",
            "reason": "开始验收周期",
        },
    )
    assert active_response.status_code == 200, active_response.text
    self_review = client.post(
        "/api/v1/workforce/performance/reviews",
        headers=admin,
        json={
            "cycle_id": cycle["id"],
            "employee_id": linked["id"],
            "rating": 90,
            "comment": "不得自评",
        },
    )
    assert self_review.status_code == 403
    review_response = client.post(
        "/api/v1/workforce/performance/reviews",
        headers=admin,
        json={
            "cycle_id": cycle["id"],
            "employee_id": subject["id"],
            "rating": 88,
            "comment": "任务交付稳定",
        },
    )
    assert review_response.status_code == 200, review_response.text
    review = review_response.json()["data"]
    published = client.post(
        f"/api/v1/workforce/performance/reviews/{review['id']}/publish",
        headers=admin,
        json={"expected_version": review["lock_version"], "reason": "经理复核完成"},
    )
    assert published.status_code == 200 and published.json()["data"]["status"] == "PUBLISHED"

    qtype_response = client.post(
        "/api/v1/workforce/qualification-types",
        headers=admin,
        json={
            "code": f"ELECTRIC_{uuid4().hex[:5]}",
            "name": "低压电工作业证",
            "validity_months": 36,
            "reminder_days": 30,
        },
    )
    assert qtype_response.status_code == 200, qtype_response.text
    qtype = qtype_response.json()["data"]
    attachment = client.post(
        "/api/v1/attachments",
        headers=admin,
        json={
            "biz_type": "WORKFORCE_QUALIFICATION",
            "biz_id": str(subject["id"]),
            "filename": "qualification.txt",
            "content_type": "text/plain",
            "content_base64": base64.b64encode(b"synthetic qualification evidence").decode(),
            "park_id": park["id"],
        },
    )
    assert attachment.status_code == 200, attachment.text
    qualification_response = client.post(
        "/api/v1/workforce/qualifications",
        headers=admin,
        json={
            "employee_id": subject["id"],
            "qualification_type_id": qtype["id"],
            "attachment_id": attachment.json()["data"]["id"],
            "credential_number": "CERT-2026-000001",
            "issuer": "合成验收机构",
            "effective_on": (TODAY - timedelta(days=365)).isoformat(),
            "expires_on": (TODAY - timedelta(days=1)).isoformat(),
        },
    )
    assert qualification_response.status_code == 200, qualification_response.text
    qualification = qualification_response.json()["data"]
    assert "CERT-2026-000001" not in str(qualification)
    verified = client.post(
        f"/api/v1/workforce/qualifications/{qualification['id']}/verify",
        headers=admin,
        json={"expected_version": qualification["lock_version"], "reason": "合成证据核验"},
    )
    assert verified.status_code == 200, verified.text
    sweep = client.post(
        "/api/v1/workforce/qualifications/sweep", headers=admin, json={"due_on": TODAY.isoformat()}
    )
    assert sweep.status_code == 200 and sweep.json()["data"]["expired"] == 1
    replay = client.post(
        "/api/v1/workforce/qualifications/sweep", headers=admin, json={"due_on": TODAY.isoformat()}
    )
    assert replay.status_code == 200 and replay.json()["data"]["expired"] == 0

    unknown = client.post(
        "/api/v1/workforce/employees",
        headers=admin,
        json={
            "park_id": park["id"],
            "employee_no": "BAD_UNKNOWN",
            "display_name": "未知字段",
            "start_date": TODAY.isoformat(),
            "unexpected": True,
        },
    )
    assert unknown.status_code == 422
    repeated = client.get("/api/v1/workforce/employees?page=1&page=2", headers=admin)
    assert repeated.status_code == 400


def test_leave_uses_native_approval_and_blocks_roster(client) -> None:
    admin = _headers()
    park = _park(client, admin, "请假园")
    employee = _employee(client, admin, park["id"], suffix="LEAVE")
    definition_code = _publish_leave_definition(client, admin)
    leave_day = TODAY + timedelta(days=7)
    leave_response = client.post(
        "/api/v1/workforce/leaves",
        headers=_key(admin, "workforce-leave-approval-1"),
        json={
            "employee_id": employee["id"],
            "leave_type": "ANNUAL",
            "start_at": datetime.combine(
                leave_day, datetime.min.time(), tzinfo=timezone.utc
            ).isoformat(),
            "end_at": datetime.combine(
                leave_day + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc
            ).isoformat(),
            "reason": "年度休假",
            "definition_code": definition_code,
        },
    )
    assert leave_response.status_code == 200, leave_response.text
    leave = leave_response.json()["data"]
    assert leave["status"] == "PENDING_APPROVAL"
    approval = client.get(f"/api/v1/approvals/{leave['approval_id']}", headers=admin)
    assert approval.status_code == 200, approval.text
    detail = approval.json()["data"]
    task = next(item for item in detail["tasks"] if item["status"] == "PENDING")
    decided = client.post(
        f"/api/v1/approval-tasks/{task['id']}/decide",
        headers=admin,
        json={
            "action": "APPROVE",
            "expected_version": detail["lock_version"],
            "idempotency_key": "workforce-leave-decision-1",
            "override_reason": "独立验收单管理员审批门禁",
        },
    )
    assert decided.status_code == 200, decided.text
    refreshed = client.post(
        f"/api/v1/workforce/leaves/{leave['id']}/refresh-approval", headers=admin
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["data"]["status"] == "APPROVED"

    shift_response = client.post(
        "/api/v1/workforce/shifts",
        headers=admin,
        json={
            "park_id": park["id"],
            "code": f"LEAVE_DAY_{uuid4().hex[:5]}",
            "name": "请假冲突日班",
            "start_time": "09:00:00",
            "end_time": "18:00:00",
            "cross_day": False,
            "break_minutes": 60,
            "late_grace_minutes": 5,
            "early_grace_minutes": 5,
        },
    )
    assert shift_response.status_code == 200, shift_response.text
    conflict = client.post(
        "/api/v1/workforce/assignments",
        headers=admin,
        json={
            "employee_id": employee["id"],
            "shift_version_id": shift_response.json()["data"]["versions"][0]["id"],
            "work_date": leave_day.isoformat(),
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "WORKFORCE_LEAVE_CONFLICT"

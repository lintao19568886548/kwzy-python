#!/usr/bin/env python3
"""Loopback-only real HTTP acceptance for workforce operations."""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import urlparse

import httpx

T = TypeVar("T")


class JourneyFailure(RuntimeError):
    """A business-stage assertion failed during the loopback journey."""


def loopback_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise argparse.ArgumentTypeError("journey is restricted to loopback targets")
    return value.rstrip("/")


def expect_ok(response: httpx.Response, label: str) -> Any:
    try:
        body = response.json()
    except ValueError as exc:
        raise JourneyFailure(
            f"{label}: non-JSON response {response.status_code}"
        ) from exc
    if response.status_code != 200 or body.get("code") != "OK":
        raise JourneyFailure(
            f"{label}: HTTP {response.status_code} code={body.get('code')} "
            f"message={body.get('message')}"
        )
    return body.get("data")


def expect_error(response: httpx.Response, status: int, code: str, label: str) -> None:
    try:
        body = response.json()
    except ValueError as exc:
        raise JourneyFailure(
            f"{label}: non-JSON response {response.status_code}"
        ) from exc
    if response.status_code != status or body.get("code") != code:
        raise JourneyFailure(
            f"{label}: expected {status}/{code}, got "
            f"{response.status_code}/{body.get('code')}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url", type=loopback_url, default="http://127.0.0.1:8010/api/v1"
    )
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    now = datetime.now(timezone.utc)
    today = now.date()
    suffix = uuid.uuid4().hex[:10].upper()
    stages: list[dict[str, Any]] = []

    def stage(name: str, operation: Callable[[], T]) -> T:
        tick = time.perf_counter()
        result = operation()
        stages.append(
            {
                "name": name,
                "passed": True,
                "ms": round((time.perf_counter() - tick) * 1000, 2),
            }
        )
        return result

    with httpx.Client(base_url=args.base_url, timeout=20.0) as client:
        login = stage(
            "login",
            lambda: expect_ok(
                client.post(
                    "/auth/login",
                    json={
                        "username": args.username,
                        "password": args.password,
                        "tenant_code": "default",
                    },
                ),
                "login",
            ),
        )
        client.headers.update(
            {
                "Authorization": f"Bearer {login['access_token']}",
                "X-Client-Platform": "workforce-acceptance-http",
            }
        )
        me = stage("identity", lambda: expect_ok(client.get("/auth/me"), "identity"))
        park = stage(
            "create_park",
            lambda: expect_ok(
                client.post(
                    "/parks",
                    json={"name": f"HTTP 人力园区 {suffix}", "address": "合成验收地址"},
                ),
                "create park",
            ),
        )
        employee = stage(
            "create_masked_employee",
            lambda: expect_ok(
                client.post(
                    "/workforce/employees",
                    json={
                        "park_id": park["id"],
                        "employee_no": f"HTTP_{suffix}",
                        "display_name": "HTTP 验收员工",
                        "department_name": "园区运营",
                        "position_name": "运营专员",
                        "mobile": "13800138000",
                        "identity_number": "110101199001011234",
                        "start_date": today.isoformat(),
                    },
                ),
                "create employee",
            ),
        )
        employee_json = json.dumps(employee, ensure_ascii=False)
        if "13800138000" in employee_json or "110101199001011234" in employee_json:
            raise JourneyFailure("raw employee PII leaked through real HTTP")
        shift = stage(
            "create_immutable_shift_version",
            lambda: expect_ok(
                client.post(
                    "/workforce/shifts",
                    json={
                        "park_id": park["id"],
                        "code": f"DAY_{suffix}",
                        "name": "HTTP 日班",
                        "start_time": "09:00:00",
                        "end_time": "18:00:00",
                        "cross_day": False,
                        "break_minutes": 60,
                        "late_grace_minutes": 5,
                        "early_grace_minutes": 5,
                    },
                ),
                "create shift",
            ),
        )
        shift_version_id = shift["versions"][0]["id"]
        assignment_payload = {
            "employee_id": employee["id"],
            "shift_version_id": shift_version_id,
            "work_date": today.isoformat(),
            "reason": "真实 HTTP 排班",
        }
        assignment = stage(
            "create_assignment",
            lambda: expect_ok(
                client.post("/workforce/assignments", json=assignment_payload),
                "create assignment",
            ),
        )
        duplicate_assignment = stage(
            "reject_duplicate_assignment",
            lambda: client.post("/workforce/assignments", json=assignment_payload),
        )
        expect_error(
            duplicate_assignment,
            409,
            "WORKFORCE_ASSIGNMENT_CONFLICT",
            "duplicate assignment",
        )
        policy = stage(
            "create_attendance_policy",
            lambda: expect_ok(
                client.post(
                    "/workforce/attendance/policies",
                    json={
                        "park_id": park["id"],
                        "code": f"POL_{suffix}",
                        "name": "HTTP 考勤策略",
                        "geofence_radius_m": 300,
                        "allow_manual": True,
                    },
                ),
                "create attendance policy",
            ),
        )
        location = stage(
            "create_reference_only_attendance_location",
            lambda: expect_ok(
                client.post(
                    "/workforce/attendance/locations",
                    json={
                        "park_id": park["id"],
                        "code": f"GATE_{suffix}",
                        "name": "HTTP 东门",
                        "config_ref": f"secret://attendance/http-{suffix.lower()}",
                        "radius_m": 300,
                    },
                ),
                "create attendance location",
            ),
        )
        punch_key = f"workforce-http-punch-{suffix}"
        punch_payload = {
            "employee_id": employee["id"],
            "punch_type": "IN",
            "punched_at": now.isoformat(),
            "source": "MOBILE",
            "location_id": location["id"],
            "distance_m": 80,
            "device_id": f"http-device-{suffix}",
            "latitude": 31.2304,
            "longitude": 121.4737,
        }
        punch = stage(
            "create_coordinate_redacted_punch",
            lambda: expect_ok(
                client.post(
                    "/workforce/attendance/punches",
                    headers={"Idempotency-Key": punch_key},
                    json=punch_payload,
                ),
                "create punch",
            ),
        )
        if "latitude" in punch or "longitude" in punch:
            raise JourneyFailure("exact punch coordinates leaked through real HTTP")
        punch_replay = stage(
            "punch_idempotent_replay",
            lambda: expect_ok(
                client.post(
                    "/workforce/attendance/punches",
                    headers={"Idempotency-Key": punch_key},
                    json=punch_payload,
                ),
                "punch replay",
            ),
        )
        if punch_replay["id"] != punch["id"]:
            raise JourneyFailure("idempotent punch replay returned a new row")
        changed_punch = stage(
            "reject_changed_idempotency_payload",
            lambda: client.post(
                "/workforce/attendance/punches",
                headers={"Idempotency-Key": punch_key},
                json={**punch_payload, "punch_type": "OUT"},
            ),
        )
        if changed_punch.status_code != 409:
            raise JourneyFailure(
                f"changed idempotency payload expected 409, got {changed_punch.status_code}"
            )
        summary = stage(
            "generate_missing_out_anomaly",
            lambda: expect_ok(
                client.post(
                    "/workforce/attendance/summaries/generate",
                    json={
                        "employee_id": employee["id"],
                        "work_date": today.isoformat(),
                    },
                ),
                "generate summary",
            ),
        )
        if summary["status"] != "ANOMALY" or summary["anomaly_code"] != "MISSING_OUT":
            raise JourneyFailure(f"unexpected attendance anomaly: {summary}")
        adjusted = stage(
            "audited_attendance_adjustment",
            lambda: expect_ok(
                client.post(
                    f"/workforce/attendance/summaries/{summary['id']}/adjust",
                    json={
                        "expected_version": summary["lock_version"],
                        "status": "ADJUSTED",
                        "worked_minutes": 480,
                        "reason": "HTTP 独立复核补卡",
                    },
                ),
                "adjust summary",
            ),
        )
        if adjusted["status"] != "ADJUSTED":
            raise JourneyFailure("attendance adjustment was not persisted")

        definition_code = f"workforce_http_{suffix.lower()}"
        definition = stage(
            "create_lowercase_leave_definition",
            lambda: expect_ok(
                client.post(
                    "/approval-definitions",
                    json={
                        "code": definition_code,
                        "name": "HTTP 员工请假审批",
                        "biz_type": "WORKFORCE_LEAVE",
                        "steps": [
                            {
                                "step_order": 1,
                                "name": "HTTP 直属经理复核",
                                "approval_mode": "ANY",
                                "min_approvals": 1,
                                "sla_hours": 24,
                                "assignees": [{"user_id": int(me["id"])}],
                            }
                        ],
                    },
                ),
                "create leave definition",
            ),
        )
        draft = next(
            item for item in definition["versions"] if item["status"] == "DRAFT"
        )
        stage(
            "publish_leave_definition",
            lambda: expect_ok(
                client.post(
                    f"/approval-definitions/{definition['id']}/publish",
                    json={
                        "version_id": draft["id"],
                        "expected_lock_version": definition["lock_version"],
                    },
                ),
                "publish leave definition",
            ),
        )
        fetched_definition = stage(
            "verify_canonical_definition_code",
            lambda: expect_ok(
                client.get(f"/approval-definitions/{definition['id']}"),
                "get leave definition",
            ),
        )
        if fetched_definition["code"] != definition_code.upper():
            raise JourneyFailure("approval definition code was not canonicalized")
        leave_day = today + timedelta(days=7)
        leave = stage(
            "submit_leave_to_native_approval",
            lambda: expect_ok(
                client.post(
                    "/workforce/leaves",
                    headers={"Idempotency-Key": f"workforce-http-leave-{suffix}"},
                    json={
                        "employee_id": employee["id"],
                        "leave_type": "ANNUAL",
                        "start_at": datetime.combine(
                            leave_day, datetime.min.time(), tzinfo=timezone.utc
                        ).isoformat(),
                        "end_at": datetime.combine(
                            leave_day + timedelta(days=1),
                            datetime.min.time(),
                            tzinfo=timezone.utc,
                        ).isoformat(),
                        "reason": "HTTP 年度休假",
                        "definition_code": definition_code,
                    },
                ),
                "submit leave",
            ),
        )
        if leave["status"] != "PENDING_APPROVAL":
            raise JourneyFailure("leave bypassed native approval")
        approval = stage(
            "read_native_leave_approval",
            lambda: expect_ok(
                client.get(f"/approvals/{leave['approval_id']}"), "read leave approval"
            ),
        )
        task = next(item for item in approval["tasks"] if item["status"] == "PENDING")
        stage(
            "approve_leave_with_audited_override",
            lambda: expect_ok(
                client.post(
                    f"/approval-tasks/{task['id']}/decide",
                    json={
                        "action": "APPROVE",
                        "expected_version": approval["lock_version"],
                        "idempotency_key": f"workforce-http-decision-{suffix}",
                        "override_reason": "本机隔离验收仅管理员作为审批候选",
                    },
                ),
                "approve leave",
            ),
        )
        approved_leave = stage(
            "refresh_approved_leave",
            lambda: expect_ok(
                client.post(f"/workforce/leaves/{leave['id']}/refresh-approval"),
                "refresh leave",
            ),
        )
        if approved_leave["status"] != "APPROVED":
            raise JourneyFailure("approved leave state was not synchronized")
        leave_conflict = stage(
            "block_roster_on_approved_leave",
            lambda: client.post(
                "/workforce/assignments",
                json={
                    "employee_id": employee["id"],
                    "shift_version_id": shift_version_id,
                    "work_date": leave_day.isoformat(),
                    "reason": "必须被请假门禁拒绝",
                },
            ),
        )
        expect_error(
            leave_conflict,
            409,
            "WORKFORCE_LEAVE_CONFLICT",
            "approved leave roster conflict",
        )

        cycle = stage(
            "create_performance_cycle",
            lambda: expect_ok(
                client.post(
                    "/workforce/performance/cycles",
                    json={
                        "park_id": park["id"],
                        "code": f"CYC_{suffix}",
                        "name": "HTTP 季度绩效",
                        "start_date": today.isoformat(),
                        "end_date": (today + timedelta(days=90)).isoformat(),
                    },
                ),
                "create performance cycle",
            ),
        )
        stage(
            "create_weighted_goal",
            lambda: expect_ok(
                client.post(
                    f"/workforce/performance/cycles/{cycle['id']}/goals",
                    json={
                        "employee_id": employee["id"],
                        "code": f"GOAL_{suffix}",
                        "title": "园区任务闭环",
                        "weight": 100,
                        "target_value": "100%",
                    },
                ),
                "create performance goal",
            ),
        )
        cycle = stage(
            "activate_performance_cycle",
            lambda: expect_ok(
                client.post(
                    f"/workforce/performance/cycles/{cycle['id']}/status",
                    json={
                        "expected_version": cycle["lock_version"],
                        "status": "ACTIVE",
                        "reason": "HTTP 真实绩效周期开始",
                    },
                ),
                "activate performance cycle",
            ),
        )
        review = stage(
            "manager_performance_review",
            lambda: expect_ok(
                client.post(
                    "/workforce/performance/reviews",
                    json={
                        "cycle_id": cycle["id"],
                        "employee_id": employee["id"],
                        "rating": 88,
                        "comment": "HTTP 任务交付稳定",
                    },
                ),
                "create performance review",
            ),
        )
        review = stage(
            "publish_performance_review",
            lambda: expect_ok(
                client.post(
                    f"/workforce/performance/reviews/{review['id']}/publish",
                    json={
                        "expected_version": review["lock_version"],
                        "reason": "HTTP 经理复核完成",
                    },
                ),
                "publish performance review",
            ),
        )
        if review["status"] != "PUBLISHED":
            raise JourneyFailure("performance review was not published")

        qualification_type = stage(
            "create_qualification_type",
            lambda: expect_ok(
                client.post(
                    "/workforce/qualification-types",
                    json={
                        "code": f"ELEC_{suffix}",
                        "name": "HTTP 低压电工作业证",
                        "validity_months": 36,
                        "reminder_days": 30,
                    },
                ),
                "create qualification type",
            ),
        )
        attachment = stage(
            "upload_qualification_evidence",
            lambda: expect_ok(
                client.post(
                    "/attachments",
                    json={
                        "biz_type": "WORKFORCE_QUALIFICATION",
                        "biz_id": str(employee["id"]),
                        "filename": "http-qualification.txt",
                        "content_type": "text/plain",
                        "content_base64": base64.b64encode(
                            b"synthetic workforce qualification evidence"
                        ).decode(),
                        "park_id": park["id"],
                    },
                ),
                "upload qualification evidence",
            ),
        )
        credential_number = f"CERT-HTTP-{suffix}"
        qualification = stage(
            "create_masked_expired_qualification",
            lambda: expect_ok(
                client.post(
                    "/workforce/qualifications",
                    json={
                        "employee_id": employee["id"],
                        "qualification_type_id": qualification_type["id"],
                        "attachment_id": attachment["id"],
                        "credential_number": credential_number,
                        "issuer": "合成验收机构",
                        "effective_on": (today - timedelta(days=365)).isoformat(),
                        "expires_on": (today - timedelta(days=1)).isoformat(),
                    },
                ),
                "create qualification",
            ),
        )
        if credential_number in json.dumps(qualification, ensure_ascii=False):
            raise JourneyFailure(
                "raw qualification credential leaked through real HTTP"
            )
        qualification = stage(
            "verify_qualification_evidence",
            lambda: expect_ok(
                client.post(
                    f"/workforce/qualifications/{qualification['id']}/verify",
                    json={
                        "expected_version": qualification["lock_version"],
                        "reason": "HTTP 合成证据核验",
                    },
                ),
                "verify qualification",
            ),
        )
        first_sweep = stage(
            "expire_qualification_and_create_work_item",
            lambda: expect_ok(
                client.post(
                    "/workforce/qualifications/sweep",
                    json={"due_on": today.isoformat()},
                ),
                "first qualification sweep",
            ),
        )
        second_sweep = stage(
            "qualification_sweep_idempotent_replay",
            lambda: expect_ok(
                client.post(
                    "/workforce/qualifications/sweep",
                    json={"due_on": today.isoformat()},
                ),
                "second qualification sweep",
            ),
        )
        if first_sweep["expired"] < 1 or second_sweep["expired"] != 0:
            raise JourneyFailure("qualification expiry sweep was not idempotent")

        polluted = stage(
            "reject_unknown_employee_field",
            lambda: client.post(
                "/workforce/employees",
                json={
                    "park_id": park["id"],
                    "employee_no": f"BAD_{suffix}",
                    "display_name": "参数污染",
                    "start_date": today.isoformat(),
                    "tenant_id": 999,
                },
            ),
        )
        if polluted.status_code != 422:
            raise JourneyFailure(
                f"unknown employee field expected 422, got {polluted.status_code}"
            )
        tenant_b_login = stage(
            "login_other_tenant",
            lambda: expect_ok(
                client.post(
                    "/auth/login",
                    json={
                        "username": "admin_b",
                        "password": "adminb123",
                        "tenant_code": "tenant_b",
                    },
                ),
                "tenant B login",
            ),
        )
        with httpx.Client(
            base_url=args.base_url,
            timeout=20.0,
            headers={"Authorization": f"Bearer {tenant_b_login['access_token']}"},
        ) as tenant_b:
            isolated = stage(
                "cross_tenant_employee_isolation",
                lambda: tenant_b.get(f"/workforce/employees/{employee['id']}"),
            )
            expect_error(
                isolated,
                404,
                "WORKFORCE_EMPLOYEE_NOT_FOUND",
                "cross-tenant employee",
            )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "real_http": True,
        "synthetic_only": True,
        "stage_count": len(stages),
        "stages": stages,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "passed": all(item["passed"] for item in stages),
        "employee_id": employee["id"],
        "assignment_id": assignment["id"],
        "attendance_policy_id": policy["id"],
        "leave_id": leave["id"],
        "performance_review_id": review["id"],
        "qualification_id": qualification["id"],
        "production_contacted": False,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"WORKFORCE_HTTP_REPORT={output}")
    print(f"WORKFORCE_REAL_HTTP=PASS stages={len(stages)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"WORKFORCE_REAL_HTTP=FAIL error={type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise

#!/usr/bin/env python3
"""Real-HTTP approval/audit journey for the isolated local acceptance stack."""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


class JourneyFailure(RuntimeError):
    pass


def expect_ok(response: httpx.Response, label: str) -> Any:
    try:
        body = response.json()
    except ValueError as exc:
        raise JourneyFailure(f"{label}: non-JSON response {response.status_code}") from exc
    if response.status_code != 200 or body.get("code") != "OK":
        raise JourneyFailure(
            f"{label}: HTTP {response.status_code} code={body.get('code')} "
            f"message={body.get('message')}"
        )
    return body.get("data")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8010/api/v1")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    suffix = uuid.uuid4().hex[:10].upper()
    code = f"HTTP_{suffix}"
    biz_id = f"HTTP-JOURNEY-{suffix}"
    submit_key = f"http-submit-{uuid.uuid4().hex}"[:64]
    decision_key = f"http-decision-{uuid.uuid4().hex}"[:64]
    stages: list[dict[str, Any]] = []

    def stage(name: str, fn):
        tick = time.perf_counter()
        result = fn()
        stages.append({"name": name, "passed": True, "ms": round((time.perf_counter() - tick) * 1000, 2)})
        return result

    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=20.0) as client:
        login = stage(
            "login",
            lambda: expect_ok(
                client.post(
                    "/auth/login",
                    json={"username": args.username, "password": args.password, "tenant_code": "default"},
                ),
                "login",
            ),
        )
        token = login["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}", "X-Client-Platform": "acceptance-http"})
        me = stage("identity", lambda: expect_ok(client.get("/auth/me"), "identity"))
        definition = stage(
            "create_definition",
            lambda: expect_ok(
                client.post(
                    "/approval-definitions",
                    json={
                        "code": code,
                        "name": f"HTTP 真实旅程 {suffix}",
                        "biz_type": "HTTP_SMOKE",
                        "steps": [
                            {
                                "step_order": 1,
                                "name": "HTTP 审批节点",
                                "approval_mode": "ANY",
                                "min_approvals": 1,
                                "sla_hours": 4,
                                "assignees": [{"user_id": int(me["id"])}],
                            }
                        ],
                    },
                ),
                "create_definition",
            ),
        )
        draft = next(item for item in definition["versions"] if item["status"] == "DRAFT")
        stage(
            "publish_definition",
            lambda: expect_ok(
                client.post(
                    f"/approval-definitions/{definition['id']}/publish",
                    json={"version_id": draft["id"], "expected_lock_version": definition["lock_version"]},
                ),
                "publish_definition",
            ),
        )
        approval = stage(
            "submit",
            lambda: expect_ok(
                client.post(
                    "/approvals",
                    json={
                        "definition_code": code,
                        "biz_type": "HTTP_SMOKE",
                        "biz_id": biz_id,
                        "title": f"HTTP 审批 {suffix}",
                        "priority": "HIGH",
                        "snapshot": {"source": "local-real-http", "phone": "13800138000"},
                        "idempotency_key": submit_key,
                    },
                ),
                "submit",
            ),
        )
        retry = stage(
            "submit_idempotent_retry",
            lambda: expect_ok(
                client.post(
                    "/approvals",
                    json={
                        "definition_code": code,
                        "biz_type": "HTTP_SMOKE",
                        "biz_id": biz_id,
                        "title": f"HTTP 审批 {suffix}",
                        "priority": "HIGH",
                        "snapshot": {"source": "local-real-http", "phone": "13800138000"},
                        "idempotency_key": submit_key,
                    },
                ),
                "submit_idempotent_retry",
            ),
        )
        if retry["id"] != approval["id"]:
            raise JourneyFailure("idempotent submit returned a different approval")
        inbox = stage(
            "task_query",
            lambda: expect_ok(client.get("/approval-tasks", params={"processed": False, "page_size": 100}), "task_query"),
        )
        task = next((item for item in inbox["items"] if item["approval_id"] == approval["id"]), None)
        if task is None:
            raise JourneyFailure("submitted approval task missing from real HTTP inbox")
        decided = stage(
            "decision",
            lambda: expect_ok(
                client.post(
                    f"/approval-tasks/{task['id']}/decide",
                    json={
                        "action": "APPROVE",
                        "remark": "HTTP 真实链路通过",
                        "expected_version": approval["lock_version"],
                        "idempotency_key": decision_key,
                        "override_reason": "本机隔离测试只有管理员作为审批候选",
                    },
                ),
                "decision",
            ),
        )
        if decided["status"] != "APPROVED":
            raise JourneyFailure(f"unexpected terminal status {decided['status']}")
        decision_retry = stage(
            "decision_idempotent_retry",
            lambda: expect_ok(
                client.post(
                    f"/approval-tasks/{task['id']}/decide",
                    json={
                        "action": "APPROVE",
                        "remark": "HTTP 真实链路通过",
                        "expected_version": approval["lock_version"],
                        "idempotency_key": decision_key,
                        "override_reason": "本机隔离测试只有管理员作为审批候选",
                    },
                ),
                "decision_idempotent_retry",
            ),
        )
        if decision_retry["lock_version"] != decided["lock_version"]:
            raise JourneyFailure("idempotent decision changed approval version")
        audits = stage(
            "audit_query",
            lambda: expect_ok(client.get("/audit-logs", params={"resource_type": "APPROVAL", "resource_id": str(approval["id"]), "page_size": 100}), "audit_query"),
        )
        if not any(item["action"] == "decision" for item in audits["items"]):
            raise JourneyFailure("decision audit evidence missing")
        verification = stage(
            "audit_verify",
            lambda: expect_ok(client.get("/audit-logs/verify"), "audit_verify"),
        )
        if verification["state"] != "VERIFIED" or verification["failed_count"] != 0:
            raise JourneyFailure(f"audit chain verification failed: {verification}")
        exported = stage(
            "audit_export",
            lambda: client.get("/audit-logs/export", params={"resource_type": "APPROVAL", "resource_id": str(approval["id"])}),
        )
        if exported.status_code != 200 or "decision" not in exported.text:
            raise JourneyFailure("audit CSV export missing decision evidence")
        detail = stage(
            "approval_detail",
            lambda: expect_ok(client.get(f"/approvals/{approval['id']}"), "approval_detail"),
        )
        serialized = json.dumps(detail, ensure_ascii=False)
        if "13800138000" in serialized or "plain-secret" in serialized:
            raise JourneyFailure("raw PII or secret leaked through approval detail")

    report = {
        "result": "PASS",
        "finished_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017 - Python 3.10
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "base_url": args.base_url,
        "real_http": True,
        "approval_id": approval["id"],
        "request_no": approval["request_no"],
        "audit_state": verification["state"],
        "stages": stages,
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"APPROVAL_AUDIT_HTTP_REPORT={path}")
    print("APPROVAL_AUDIT_REAL_HTTP=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"APPROVAL_AUDIT_REAL_HTTP=FAIL error={type(exc).__name__}: {exc}", file=sys.stderr)
        raise

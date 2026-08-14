#!/usr/bin/env python3
"""Loopback-only real HTTP workbench automation acceptance journey."""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import urlparse

import httpx


class JourneyFailure(RuntimeError):
    pass


T = TypeVar("T")


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
        raise JourneyFailure(f"{label}: non-JSON response {response.status_code}") from exc
    if response.status_code != 200 or body.get("code") != "OK":
        raise JourneyFailure(
            f"{label}: HTTP {response.status_code} code={body.get('code')} "
            f"message={body.get('message')}"
        )
    return body.get("data")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", type=loopback_url, default="http://127.0.0.1:8010/api/v1")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    suffix = uuid.uuid4().hex[:10].upper()
    stages: list[dict[str, Any]] = []

    def stage(name: str, operation: Callable[[], T]) -> T:
        tick = time.perf_counter()
        result = operation()
        stages.append(
            {"name": name, "passed": True, "ms": round((time.perf_counter() - tick) * 1000, 2)}
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
                "X-Client-Platform": "acceptance-http",
            }
        )
        me = stage("identity", lambda: expect_ok(client.get("/auth/me"), "identity"))
        user_id = int(me["id"])

        title = f"HTTP 自动化待办 {suffix}"
        notification_title = f"HTTP 自动化消息 {suffix}"
        rule = stage(
            "create_rule_draft",
            lambda: expect_ok(
                client.post(
                    "/automation-rules",
                    json={
                        "code": f"HTTP_GOOD_{suffix}",
                        "name": f"HTTP 自动化规则 {suffix}",
                        "event_type": "TEST_AUTOMATION_EVENT",
                        "conditions": [{"field": "status", "operator": "EQ", "value": "READY"}],
                        "actions": [
                            {
                                "type": "CREATE_WORK_ITEM",
                                "title": title,
                                "description": "真实 HTTP 投影",
                                "item_type": "HTTP_ACCEPTANCE",
                                "priority": "HIGH",
                                "assignee_user_id": user_id,
                                "deep_link": "/todos",
                            },
                            {
                                "type": "CREATE_NOTIFICATION",
                                "title": notification_title,
                                "content": "真实 HTTP 站内消息",
                                "recipient_user_id": user_id,
                                "category": "ACCEPTANCE",
                                "deep_link": "/workbench",
                            },
                        ],
                    },
                ),
                "create_rule_draft",
            ),
        )
        edited = stage(
            "update_rule_draft",
            lambda: expect_ok(
                client.put(
                    f"/automation-rules/{rule['id']}/draft",
                    json={
                        "expected_version": rule["lock_version"],
                        "name": f"HTTP 自动化规则已复核 {suffix}",
                        "priority": 90,
                    },
                ),
                "update_rule_draft",
            ),
        )
        published = stage(
            "publish_rule",
            lambda: expect_ok(
                client.post(
                    f"/automation-rules/{rule['id']}/publish",
                    json={"expected_version": edited["lock_version"]},
                ),
                "publish_rule",
            ),
        )
        if published["versions"][0]["status"] != "PUBLISHED":
            raise JourneyFailure("rule publication did not create an immutable published version")

        event_key = f"http-good-{suffix.lower()}"
        event_payload = {
            "event_type": "TEST_AUTOMATION_EVENT",
            "source_type": "HTTP_ACCEPTANCE",
            "source_id": suffix,
            "idempotency_key": event_key,
            "payload": {
                "title": title,
                "description": "真实 HTTP 旅程",
                "status": "READY",
                "assignee_user_id": user_id,
                "deep_link": "/todos",
            },
        }
        event = stage(
            "emit_event",
            lambda: expect_ok(client.post("/business-events", json=event_payload), "emit_event"),
        )
        repeated = stage(
            "event_idempotent_retry",
            lambda: expect_ok(
                client.post("/business-events", json=event_payload), "event_idempotent_retry"
            ),
        )
        if repeated["id"] != event["id"]:
            raise JourneyFailure("event idempotency returned a different event")
        dispatch = stage(
            "dispatch_event",
            lambda: expect_ok(client.post("/business-events/dispatch?limit=20"), "dispatch_event"),
        )
        if dispatch["succeeded"] < 1:
            raise JourneyFailure(f"event was not consumed: {dispatch}")

        todos = stage(
            "query_source_owned_todo",
            lambda: expect_ok(
                client.get(
                    "/work-items",
                    params={"status": "OPEN", "item_type": "HTTP_ACCEPTANCE", "page_size": 100},
                ),
                "query_source_owned_todo",
            ),
        )
        todo = next((item for item in todos["items"] if item["title"] == title), None)
        if todo is None or not todo["source_owned"] or todo["deep_link"] != "/todos":
            raise JourneyFailure("source-owned todo projection or deep link is missing")
        notifications = stage(
            "query_notification",
            lambda: expect_ok(client.get("/notifications?page_size=100"), "query_notification"),
        )
        notification = next(
            (item for item in notifications["items"] if item["title"] == notification_title), None
        )
        if notification is None or notification["status"] != "UNREAD":
            raise JourneyFailure("recipient-scoped notification projection is missing")
        stage(
            "read_notification",
            lambda: expect_ok(
                client.post(f"/notifications/{notification['id']}/read"), "read_notification"
            ),
        )

        schedule = stage(
            "create_disabled_schedule",
            lambda: expect_ok(
                client.post(
                    "/scheduler/definitions",
                    json={
                        "code": f"HTTP_SCHEDULE_{suffix}",
                        "name": f"HTTP 调度 {suffix}",
                        "handler_key": "OUTBOX_DISPATCH",
                        "parameters": {"limit": 20},
                        "cadence_seconds": 60,
                        "enabled": False,
                        "concurrency_policy": "FORBID",
                    },
                ),
                "create_disabled_schedule",
            ),
        )
        enabled = stage(
            "enable_schedule",
            lambda: expect_ok(
                client.put(
                    f"/scheduler/definitions/{schedule['id']}",
                    json={"expected_version": schedule["lock_version"], "enabled": True},
                ),
                "enable_schedule",
            ),
        )
        run_key = f"http-run-{suffix.lower()}"
        run = stage(
            "manual_schedule_run",
            lambda: expect_ok(
                client.post(
                    f"/scheduler/definitions/{schedule['id']}/run",
                    json={"idempotency_key": run_key},
                ),
                "manual_schedule_run",
            ),
        )
        run_retry = stage(
            "schedule_run_idempotent_retry",
            lambda: expect_ok(
                client.post(
                    f"/scheduler/definitions/{schedule['id']}/run",
                    json={"idempotency_key": run_key},
                ),
                "schedule_run_idempotent_retry",
            ),
        )
        if run_retry["id"] != run["id"] or run["status"] != "SUCCEEDED":
            raise JourneyFailure("scheduler manual run is not terminal and idempotent")
        stage(
            "disable_schedule",
            lambda: expect_ok(
                client.put(
                    f"/scheduler/definitions/{schedule['id']}",
                    json={"expected_version": enabled["lock_version"], "enabled": False},
                ),
                "disable_schedule",
            ),
        )

        role_choices = stage(
            "list_role_layouts",
            lambda: expect_ok(client.get("/workbench/layout/roles"), "list_role_layouts"),
        )
        admin_role = next((item for item in role_choices if item["role_code"] == "ADMIN"), None)
        if admin_role is None:
            raise JourneyFailure("ADMIN role is unavailable for role-layout journey")
        role_layout = stage(
            "get_role_layout",
            lambda: expect_ok(
                client.get(f"/workbench/layout/roles/{admin_role['role_id']}"), "get_role_layout"
            ),
        )
        saved_role = stage(
            "save_role_layout",
            lambda: expect_ok(
                client.put(
                    f"/workbench/layout/roles/{admin_role['role_id']}",
                    json={
                        "role_id": admin_role["role_id"],
                        "expected_version": role_layout["lock_version"],
                        "name": f"HTTP 管理员默认 {suffix}",
                        "priority": 10,
                        "widgets": role_layout["widgets"],
                    },
                ),
                "save_role_layout",
            ),
        )
        if saved_role["lock_version"] != role_layout["lock_version"] + 1:
            raise JourneyFailure("role layout optimistic version was not advanced")
        effective = stage(
            "effective_role_layout",
            lambda: expect_ok(client.get("/workbench/layout"), "effective_role_layout"),
        )
        personal_expected = effective["lock_version"] if effective["source"] == "USER" else 0
        personal = stage(
            "save_personal_layout",
            lambda: expect_ok(
                client.put(
                    "/workbench/layout",
                    json={
                        "expected_version": personal_expected,
                        "name": f"HTTP 个人工作台 {suffix}",
                        "widgets": role_layout["widgets"],
                    },
                ),
                "save_personal_layout",
            ),
        )
        stale = stage(
            "personal_layout_conflict",
            lambda: client.put(
                "/workbench/layout",
                json={
                    "expected_version": personal_expected,
                    "name": "过期窗口",
                    "widgets": role_layout["widgets"],
                },
            ),
        )
        stale_body = stale.json()
        if stale.status_code != 409 or stale_body.get("code") != "LAYOUT_VERSION_CONFLICT":
            raise JourneyFailure("stale personal layout did not receive the documented 409")
        if personal["source"] != "USER":
            raise JourneyFailure("personal layout did not override the role layout")
        reset = stage(
            "reset_to_role_layout",
            lambda: expect_ok(client.delete("/workbench/layout"), "reset_to_role_layout"),
        )
        if reset["source"] != "ROLE":
            raise JourneyFailure("personal reset did not fall back to the role layout")

        bad_rule = stage(
            "create_dead_letter_rule",
            lambda: expect_ok(
                client.post(
                    "/automation-rules",
                    json={
                        "code": f"HTTP_DEAD_{suffix}",
                        "name": f"HTTP 死信规则 {suffix}",
                        "event_type": "LEAD_CREATED",
                        "actions": [
                            {
                                "type": "CREATE_NOTIFICATION",
                                "title": "无效接收人",
                                "content": "仅用于隔离验收",
                                "recipient_user_id": 999999999,
                                "deep_link": "/leads",
                            }
                        ],
                    },
                ),
                "create_dead_letter_rule",
            ),
        )
        bad_published = stage(
            "publish_dead_letter_rule",
            lambda: expect_ok(
                client.post(
                    f"/automation-rules/{bad_rule['id']}/publish",
                    json={"expected_version": bad_rule["lock_version"]},
                ),
                "publish_dead_letter_rule",
            ),
        )
        if bad_published["status"] != "ACTIVE":
            raise JourneyFailure("dead-letter test rule was not activated")
        bad_event = stage(
            "emit_dead_letter_event",
            lambda: expect_ok(
                client.post(
                    "/business-events",
                    json={
                        "event_type": "LEAD_CREATED",
                        "source_type": "HTTP_ACCEPTANCE",
                        "source_id": f"DEAD-{suffix}",
                        "idempotency_key": f"http-dead-{suffix.lower()}",
                        "payload": {
                            "title": "死信验收",
                            "description": "无效接收人触发",
                            "deep_link": "/leads",
                        },
                    },
                ),
                "emit_dead_letter_event",
            ),
        )
        for attempt, delay in enumerate((0.0, 2.2, 4.2), start=1):
            if delay:
                time.sleep(delay)
            stage(
                f"dead_letter_dispatch_{attempt}",
                lambda attempt=attempt: expect_ok(
                    client.post("/business-events/dispatch?limit=20"),
                    f"dead_letter_dispatch_{attempt}",
                ),
            )
        event_page = stage(
            "inspect_dead_letter",
            lambda: expect_ok(
                client.get("/business-events", params={"event_type": "LEAD_CREATED", "page_size": 100}),
                "inspect_dead_letter",
            ),
        )
        selected_event = next(item for item in event_page["items"] if item["id"] == bad_event["id"])
        dead = next((item for item in selected_event["consumers"] if item["status"] == "DEAD"), None)
        if dead is None or dead["attempt_count"] != 3:
            raise JourneyFailure("consumer did not reach DEAD after bounded retry")
        replay = stage(
            "controlled_dead_letter_replay",
            lambda: expect_ok(
                client.post(
                    f"/event-consumers/{dead['id']}/replay",
                    json={"reason": "隔离验收确认失败证据后重放"},
                ),
                "controlled_dead_letter_replay",
            ),
        )
        if replay["generation"] != dead["generation"] + 1 or replay["status"] != "PENDING":
            raise JourneyFailure("dead-letter replay did not preserve generation evidence")

    report = {
        "schema_version": 1,
        "result": "PASS",
        "finished_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017 - Python 3.10
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "target": args.base_url,
        "real_http": True,
        "event_id": event["id"],
        "work_item_id": todo["id"],
        "notification_id": notification["id"],
        "schedule_run_id": run["id"],
        "dead_consumer_id": dead["id"],
        "replay_generation": replay["generation"],
        "stages": stages,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"WORKBENCH_AUTOMATION_HTTP_REPORT={output}")
    print("WORKBENCH_AUTOMATION_REAL_HTTP=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"WORKBENCH_AUTOMATION_REAL_HTTP=FAIL error={type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise

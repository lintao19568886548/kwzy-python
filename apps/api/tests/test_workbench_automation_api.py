"""Event, rule, notification, scheduler and layout API acceptance tests."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.core.security import create_access_token
from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.workbench_automation import EventConsumerLog


def _h(*, permissions: list[str] | None = None, park_ids: list[int] | None = None) -> dict:
    token = create_access_token(
        subject="admin",
        claims={
            "uid": 1,
            "tenant_id": 1,
            "permissions": permissions or ["*"],
            "park_ids": park_ids or [],
            "park_scope_mode": "LIST" if park_ids else "ALL",
        },
    )
    return {"Authorization": f"Bearer {token}"}


def _forged_h(user_id: int, permissions: list[str]) -> dict:
    token = create_access_token(
        subject=f"user-{user_id}",
        claims={
            "uid": user_id,
            "tenant_id": 1,
            "permissions": permissions,
            "park_ids": [],
            "park_scope_mode": "ALL",
        },
    )
    return {"Authorization": f"Bearer {token}"}


def _park(client, headers: dict, name: str = "自动化园") -> dict:
    response = client.post("/api/v1/parks", headers=headers, json={"name": name, "address": "test"})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _create_rule(client, headers: dict, park_id: int, *, recipient: int = 1) -> dict:
    response = client.post(
        "/api/v1/automation-rules",
        headers=headers,
        json={
            "code": f"BILL_HIGH_{park_id}_{recipient}",
            "name": "高额账单协同",
            "park_id": park_id,
            "event_type": "TEST_AUTOMATION_EVENT",
            "conditions": [{"field": "amount", "operator": "GTE", "value": "100"}],
            "actions": [
                {
                    "type": "CREATE_WORK_ITEM",
                    "title": "复核 ${payload.title}",
                    "description": "金额 ${payload.amount}",
                    "item_type": "FINANCE_REVIEW",
                    "priority": "HIGH",
                    "assignee_user_id": "${payload.assignee_user_id}",
                    "deep_link": "/bills",
                },
                {
                    "type": "CREATE_NOTIFICATION",
                    "title": "请处理 ${payload.title}",
                    "content": "金额 ${payload.amount} 已进入复核",
                    "recipient_user_id": str(recipient),
                    "category": "FINANCE",
                    "deep_link": "/bills",
                },
            ],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _emit(client, headers: dict, park_id: int, key: str, *, amount: str = "800") -> dict:
    response = client.post(
        "/api/v1/business-events",
        headers=headers,
        json={
            "event_type": "TEST_AUTOMATION_EVENT",
            "source_type": "TEST_BILL",
            "source_id": key,
            "idempotency_key": f"automation-test:{key}",
            "park_id": park_id,
            "payload": {
                "title": f"账单 {key}",
                "description": "合成验收事件",
                "amount": amount,
                "assignee_user_id": 1,
                "deep_link": "/bills",
                "park_id": park_id,
            },
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_event_rule_todo_notification_end_to_end(client) -> None:
    headers = _h()
    park = _park(client, headers)
    rule = _create_rule(client, headers, park["id"])
    assert rule["versions"][0]["status"] == "DRAFT"

    published = client.post(
        f"/api/v1/automation-rules/{rule['id']}/publish",
        headers=headers,
        json={"expected_version": rule["lock_version"]},
    )
    assert published.status_code == 200, published.text
    assert published.json()["data"]["versions"][0]["status"] == "PUBLISHED"

    event = _emit(client, headers, park["id"], "one")
    repeated = _emit(client, headers, park["id"], "one")
    assert repeated["id"] == event["id"]

    dispatched = client.post("/api/v1/business-events/dispatch?limit=20", headers=headers)
    assert dispatched.status_code == 200, dispatched.text
    assert dispatched.json()["data"]["succeeded"] == 1

    todos = client.get(
        "/api/v1/work-items",
        headers=headers,
        params={"status": "OPEN", "item_type": "FINANCE_REVIEW"},
    ).json()["data"]
    assert todos["total"] == 1
    todo = todos["items"][0]
    assert todo["source_owned"] is True
    assert todo["deep_link"] == "/bills"
    blocked = client.post(
        f"/api/v1/work-items/{todo['id']}/complete",
        headers=_h(permissions=["work_item:write"]),
        json={"expected_version": todo["lock_version"]},
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "WORK_ITEM_SOURCE_OWNED"

    inbox = client.get("/api/v1/notifications", headers=headers)
    assert inbox.status_code == 200, inbox.text
    notification = inbox.json()["data"]["items"][0]
    assert notification["channel"] == "IN_APP"
    assert notification["status"] == "UNREAD"
    read = client.post(f"/api/v1/notifications/{notification['id']}/read", headers=headers)
    assert read.status_code == 200
    assert read.json()["data"]["status"] == "READ"

    executions = client.get("/api/v1/automation-executions", headers=headers)
    assert executions.status_code == 200
    assert executions.json()["data"][0]["status"] == "SUCCEEDED"


def test_rule_safety_publication_conflict_and_no_match(client) -> None:
    headers = _h()
    park = _park(client, headers, "规则安全园")
    unsafe = client.post(
        "/api/v1/automation-rules",
        headers=headers,
        json={
            "code": "UNSAFE_RULE",
            "name": "不安全规则",
            "park_id": park["id"],
            "event_type": "TEST_AUTOMATION_EVENT",
            "conditions": [{"field": "unknown", "operator": "EQ", "value": "x"}],
            "actions": [{"type": "CREATE_WORK_ITEM", "title": "x"}],
        },
    )
    assert unsafe.status_code == 400
    assert unsafe.json()["code"] == "RULE_GRAMMAR_INVALID"

    unsafe_url = client.post(
        "/api/v1/automation-rules",
        headers=headers,
        json={
            "code": "URL_RULE",
            "name": "URL 规则",
            "park_id": park["id"],
            "event_type": "TEST_AUTOMATION_EVENT",
            "actions": [
                {"type": "CREATE_WORK_ITEM", "title": "x", "deep_link": "https://evil.invalid"}
            ],
        },
    )
    assert unsafe_url.status_code == 400
    assert unsafe_url.json()["code"] == "RULE_UNSAFE_CONTENT"

    rule = _create_rule(client, headers, park["id"])
    first = client.post(
        f"/api/v1/automation-rules/{rule['id']}/publish",
        headers=headers,
        json={"expected_version": rule["lock_version"]},
    )
    assert first.status_code == 200
    stale = client.post(
        f"/api/v1/automation-rules/{rule['id']}/draft",
        headers=headers,
        json={"expected_version": rule["lock_version"]},
    )
    assert stale.status_code == 409

    _emit(client, headers, park["id"], "low", amount="20")
    dispatched = client.post("/api/v1/business-events/dispatch", headers=headers)
    assert dispatched.status_code == 200
    assert dispatched.json()["data"]["succeeded"] == 1
    executions = client.get("/api/v1/automation-executions", headers=headers).json()["data"]
    assert executions[0]["status"] == "NOT_MATCHED"


def test_dead_letter_and_generation_preserving_replay(client, db_session) -> None:
    headers = _h()
    park = _park(client, headers, "死信园")
    rule = _create_rule(client, headers, park["id"], recipient=999999)
    published = client.post(
        f"/api/v1/automation-rules/{rule['id']}/publish",
        headers=headers,
        json={"expected_version": rule["lock_version"]},
    )
    assert published.status_code == 200
    event = _emit(client, headers, park["id"], "dead")

    for attempt in range(3):
        response = client.post("/api/v1/business-events/dispatch", headers=headers)
        assert response.status_code == 200, response.text
        if attempt < 2:
            row = db_session.scalars(
                select(EventConsumerLog).where(EventConsumerLog.event_id == event["id"])
            ).first()
            assert row is not None
            row.next_attempt_at = utc_now() - timedelta(seconds=1)
            db_session.add(row)
            db_session.commit()

    event_detail = client.get("/api/v1/business-events", headers=headers).json()["data"]["items"]
    selected = next(item for item in event_detail if item["id"] == event["id"])
    dead = selected["consumers"][0]
    assert dead["status"] == "DEAD"
    replay = client.post(
        f"/api/v1/event-consumers/{dead['id']}/replay",
        headers=headers,
        json={"reason": "修复接收人映射后重放"},
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["generation"] == 2
    assert replay.json()["data"]["status"] == "PENDING"


def test_notification_recipient_idor_and_atomic_bulk_read(client, db_session) -> None:
    headers = _h()
    user_response = client.post(
        "/api/v1/system/users",
        headers=headers,
        json={"username": "notify-two", "password": "Strong#12345", "real_name": "接收人二"},
    )
    assert user_response.status_code == 200, user_response.text
    user_two = user_response.json()["data"]
    park = _park(client, headers, "通知隔离园")
    rule = _create_rule(client, headers, park["id"], recipient=user_two["id"])
    client.post(
        f"/api/v1/automation-rules/{rule['id']}/publish",
        headers=headers,
        json={"expected_version": rule["lock_version"]},
    )
    _emit(client, headers, park["id"], "recipient-two")
    client.post("/api/v1/business-events/dispatch", headers=headers)

    own = client.get("/api/v1/notifications", headers=headers)
    assert own.status_code == 200
    assert own.json()["data"]["total"] == 0

    from app.infrastructure.database.models.workbench_automation import InAppNotification

    db_session.expire_all()
    other = db_session.scalars(
        select(InAppNotification).where(InAppNotification.recipient_user_id == user_two["id"])
    ).first()
    assert other is not None
    hidden = client.post(f"/api/v1/notifications/{other.id}/read", headers=headers)
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "NOTIFICATION_NOT_FOUND"

    own_rule = _create_rule(client, headers, park["id"], recipient=1)
    publish = client.post(
        f"/api/v1/automation-rules/{own_rule['id']}/publish",
        headers=headers,
        json={"expected_version": own_rule["lock_version"]},
    )
    assert publish.status_code == 200
    _emit(client, headers, park["id"], "recipient-one")
    client.post("/api/v1/business-events/dispatch", headers=headers)
    own_notification = client.get("/api/v1/notifications", headers=headers).json()["data"]["items"][0]
    bulk = client.post(
        "/api/v1/notifications/bulk-read",
        headers=headers,
        json={"ids": [own_notification["id"], other.id]},
    )
    assert bulk.status_code == 404
    unchanged = client.get("/api/v1/notifications", headers=headers).json()["data"]["items"][0]
    assert unchanged["status"] == "UNREAD"


def test_layout_resolution_validation_and_optimistic_conflict(client) -> None:
    headers = _h()
    default = client.get("/api/v1/workbench/layout", headers=headers)
    assert default.status_code == 200, default.text
    layout = default.json()["data"]
    assert layout["source"] == "SERVER_DEFAULT"
    assert layout["lock_version"] == 0
    assert len(layout["widgets"]) >= 3

    widgets = [
        {
            "widget_key": "OPERATIONS_METRICS",
            "position_x": 0,
            "position_y": 0,
            "width": 12,
            "height": 2,
            "visible": True,
            "config": {},
        },
        {
            "widget_key": "MY_TODOS",
            "position_x": 0,
            "position_y": 2,
            "width": 8,
            "height": 4,
            "visible": True,
            "config": {"limit": 10},
        },
    ]
    saved = client.put(
        "/api/v1/workbench/layout",
        headers=headers,
        json={"expected_version": 0, "name": "财务工作台", "widgets": widgets},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["source"] == "USER"
    stale = client.put(
        "/api/v1/workbench/layout",
        headers=headers,
        json={"expected_version": 0, "name": "旧窗口", "widgets": widgets},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "LAYOUT_VERSION_CONFLICT"

    overlap = client.put(
        "/api/v1/workbench/layout",
        headers=headers,
        json={
            "expected_version": saved.json()["data"]["lock_version"],
            "name": "重叠布局",
            "widgets": [
                {**widgets[0], "width": 8},
                {**widgets[1], "position_x": 4, "position_y": 0},
            ],
        },
    )
    assert overlap.status_code == 400
    assert overlap.json()["code"] == "WIDGET_GRID_OVERLAP"
    reset = client.delete("/api/v1/workbench/layout", headers=headers)
    assert reset.status_code == 200
    assert reset.json()["data"]["source"] == "SERVER_DEFAULT"

    roles = client.get("/api/v1/workbench/layout/roles", headers=headers)
    assert roles.status_code == 200, roles.text
    admin_role = next(item for item in roles.json()["data"] if item["role_code"] == "ADMIN")
    role_default = client.get(
        f"/api/v1/workbench/layout/roles/{admin_role['role_id']}", headers=headers
    )
    assert role_default.status_code == 200, role_default.text
    assert role_default.json()["data"]["lock_version"] == 0
    saved_role = client.put(
        f"/api/v1/workbench/layout/roles/{admin_role['role_id']}",
        headers=headers,
        json={
            "role_id": admin_role["role_id"],
            "expected_version": 0,
            "name": "管理员默认工作台",
            "priority": 10,
            "widgets": widgets,
        },
    )
    assert saved_role.status_code == 200, saved_role.text
    assert saved_role.json()["data"]["lock_version"] == 1
    effective_role = client.get("/api/v1/workbench/layout", headers=headers)
    assert effective_role.status_code == 200
    assert effective_role.json()["data"]["source"] == "ROLE"
    assert effective_role.json()["data"]["name"] == "管理员默认工作台"
    polluted = client.put(
        f"/api/v1/workbench/layout/roles/{admin_role['role_id']}",
        headers=headers,
        json={
            "role_id": admin_role["role_id"] + 1,
            "expected_version": 1,
            "name": "污染请求",
            "priority": 10,
            "widgets": widgets,
        },
    )
    assert polluted.status_code == 400
    assert polluted.json()["code"] == "PARAMETER_POLLUTION"


def test_scheduler_allowlist_manual_run_and_idempotency(client) -> None:
    headers = _h()
    unsafe = client.post(
        "/api/v1/scheduler/definitions",
        headers=headers,
        json={
            "code": "UNSAFE_JOB",
            "name": "不安全任务",
            "handler_key": "SHELL",
            "parameters": {"command": "whoami"},
            "cadence_seconds": 60,
        },
    )
    assert unsafe.status_code == 400
    assert unsafe.json()["code"] == "SCHEDULER_HANDLER_NOT_REGISTERED"

    created = client.post(
        "/api/v1/scheduler/definitions",
        headers=headers,
        json={
            "code": "DISPATCH_JOB",
            "name": "事件派发",
            "handler_key": "OUTBOX_DISPATCH",
            "parameters": {"limit": 10},
            "cadence_seconds": 60,
            "enabled": False,
        },
    )
    assert created.status_code == 200, created.text
    schedule = created.json()["data"]
    first = client.post(
        f"/api/v1/scheduler/definitions/{schedule['id']}/run",
        headers=headers,
        json={"idempotency_key": "manual-dispatch-001"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["data"]["status"] == "SUCCEEDED"
    repeated = client.post(
        f"/api/v1/scheduler/definitions/{schedule['id']}/run",
        headers=headers,
        json={"idempotency_key": "manual-dispatch-001"},
    )
    assert repeated.status_code == 200
    assert repeated.json()["data"]["id"] == first.json()["data"]["id"]
    runs = client.get("/api/v1/scheduler/runs", headers=headers)
    assert runs.status_code == 200
    assert len(runs.json()["data"]) == 1


def test_automation_permission_and_park_scope(client) -> None:
    headers = _h()
    park_one = _park(client, headers, "可见园")
    park_two = _park(client, headers, "不可见园")
    _emit(client, headers, park_two["id"], "scope")

    denied = client.get(
        "/api/v1/automation-rules", headers=_h(permissions=["workbench.layout.read"])
    )
    assert denied.status_code == 403
    scoped = client.get(
        "/api/v1/business-events",
        headers=_h(permissions=["event.read"], park_ids=[park_one["id"]]),
    )
    assert scoped.status_code == 200
    assert scoped.json()["data"]["total"] == 0

    unprivileged = client.post(
        "/api/v1/system/users",
        headers=headers,
        json={"username": "no-automation", "password": "Strong#12345"},
    )
    assert unprivileged.status_code == 200
    forged = client.get(
        "/api/v1/business-events",
        headers=_forged_h(unprivileged.json()["data"]["id"], ["event.read", "*"]),
    )
    assert forged.status_code == 403
    assert forged.json()["code"] == "PERMISSION_DENIED"

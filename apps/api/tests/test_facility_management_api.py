"""End-to-end API regression tests for facility devices, inspections and IoT alarms."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.security import create_access_token


def _headers(
    *,
    tenant_id: int = 1,
    uid: int = 1,
    permissions: list[str] | None = None,
    park_ids: list[int] | None = None,
    mode: str = "ALL",
) -> dict[str, str]:
    token = create_access_token(
        subject=f"facility-user-{uid}",
        claims={
            "uid": uid,
            "tenant_id": tenant_id,
            "permissions": permissions or ["*"],
            "park_ids": park_ids or [],
            "park_scope_mode": mode,
        },
    )
    return {"Authorization": f"Bearer {token}"}


def _key(headers: dict[str, str], value: str) -> dict[str, str]:
    return {**headers, "Idempotency-Key": value}


def test_facility_inspection_and_iot_alarm_lifecycle(client) -> None:
    headers = _headers()
    park = client.post(
        "/api/v1/parks",
        headers=headers,
        json={"name": f"设施园-{uuid4().hex[:8]}", "address": "设施验收地址"},
    )
    assert park.status_code == 200, park.text
    park_id = park.json()["data"]["id"]
    operator_suffix = uuid4().hex[:8]
    role = client.post(
        "/api/v1/system/roles",
        headers=headers,
        json={
            "code": f"INSPECTOR_{operator_suffix.upper()}",
            "name": f"巡检员 {operator_suffix}",
            "all_parks": False,
            "permission_codes": ["inspection:execute"],
            "park_ids": [park_id],
        },
    )
    assert role.status_code == 200, role.text
    operator = client.post(
        "/api/v1/system/users",
        headers=headers,
        json={
            "username": f"inspector_{operator_suffix}",
            "password": "Inspector-Test-123!",
            "real_name": "周巡检执行人",
            "role_ids": [role.json()["data"]["id"]],
            "park_ids": [park_id],
            "all_parks": False,
        },
    )
    assert operator.status_code == 200, operator.text
    operator_data = operator.json()["data"]
    operator_headers = _headers(
        uid=operator_data["id"],
        permissions=["inspection:execute"],
        park_ids=[park_id],
        mode="LIST",
    )

    created_device = client.post(
        "/api/v1/facility-devices",
        headers=headers,
        json={
            "park_id": park_id,
            "device_code": f"FIRE-{uuid4().hex[:8]}",
            "name": "消防泵一号",
            "device_type": "FIRE",
            "location": "A 栋负一层泵房",
            "criticality": "CRITICAL",
            "properties": {"rated_power_kw": 45, "networked": True},
        },
    )
    assert created_device.status_code == 200, created_device.text
    device = created_device.json()["data"]
    assert device["status"] == "ACTIVE"
    assert device["history"][0]["action"] == "CREATED"

    updated = client.put(
        f"/api/v1/facility-devices/{device['id']}",
        headers=headers,
        json={
            "expected_version": device["lock_version"],
            "reason": "季度维护窗口",
            "status": "MAINTENANCE",
            "location": "A 栋负一层消防泵房",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["lock_version"] == 2

    template_response = client.post(
        "/api/v1/inspection-templates",
        headers=headers,
        json={
            "code": f"FIRE_WEEKLY_{uuid4().hex[:6].upper()}",
            "name": "消防设备周检",
            "device_type": "FIRE",
            "items": [
                {
                    "item_code": "RUNNING",
                    "label": "运行状态",
                    "result_type": "BOOLEAN",
                    "critical": True,
                },
                {
                    "item_code": "PRESSURE",
                    "label": "出口压力",
                    "result_type": "NUMBER",
                    "minimum": "0.4",
                    "maximum": "1.2",
                },
            ],
        },
    )
    assert template_response.status_code == 200, template_response.text
    template = template_response.json()["data"]
    version = template["versions"][0]
    published = client.post(
        f"/api/v1/inspection-template-versions/{version['id']}/publish",
        headers=headers,
        json={"expected_version": version["lock_version"]},
    )
    assert published.status_code == 200, published.text
    published_version = published.json()["data"]
    assert published_version["status"] == "PUBLISHED"

    now = datetime.now(timezone.utc)
    shanghai_now = now + timedelta(hours=8)
    due = shanghai_now + timedelta(minutes=30)
    schedule_response = client.post(
        "/api/v1/inspection-schedules",
        headers=headers,
        json={
            "park_id": park_id,
            "code": f"FIRE-SCHEDULE-{uuid4().hex[:6]}",
            "name": "消防泵周检",
            "device_id": device["id"],
            "template_version_id": published_version["id"],
            "assignee_user_id": operator_data["id"],
            "timezone": "Asia/Shanghai",
            "weekday": due.isoweekday(),
            "local_due_time": due.strftime("%H:%M"),
            "completion_window_minutes": 10080,
            "missed_work_order": True,
        },
    )
    assert schedule_response.status_code == 200, schedule_response.text
    schedule = schedule_response.json()["data"]
    paused = client.post(
        f"/api/v1/inspection-schedules/{schedule['id']}/pause",
        headers=headers,
        json={"expected_version": schedule["lock_version"], "reason": "测试暂停"},
    )
    assert paused.status_code == 200, paused.text
    assert paused.json()["data"]["status"] == "PAUSED"
    resumed = client.post(
        f"/api/v1/inspection-schedules/{schedule['id']}/resume",
        headers=headers,
        json={
            "expected_version": paused.json()["data"]["lock_version"],
            "reason": "测试恢复",
        },
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["data"]["status"] == "ACTIVE"

    blocked_retirement = client.post(
        f"/api/v1/facility-devices/{device['id']}/retire",
        headers=headers,
        json={"expected_version": 2, "reason": "生效周检存在时不得退役"},
    )
    assert blocked_retirement.status_code == 409, blocked_retirement.text
    assert blocked_retirement.json()["code"] == "FACILITY_DEVICE_RETIREMENT_BLOCKED"
    assert blocked_retirement.json()["data"]["active_schedules"] == 1

    generated = client.post(
        "/api/v1/inspection-tasks/generate", headers=headers, json={"as_of": now.isoformat()}
    )
    assert generated.status_code == 200, generated.text
    task_id = generated.json()["data"]["created_ids"][0]
    replay_generation = client.post(
        "/api/v1/inspection-tasks/generate", headers=headers, json={"as_of": now.isoformat()}
    )
    assert replay_generation.status_code == 200, replay_generation.text
    assert replay_generation.json()["data"]["existing_ids"] == [task_id]

    task = client.get(
        f"/api/v1/inspection-tasks/{task_id}", headers=operator_headers
    ).json()["data"]
    started = client.post(
        f"/api/v1/inspection-tasks/{task_id}/start",
        headers=_key(operator_headers, f"inspection-start-{uuid4()}"),
        json={"expected_version": task["lock_version"]},
    )
    assert started.status_code == 200, started.text
    started_task = started.json()["data"]

    submit_key = f"inspection-submit-{uuid4()}"
    submitted = client.post(
        f"/api/v1/inspection-tasks/{task_id}/submit",
        headers=_key(operator_headers, submit_key),
        json={
            "expected_version": started_task["lock_version"],
            "results": [
                {
                    "item_code": "RUNNING",
                    "value": False,
                    "evidence_refs": ["evidence://fire-pump/video-1"],
                    "remark": "消防泵无法启动",
                },
                {"item_code": "PRESSURE", "value": "0.8"},
            ],
        },
    )
    assert submitted.status_code == 200, submitted.text
    submitted_task = submitted.json()["data"]
    assert submitted_task["status"] == "FAILED"
    assert submitted_task["exceptions"][0]["work_order_id"] is not None
    replay_submit = client.post(
        f"/api/v1/inspection-tasks/{task_id}/submit",
        headers=_key(operator_headers, submit_key),
        json={
            "expected_version": started_task["lock_version"],
            "results": [
                {"item_code": "RUNNING", "value": False},
                {"item_code": "PRESSURE", "value": "0.8"},
            ],
        },
    )
    assert replay_submit.status_code == 200, replay_submit.text
    assert replay_submit.json()["data"]["id"] == task_id

    overdue_due = shanghai_now - timedelta(minutes=5)
    overdue_schedule = client.post(
        "/api/v1/inspection-schedules",
        headers=headers,
        json={
            "park_id": park_id,
            "code": f"OVERDUE-SCHEDULE-{uuid4().hex[:6]}",
            "name": "消防泵漏检升级",
            "device_id": device["id"],
            "template_version_id": published_version["id"],
            "assignee_user_id": operator_data["id"],
            "timezone": "Asia/Shanghai",
            "weekday": overdue_due.isoweekday(),
            "local_due_time": overdue_due.strftime("%H:%M"),
            "completion_window_minutes": 1,
            "missed_work_order": True,
        },
    )
    assert overdue_schedule.status_code == 200, overdue_schedule.text
    overdue_generated = client.post(
        "/api/v1/inspection-tasks/generate",
        headers=headers,
        json={"as_of": now.isoformat()},
    )
    assert overdue_generated.status_code == 200, overdue_generated.text
    overdue_task_id = overdue_generated.json()["data"]["created_ids"][0]
    missed = client.post(
        "/api/v1/inspection-tasks/sweep-missed",
        headers=headers,
        json={"as_of": now.isoformat()},
    )
    assert missed.status_code == 200, missed.text
    assert overdue_task_id in missed.json()["data"]["missed_ids"]
    assert missed.json()["data"]["work_order_ids"]

    provider_response = client.post(
        "/api/v1/iot-providers",
        headers=headers,
        json={
            "code": f"SANDBOX_{uuid4().hex[:6].upper()}",
            "name": "本地 IoT 沙箱",
            "adapter_kind": "SANDBOX",
            "severity_mapping": {"FATAL": "CRITICAL"},
            "correlation_minutes": 30,
        },
    )
    assert provider_response.status_code == 200, provider_response.text
    provider = provider_response.json()["data"]
    assert provider["capability_state"] == "SANDBOX_VERIFIED"

    binding_response = client.post(
        "/api/v1/iot-device-bindings",
        headers=headers,
        json={
            "provider_id": provider["id"],
            "device_id": device["id"],
            "external_device_key": "fire-pump-001",
            "reason": "本地沙箱接入验收",
        },
    )
    assert binding_response.status_code == 200, binding_response.text

    source_event_id = f"evt-{uuid4()}"
    event_body = {
        "provider_id": provider["id"],
        "external_device_key": "fire-pump-001",
        "source_event_id": source_event_id,
        "source_time": datetime.now(timezone.utc).isoformat(),
        "alarm_type": "START_FAILURE",
        "title": "消防泵启动失败",
        "severity": "FATAL",
        "payload": {"error_code": "E101", "token": "must-be-dropped"},
    }
    ingested = client.post("/api/v1/iot-alarm-events/ingest", headers=headers, json=event_body)
    assert ingested.status_code == 200, ingested.text
    alarm = ingested.json()["data"]["alarm"]
    assert alarm["severity"] == "CRITICAL"
    assert alarm["work_order_id"] is not None
    assert alarm["events"][0]["payload"] == {"error_code": "E101"}

    replay_event = client.post("/api/v1/iot-alarm-events/ingest", headers=headers, json=event_body)
    assert replay_event.status_code == 200, replay_event.text
    assert replay_event.json()["data"]["replayed"] is True
    conflict_body = {**event_body, "payload": {"error_code": "DIFFERENT"}}
    conflict = client.post(
        "/api/v1/iot-alarm-events/ingest", headers=headers, json=conflict_body
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["code"] == "IOT_EVENT_CONFLICT"

    escalated = client.post(
        "/api/v1/iot-alarms/sweep-escalations",
        headers=headers,
        json={
            "as_of": (
                datetime.fromisoformat(event_body["source_time"]) + timedelta(minutes=130)
            ).isoformat()
        },
    )
    assert escalated.status_code == 200, escalated.text
    detail = client.get(f"/api/v1/iot-alarms/{alarm['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert [item["level"] for item in detail.json()["data"]["escalations"]] == [1, 2, 3]

    acknowledged = client.post(
        f"/api/v1/iot-alarms/{alarm['id']}/acknowledge",
        headers=headers,
        json={"expected_version": alarm["lock_version"]},
    )
    assert acknowledged.status_code == 200, acknowledged.text
    acknowledged_alarm = acknowledged.json()["data"]
    resolved = client.post(
        f"/api/v1/iot-alarms/{alarm['id']}/resolve",
        headers=headers,
        json={
            "expected_version": acknowledged_alarm["lock_version"],
            "reason": "已切换备用泵并完成复测",
        },
    )
    assert resolved.status_code == 200, resolved.text
    resolved_alarm = resolved.json()["data"]
    closed = client.post(
        f"/api/v1/iot-alarms/{alarm['id']}/close",
        headers=headers,
        json={"expected_version": resolved_alarm["lock_version"]},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["data"]["status"] == "CLOSED"


def test_facility_scope_external_truthfulness_and_retirement(client) -> None:
    admin = _headers()
    forged = client.get(
        "/api/v1/facility-devices",
        headers=_headers(uid=999999, permissions=["facility_device:read"]),
    )
    assert forged.status_code in {401, 403}, forged.text
    duplicate_query = client.get(
        "/api/v1/facility-devices?page=1&page=2",
        headers=admin,
    )
    assert duplicate_query.status_code == 400, duplicate_query.text
    assert duplicate_query.json()["code"] == "DUPLICATE_QUERY_PARAMETER"
    park = client.post(
        "/api/v1/parks",
        headers=admin,
        json={"name": f"隔离园-{uuid4().hex[:8]}", "address": "隔离地址"},
    ).json()["data"]
    device = client.post(
        "/api/v1/facility-devices",
        headers=admin,
        json={
            "park_id": park["id"],
            "device_code": f"ELEVATOR-{uuid4().hex[:8]}",
            "name": "客梯一号",
            "device_type": "ELEVATOR",
            "location": "B 栋",
        },
    ).json()["data"]
    unknown_field = client.post(
        "/api/v1/facility-devices",
        headers=admin,
        json={
            "park_id": park["id"],
            "device_code": f"UNKNOWN-{uuid4().hex[:8]}",
            "name": "禁止未知字段",
            "device_type": "FIRE",
            "location": "测试位置",
            "tenant_id": 999,
        },
    )
    assert unknown_field.status_code == 422, unknown_field.text

    no_scope = _headers(
        permissions=["facility_device:read"], park_ids=[], mode="NONE"
    )
    hidden = client.get(f"/api/v1/facility-devices/{device['id']}", headers=no_scope)
    assert hidden.status_code == 404, hidden.text

    other_tenant = _headers(tenant_id=2, permissions=["facility_device:read"])
    cross_tenant = client.get(
        f"/api/v1/facility-devices/{device['id']}", headers=other_tenant
    )
    assert cross_tenant.status_code in {401, 404}, cross_tenant.text

    http_provider = client.post(
        "/api/v1/iot-providers",
        headers=admin,
        json={
            "code": f"UNVERIFIED_{uuid4().hex[:6]}",
            "name": "未验证外部平台",
            "adapter_kind": "HTTP",
            "environment": "PROD",
            "credential_ref": "vault://iot/provider",
        },
    )
    assert http_provider.status_code == 200, http_provider.text
    provider = http_provider.json()["data"]
    assert provider["status"] == "NOT_CONNECTED"
    assert provider["capability_state"] == "EXTERNAL_CONNECTION_NOT_VERIFIED"
    rejected_binding = client.post(
        "/api/v1/iot-device-bindings",
        headers=admin,
        json={
            "provider_id": provider["id"],
            "device_id": device["id"],
            "external_device_key": "unverified-001",
            "reason": "验证不可虚报真实连接",
        },
    )
    assert rejected_binding.status_code == 409, rejected_binding.text
    assert rejected_binding.json()["code"] == "IOT_PROVIDER_UNAVAILABLE"

    retired = client.post(
        f"/api/v1/facility-devices/{device['id']}/retire",
        headers=admin,
        json={"expected_version": device["lock_version"], "reason": "设备报废"},
    )
    assert retired.status_code == 200, retired.text
    retired_data = retired.json()["data"]
    assert retired_data["status"] == "RETIRED"
    assert retired_data["history"][-1]["action"] == "RETIRED"
    stale_update = client.put(
        f"/api/v1/facility-devices/{device['id']}",
        headers=admin,
        json={
            "expected_version": device["lock_version"],
            "reason": "不应成功",
            "location": "错误位置",
        },
    )
    assert stale_update.status_code == 409, stale_update.text

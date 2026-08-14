"""Regression coverage for the completed Investment CRM journey."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import timedelta

from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.identity import (
    Permission,
    Role,
    RolePermission,
    Tenant,
    User,
    UserParkScope,
    UserRole,
)
from app.infrastructure.database.models.investment import (
    LeadActivity,
    LeadChannelInboxEvent,
    LeadIntentVersion,
)
from app.infrastructure.database.models.workflow import ApprovalRequest


def _headers(
    *,
    user_id: int = 1,
    tenant_id: int = 1,
    permissions: list[str] | None = None,
    park_ids: list[int] | None = None,
    park_scope_mode: str = "ALL",
) -> dict[str, str]:
    token = create_access_token(
        subject="admin",
        claims={
            "uid": user_id,
            "tenant_id": tenant_id,
            "permissions": permissions if permissions is not None else ["*"],
            "park_ids": park_ids or [],
            "park_scope_mode": park_scope_mode,
            "tv": 0,
        },
    )
    return {"Authorization": f"Bearer {token}"}


def _post(client, path: str, headers: dict[str, str], payload: dict) -> dict:
    response = client.post(path, headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _park(client, headers: dict[str, str], name: str) -> dict:
    return _post(client, "/api/v1/parks", headers, {"name": name, "address": "synthetic"})


def _unit(client, headers: dict[str, str], park_id: int, code: str) -> dict:
    return _post(
        client,
        "/api/v1/units",
        headers,
        {
            "park_id": park_id,
            "name": code,
            "code": code,
            "rentable_area": "100",
            "usage_type": "FACTORY",
            "base_rent_price": "25",
            "status": "VACANT",
        },
    )


def _publish_intent_definition(client, headers: dict[str, str]) -> None:
    created = _post(
        client,
        "/api/v1/approval-definitions",
        headers,
        {
            "code": "LEAD_INTENT_DEFAULT",
            "name": "招商意向审批",
            "biz_type": "LEAD_INTENT",
            "steps": [
                {
                    "step_order": 1,
                    "name": "园区经理审批",
                    "approval_mode": "ANY",
                    "min_approvals": 1,
                    "sla_hours": 24,
                    "assignees": [{"user_id": 1}],
                }
            ],
        },
    )
    draft = next(row for row in created["versions"] if row["status"] == "DRAFT")
    _post(
        client,
        f"/api/v1/approval-definitions/{created['id']}/publish",
        headers,
        {"version_id": draft["id"], "expected_lock_version": 0},
    )


def test_published_rule_excludes_member_after_park_scope_revocation(
    client, db_session
) -> None:
    headers = _headers()
    park = _park(client, headers, "招商撤权园")
    member = User(
        tenant_id=1,
        username="crm-revoked-member",
        password_hash=hash_password("synthetic-password"),
        real_name="撤权招商员",
        status="ACTIVE",
        all_parks=False,
    )
    db_session.add(member)
    db_session.flush()
    grant = UserParkScope(tenant_id=1, user_id=int(member.id), park_id=int(park["id"]))
    db_session.add(grant)
    db_session.commit()

    rule = _post(
        client,
        "/api/v1/crm/assignment-rules",
        headers,
        {
            "park_id": park["id"],
            "code": "REVOKED_SCOPE_MEMBER",
            "name": "撤权成员排除规则",
            "trigger": "MANUAL_CREATE",
            "members": [
                {
                    "user_id": int(member.id),
                    "capacity": 10,
                    "weight": 1,
                    "member_order": 1,
                }
            ],
        },
    )
    _post(
        client,
        f"/api/v1/crm/assignment-rules/{rule['id']}/publish",
        headers,
        {"expected_lock_version": rule["lock_version"]},
    )

    db_session.delete(grant)
    db_session.commit()
    preview_response = client.get(
        "/api/v1/crm/assignment-rules/preview",
        headers=headers,
        params={"park_id": park["id"], "trigger": "MANUAL_CREATE"},
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()["data"]
    assert preview["winner_user_id"] is None
    assert preview["fallback_reason"] == "NO_ELIGIBLE_MEMBER"
    assert preview["members"] == [
        {
            "user_id": int(member.id),
            "capacity": 10,
            "weight": 1,
            "member_order": 1,
            "open_count": 0,
            "workload_ratio": 0.0,
            "last_assigned_at": None,
            "eligible": False,
            "exclusion_reason": "PARK_SCOPE_REVOKED",
        }
    ]

    lead = _post(
        client,
        "/api/v1/leads",
        headers,
        {
            "park_id": park["id"],
            "name": "撤权后回落公海企业",
            "contact_phone": "13800138088",
        },
    )
    assert lead["owner_user_id"] is None
    assert lead["pool_status"] == "PUBLIC"
    detail = client.get(f"/api/v1/leads/{lead['id']}", headers=headers).json()["data"]
    assert detail["assignment_events"][0]["event_type"] == "AUTO_ASSIGN_FALLBACK"
    assert detail["assignment_events"][0]["decision"]["members"][0][
        "exclusion_reason"
    ] == "PARK_SCOPE_REVOKED"


def test_rule_viewing_intent_approval_and_lock_journey(client, db_session) -> None:
    headers = _headers()
    park = _park(client, headers, "招商闭环园")
    unit = _unit(client, headers, park["id"], "CRM-A-101")

    rule = _post(
        client,
        "/api/v1/crm/assignment-rules",
        headers,
        {
            "park_id": park["id"],
            "code": "MANUAL_CREATE_PRIMARY",
            "name": "新线索最小负荷分配",
            "trigger": "MANUAL_CREATE",
            "recycle_after_hours": 72,
            "members": [
                {"user_id": 1, "capacity": 100, "weight": 1, "member_order": 1}
            ],
        },
    )
    published = _post(
        client,
        f"/api/v1/crm/assignment-rules/{rule['id']}/publish",
        headers,
        {"expected_lock_version": rule["lock_version"]},
    )
    assert published["current_version"] == 1

    lead = _post(
        client,
        "/api/v1/leads",
        headers,
        {
            "park_id": park["id"],
            "name": "闭环制造企业",
            "contact_phone": "13800138001",
            "intent_area": "80",
            "desired_usage": "FACTORY",
            "budget_unit_price": "30",
        },
    )
    assert lead["owner_user_id"] == 1
    detail = client.get(f"/api/v1/leads/{lead['id']}", headers=headers).json()["data"]
    auto_event = detail["assignment_events"][0]
    assert auto_event["event_type"] == "AUTO_ASSIGN"
    assert auto_event["rule_version_id"] is not None
    assert auto_event["decision"]["winner_user_id"] == 1

    start = utc_now() + timedelta(days=1)
    viewing = _post(
        client,
        f"/api/v1/leads/{lead['id']}/viewings",
        headers,
        {
            "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(hours=1)).isoformat(),
            "unit_ids": [unit["id"]],
            "visitor_name": "企业代表",
            "visitor_count": 2,
        },
    )
    confirmed = _post(
        client,
        f"/api/v1/crm/viewings/{viewing['id']}/transition",
        headers,
        {"expected_version": viewing["lock_version"], "status": "CONFIRMED"},
    )
    completed = _post(
        client,
        f"/api/v1/crm/viewings/{viewing['id']}/transition",
        headers,
        {
            "expected_version": confirmed["lock_version"],
            "status": "COMPLETED",
            "outcome": "厂房条件匹配，进入意向审批",
            "next_follow_up_at": (start + timedelta(days=1)).isoformat(),
            "idempotency_key": "viewing-complete-crm-001",
        },
    )
    retried = _post(
        client,
        f"/api/v1/crm/viewings/{viewing['id']}/transition",
        headers,
        {
            "expected_version": confirmed["lock_version"],
            "status": "COMPLETED",
            "outcome": "ignored retry",
            "idempotency_key": "viewing-complete-crm-001",
        },
    )
    assert completed["status"] == retried["status"] == "COMPLETED"
    visits = db_session.scalars(
        select(LeadActivity).where(
            LeadActivity.lead_id == lead["id"], LeadActivity.activity_type == "VISIT"
        )
    ).all()
    assert len(visits) == 1

    _publish_intent_definition(client, headers)
    intent = _post(
        client,
        f"/api/v1/leads/{lead['id']}/intent",
        headers,
        {
            "starts_on": utc_now().date().isoformat(),
            "ends_on": (utc_now().date() + timedelta(days=365)).isoformat(),
            "valid_until": (utc_now() + timedelta(days=30)).isoformat(),
            "proposed_unit_price": "28.50",
            "currency": "CNY",
            "remark": "价格和租期待审批",
            "units": [{"unit_id": unit["id"], "requested_area": "80"}],
        },
    )
    denied = client.post(
        f"/api/v1/leads/{lead['id']}/unit-locks",
        headers=headers,
        json={
            "expected_version": client.get(
                f"/api/v1/leads/{lead['id']}", headers=headers
            ).json()["data"]["lock_version"],
            "unit_id": unit["id"],
            "intent_id": intent["id"],
        },
    )
    assert denied.status_code == 409
    assert denied.json()["code"] == "INTENT_LOCK_GATE_DENIED"

    foreign_lead = _post(
        client,
        "/api/v1/leads",
        headers,
        {
            "park_id": park["id"],
            "name": "异线索意向门禁",
            "contact_phone": "13800138009",
            "intent_area": "80",
        },
    )
    foreign_intent = _post(
        client,
        f"/api/v1/leads/{foreign_lead['id']}/intent",
        headers,
        {
            "starts_on": utc_now().date().isoformat(),
            "ends_on": (utc_now().date() + timedelta(days=365)).isoformat(),
            "valid_until": (utc_now() + timedelta(days=30)).isoformat(),
            "proposed_unit_price": "28.50",
            "currency": "CNY",
            "units": [{"unit_id": unit["id"], "requested_area": "80"}],
        },
    )
    current_lead = client.get(f"/api/v1/leads/{lead['id']}", headers=headers).json()["data"]
    foreign_gate = client.post(
        f"/api/v1/leads/{lead['id']}/unit-locks",
        headers=headers,
        json={
            "expected_version": current_lead["lock_version"],
            "unit_id": unit["id"],
            "intent_id": foreign_intent["id"],
            "duration_hours": 48,
        },
    )
    assert foreign_gate.status_code == 409
    assert foreign_gate.json()["code"] == "INTENT_LOCK_GATE_DENIED"

    submitted = _post(
        client,
        f"/api/v1/crm/intents/{intent['id']}/submit",
        headers,
        {
            "expected_version": intent["lock_version"],
            "definition_code": "LEAD_INTENT_DEFAULT",
            "idempotency_key": "intent-submit-crm-001",
            "priority": "HIGH",
        },
    )
    assert submitted["status"] == "PENDING"
    tasks = client.get("/api/v1/approval-tasks", headers=headers).json()["data"]["items"]
    task = next(row for row in tasks if row["biz_type"] == "LEAD_INTENT")
    approved = _post(
        client,
        f"/api/v1/approval-tasks/{task['id']}/decide",
        headers,
        {
            "action": "APPROVE",
            "remark": "同意锁房",
            "expected_version": task["approval_lock_version"],
            "idempotency_key": "intent-approve-crm-001",
            "override_reason": "合成验收租户由管理员执行单人审批",
        },
    )
    assert approved["status"] == "APPROVED"
    refreshed_intent = client.get(
        f"/api/v1/crm/intents/{intent['id']}", headers=headers
    ).json()["data"]
    assert refreshed_intent["status"] == "APPROVED"
    assert refreshed_intent["approval_deep_link"].endswith(
        str(refreshed_intent["approval_request_id"])
    )

    approval = db_session.get(ApprovalRequest, refreshed_intent["approval_request_id"])
    intent_version = db_session.get(LeadIntentVersion, refreshed_intent["versions"][0]["id"])
    assert approval is not None and intent_version is not None
    for non_approved_status in ("REJECTED", "RETURNED", "WITHDRAWN"):
        approval.status = non_approved_status
        db_session.commit()
        current_lead = client.get(
            f"/api/v1/leads/{lead['id']}", headers=headers
        ).json()["data"]
        rejected_gate = client.post(
            f"/api/v1/leads/{lead['id']}/unit-locks",
            headers=headers,
            json={
                "expected_version": current_lead["lock_version"],
                "unit_id": unit["id"],
                "intent_id": intent["id"],
                "duration_hours": 48,
            },
        )
        assert rejected_gate.status_code == 409
        assert rejected_gate.json()["code"] == "INTENT_LOCK_GATE_DENIED"

    approval.status = "APPROVED"
    original_valid_until = intent_version.valid_until
    intent_version.valid_until = utc_now() - timedelta(seconds=1)
    db_session.commit()
    current_lead = client.get(f"/api/v1/leads/{lead['id']}", headers=headers).json()["data"]
    expired_gate = client.post(
        f"/api/v1/leads/{lead['id']}/unit-locks",
        headers=headers,
        json={
            "expected_version": current_lead["lock_version"],
            "unit_id": unit["id"],
            "intent_id": intent["id"],
            "duration_hours": 48,
        },
    )
    assert expired_gate.status_code == 409
    assert expired_gate.json()["code"] == "INTENT_EXPIRED"
    intent_version.valid_until = original_valid_until
    db_session.commit()

    refreshed_lead = client.get(f"/api/v1/leads/{lead['id']}", headers=headers).json()["data"]
    locked = _post(
        client,
        f"/api/v1/leads/{lead['id']}/unit-locks",
        headers,
        {
            "expected_version": refreshed_lead["lock_version"],
            "unit_id": unit["id"],
            "intent_id": intent["id"],
            "duration_hours": 48,
        },
    )
    assert locked["intent_application_id"] == intent["id"]
    assert locked["intent_version_id"] == refreshed_intent["versions"][0]["id"]


def _signed_headers(secret: str, event_id: str, raw: bytes) -> dict[str, str]:
    timestamp = str(int(time.time()))
    body_sha = hashlib.sha256(raw).hexdigest()
    signing_input = f"v1\n{timestamp}\n{event_id}\n{body_sha}".encode()
    signature = "v1=" + hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-KWZY-Timestamp": timestamp,
        "X-KWZY-Event-Id": event_id,
        "X-KWZY-Signature": signature,
    }


def test_signed_channel_idempotency_quarantine_and_safe_replay(
    client, db_session, monkeypatch
) -> None:
    headers = _headers()
    park = _park(client, headers, "渠道接入园")
    secret = "synthetic-channel-secret-32-bytes"
    monkeypatch.setenv("KWZY_TEST_LEAD_CHANNEL_SECRET", secret)
    channel = _post(
        client,
        "/api/v1/crm/channels",
        headers,
        {
            "park_id": park["id"],
            "code": "LOCAL_WEB",
            "name": "本地合约验收渠道",
            "secret_env_key": "KWZY_TEST_LEAD_CHANNEL_SECRET",
            "enabled": True,
            "allow_auto_assign": False,
        },
    )
    raw = json.dumps(
        {"name": "渠道企业", "contact_phone": "13800138002", "intent_area": "60"},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    signed = _signed_headers(secret, "evt-local-001", raw)
    received = client.post(
        f"/api/v1/public/lead-channels/{channel['public_id']}/events",
        headers=signed,
        content=raw,
    )
    assert received.status_code == 200, received.text
    event = received.json()["data"]
    assert event["status"] == "ACCEPTED"
    assert event["lead_id"] is not None
    assert "payload_ciphertext" not in event
    assert "13800138002" not in json.dumps(event, ensure_ascii=False)

    repeated = client.post(
        f"/api/v1/public/lead-channels/{channel['public_id']}/events",
        headers=signed,
        content=raw,
    )
    assert repeated.status_code == 200
    assert repeated.json()["data"]["id"] == event["id"]

    invalid_raw = json.dumps(
        {"name": "未知字段企业", "contact_phone": "13800138003", "owner_user_id": 999},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    quarantined = client.post(
        f"/api/v1/public/lead-channels/{channel['public_id']}/events",
        headers=_signed_headers(secret, "evt-local-002", invalid_raw),
        content=invalid_raw,
    )
    assert quarantined.status_code == 200, quarantined.text
    quarantine_event = quarantined.json()["data"]
    assert quarantine_event["status"] == "QUARANTINED"
    assert quarantine_event["failure_code"] == "CHANNEL_PAYLOAD_FIELD_DENIED"

    replayed = client.post(
        f"/api/v1/crm/channels/{channel['id']}/events/{quarantine_event['id']}/replay",
        headers=headers,
    )
    assert replayed.status_code == 200, replayed.text
    assert replayed.json()["data"]["status"] == "QUARANTINED"
    assert replayed.json()["data"]["replay_count"] == 1

    stored = db_session.get(LeadChannelInboxEvent, quarantine_event["id"])
    assert stored is not None
    assert stored.payload_ciphertext
    assert invalid_raw.decode("utf-8") not in stored.payload_ciphertext
    assert stored.payload_key_ref == "KWZY_TEST_LEAD_CHANNEL_SECRET"

    tampered = dict(_signed_headers(secret, "evt-local-003", raw))
    tampered["X-KWZY-Signature"] = "v1=" + "0" * 64
    rejected = client.post(
        f"/api/v1/public/lead-channels/{channel['public_id']}/events",
        headers=tampered,
        content=raw,
    )
    assert rejected.status_code == 401
    assert rejected.json()["code"] == "CHANNEL_AUTH_FAILED"


def test_completion_routes_fail_closed_for_permission_park_tenant_and_pollution(
    client, db_session, monkeypatch
) -> None:
    admin = _headers()
    allowed = _park(client, admin, "招商安全园-A")
    denied = _park(client, admin, "招商安全园-B")
    unit = _unit(client, admin, allowed["id"], "CRM-SEC-A-101")
    lead = _post(
        client,
        "/api/v1/leads",
        admin,
        {
            "park_id": allowed["id"],
            "name": "权限隔离企业",
            "contact_phone": "13800138111",
            "owner_user_id": 1,
            "auto_assign": False,
        },
    )
    rule = _post(
        client,
        "/api/v1/crm/assignment-rules",
        admin,
        {
            "park_id": allowed["id"],
            "code": "SECURITY_SCOPE_RULE",
            "name": "权限隔离规则",
            "trigger": "CHANNEL_INTAKE",
            "members": [{"user_id": 1, "capacity": 10, "member_order": 1}],
        },
    )
    start = utc_now() + timedelta(days=2)
    viewing = _post(
        client,
        f"/api/v1/leads/{lead['id']}/viewings",
        admin,
        {
            "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(hours=1)).isoformat(),
            "unit_ids": [unit["id"]],
        },
    )
    intent = _post(
        client,
        f"/api/v1/leads/{lead['id']}/intent",
        admin,
        {
            "starts_on": utc_now().date().isoformat(),
            "ends_on": (utc_now().date() + timedelta(days=365)).isoformat(),
            "valid_until": (utc_now() + timedelta(days=30)).isoformat(),
            "proposed_unit_price": "20",
            "units": [{"unit_id": unit["id"], "requested_area": "60"}],
        },
    )
    monkeypatch.setenv("KWZY_TEST_SECURITY_CHANNEL_SECRET", "local-security-secret")
    channel = _post(
        client,
        "/api/v1/crm/channels",
        admin,
        {
            "park_id": allowed["id"],
            "code": "SECURITY_CHANNEL",
            "name": "权限隔离渠道",
            "secret_env_key": "KWZY_TEST_SECURITY_CHANNEL_SECRET",
            "enabled": True,
        },
    )

    read_only = _headers(permissions=["lead:read"])
    forbidden = client.get("/api/v1/crm/assignment-rules", headers=read_only)
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "PERMISSION_DENIED"

    scoped = _headers(park_ids=[denied["id"]], park_scope_mode="LIST")
    for method, path in (
        ("get", f"/api/v1/crm/assignment-rules/{rule['id']}"),
        ("get", f"/api/v1/crm/viewings/{viewing['id']}"),
        ("get", f"/api/v1/crm/intents/{intent['id']}"),
        ("get", f"/api/v1/crm/channels/{channel['id']}"),
    ):
        response = getattr(client, method)(path, headers=scoped)
        assert response.status_code == 404, (path, response.text)

    polluted = client.post(
        "/api/v1/crm/assignment-rules",
        headers=admin,
        json={
            "tenant_id": 999,
            "park_id": allowed["id"],
            "code": "POLLUTED_RULE",
            "name": "参数污染",
            "trigger": "RECYCLE",
            "members": [{"user_id": 1, "capacity": 10, "member_order": 1}],
        },
    )
    assert polluted.status_code == 422

    tenant = Tenant(code="crm-security-t2", name="招商安全租户2", status="ACTIVE")
    db_session.add(tenant)
    db_session.flush()
    user = User(
        tenant_id=int(tenant.id),
        username="crm-security-admin",
        password_hash=hash_password("synthetic-password"),
        real_name="租户2管理员",
        status="ACTIVE",
        all_parks=True,
    )
    role = Role(
        tenant_id=int(tenant.id),
        code="CRM_SECURITY_ADMIN",
        name="招商安全管理员",
        status="ACTIVE",
        all_parks=True,
    )
    db_session.add_all([user, role])
    db_session.flush()
    star = db_session.scalars(select(Permission).where(Permission.code == "*")).one()
    db_session.add_all(
        [
            UserRole(tenant_id=int(tenant.id), user_id=int(user.id), role_id=int(role.id)),
            RolePermission(
                tenant_id=int(tenant.id),
                role_id=int(role.id),
                permission_id=int(star.id),
            ),
        ]
    )
    db_session.commit()
    foreign = _headers(user_id=int(user.id), tenant_id=int(tenant.id))
    assert client.get(
        f"/api/v1/crm/assignment-rules/{rule['id']}", headers=foreign
    ).status_code == 404
    assert client.get(f"/api/v1/crm/viewings/{viewing['id']}", headers=foreign).status_code == 404
    assert client.get(f"/api/v1/crm/intents/{intent['id']}", headers=foreign).status_code == 404
    assert client.get(f"/api/v1/crm/channels/{channel['id']}", headers=foreign).status_code == 404

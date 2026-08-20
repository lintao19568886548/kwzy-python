"""Real HTTP engagement journeys, authorization, and strict-contract acceptance."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.facility_ops import (
    TenantServicePrincipal,
    TenantServicePrincipalPark,
)
from app.infrastructure.database.models.identity import User
from app.infrastructure.database.models.park_property import Park
from app.infrastructure.database.models.party import Party, PartyParkRelation, PartyRole
from app.modules.identity.application.bootstrap import ensure_default_tenant


def _headers(
    *,
    user_id: int,
    tenant_id: int,
    permissions: list[str] | None = None,
    park_ids: list[int] | None = None,
    mode: str = "ALL",
) -> dict[str, str]:
    token = create_access_token(
        subject=f"engagement-http-{user_id}",
        claims={
            "uid": user_id,
            "tenant_id": tenant_id,
            "permissions": permissions or ["*"],
            "park_ids": park_ids or [],
            "park_scope_mode": mode,
            "tv": 0,
        },
    )
    return {"Authorization": f"Bearer {token}"}


def _key(headers: dict[str, str], value: str) -> dict[str, str]:
    return {**headers, "Idempotency-Key": value}


def _seed_principal(session: Session) -> dict[str, int]:
    tenant = ensure_default_tenant(session)
    user = session.scalar(
        select(User).where(User.tenant_id == tenant.id, User.username == "admin")
    )
    assert user is not None
    park = Park(tenant_id=tenant.id, name=f"参与验收园-{uuid4().hex[:8]}", status="ACTIVE")
    session.add(park)
    session.flush()
    party = Party(
        tenant_id=tenant.id,
        party_type="ORGANIZATION",
        name="HTTP 验收企业",
        credit_code=f"91310{uuid4().hex[:13].upper()}",
        status="ACTIVE",
        risk_status="NORMAL",
    )
    session.add(party)
    session.flush()
    role = PartyRole(
        tenant_id=tenant.id,
        party_id=party.id,
        role_code="TENANT",
        status="ACTIVE",
    )
    session.add(role)
    session.flush()
    session.add(
        PartyParkRelation(
            tenant_id=tenant.id,
            party_id=party.id,
            park_id=park.id,
            party_role_id=role.id,
            status="ACTIVE",
        )
    )
    principal = TenantServicePrincipal(
        tenant_id=tenant.id,
        user_id=user.id,
        party_id=party.id,
        status="ACTIVE",
        created_by=user.id,
    )
    session.add(principal)
    session.flush()
    session.add(
        TenantServicePrincipalPark(
            tenant_id=tenant.id,
            principal_id=principal.id,
            park_id=park.id,
        )
    )
    session.commit()
    return {
        "tenant_id": int(tenant.id),
        "user_id": int(user.id),
        "park_id": int(park.id),
        "party_id": int(party.id),
    }


def _approval_definition(client, headers: dict[str, str], biz_type: str) -> str:
    code = f"ENG_{biz_type.removeprefix('ENGAGEMENT_')}_{uuid4().hex[:5]}".upper()
    response = client.post(
        "/api/v1/approval-definitions",
        headers=headers,
        json={
            "code": code,
            "name": f"{biz_type} HTTP 验收审批",
            "biz_type": biz_type,
            "steps": [
                {
                    "step_order": 1,
                    "name": "管理员复核",
                    "approval_mode": "ANY",
                    "min_approvals": 1,
                    "sla_hours": 24,
                    "assignees": [{"user_id": 1}],
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    definition = response.json()["data"]
    draft = next(item for item in definition["versions"] if item["status"] == "DRAFT")
    published = client.post(
        f"/api/v1/approval-definitions/{definition['id']}/publish",
        headers=headers,
        json={"version_id": draft["id"], "expected_lock_version": 0},
    )
    assert published.status_code == 200, published.text
    return code


def _approve(client, headers: dict[str, str], approval_id: int) -> None:
    detail_response = client.get(f"/api/v1/approvals/{approval_id}", headers=headers)
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()["data"]
    task = next(item for item in detail["tasks"] if item["status"] == "PENDING")
    decided = client.post(
        f"/api/v1/approval-tasks/{task['id']}/decide",
        headers=headers,
        json={
            "action": "APPROVE",
            "expected_version": detail["lock_version"],
            "idempotency_key": f"engagement-approve-{uuid4().hex}",
            "override_reason": "engagement HTTP 独立验收",
        },
    )
    assert decided.status_code == 200, decided.text


def test_engagement_real_http_staff_and_tenant_journeys(client, db_session: Session) -> None:
    seed = _seed_principal(db_session)
    headers = _headers(
        user_id=seed["user_id"], tenant_id=seed["tenant_id"]
    )
    now = utc_now()

    policy_payload = {
        "park_id": seed["park_id"],
        "code": f"POL_{uuid4().hex[:6]}",
        "title": "HTTP 本地政策指引",
        "summary": "只表达本地相关性，不代表政府资格。",
        "content_text": "HTTP 政策正文。",
        "category": "INDUSTRY",
        "region_code": "CN-SH",
        "source_type": "LOCAL",
        "source_system": "KWZY",
        "source_identifier": "HTTP-SYNTHETIC-POLICY",
        "source_publisher": "园区政策服务中心",
        "source_url": "https://policy.example.com/http",
        "allowed_hosts": ["policy.example.com"],
        "source_published_at": now.isoformat(),
        "effective_on": now.date().isoformat(),
        "expires_on": (now + timedelta(days=30)).date().isoformat(),
        "attachment_ids": [],
        "applicability": [],
    }
    created = client.post(
        "/api/v1/engagement/staff/policies", headers=headers, json=policy_payload
    )
    assert created.status_code == 200, created.text
    policy = created.json()["data"]
    definition = _approval_definition(client, headers, "ENGAGEMENT_POLICY")
    policy_submit_key = "p" * 128
    policy_submit_body = {
        "expected_version": policy["lock_version"],
        "definition_code": definition,
    }
    submitted = client.post(
        f"/api/v1/engagement/staff/policies/{policy['id']}/submit",
        headers=_key(headers, policy_submit_key),
        json=policy_submit_body,
    )
    assert submitted.status_code == 200, submitted.text
    policy = submitted.json()["data"]
    submit_replay = client.post(
        f"/api/v1/engagement/staff/policies/{policy['id']}/submit",
        headers=_key(headers, policy_submit_key),
        json=policy_submit_body,
    )
    assert submit_replay.status_code == 200, submit_replay.text
    assert (
        submit_replay.json()["data"]["version"]["approval_id"]
        == policy["version"]["approval_id"]
    )
    _approve(client, headers, policy["version"]["approval_id"])
    published = client.post(
        f"/api/v1/engagement/staff/policies/{policy['id']}/publish",
        headers=headers,
        json={"expected_version": policy["lock_version"]},
    )
    assert published.status_code == 200, published.text
    policy = published.json()["data"]
    match_key = f"policy-match-{uuid4().hex}"
    matched = client.post(
        f"/api/v1/engagement/tenant/policies/{policy['id']}/match",
        headers=_key(headers, match_key),
    )
    replay = client.post(
        f"/api/v1/engagement/tenant/policies/{policy['id']}/match",
        headers=_key(headers, match_key),
    )
    assert matched.status_code == replay.status_code == 200
    assert matched.json()["data"] == replay.json()["data"]
    assert matched.json()["data"]["official_eligibility"] == "NOT_DETERMINED"
    consultation_key = f"policy-consult-{uuid4().hex}"
    consultation_body = {
        "park_id": seed["park_id"],
        "subject": "HTTP 咨询",
        "question": "本地服务范围是什么？",
    }
    consultation = client.post(
        f"/api/v1/engagement/tenant/policies/{policy['id']}/consultations",
        headers=_key(headers, consultation_key),
        json=consultation_body,
    )
    consultation_replay = client.post(
        f"/api/v1/engagement/tenant/policies/{policy['id']}/consultations",
        headers=_key(headers, consultation_key),
        json=consultation_body,
    )
    assert consultation.status_code == consultation_replay.status_code == 200
    assert consultation.json()["data"]["id"] == consultation_replay.json()["data"]["id"]
    revised = client.put(
        f"/api/v1/engagement/staff/policies/{policy['id']}/draft",
        headers=_key(headers, f"policy-revise-{uuid4().hex}"),
        json={**policy_payload, "expected_version": policy["lock_version"], "title": "待审修订"},
    )
    assert revised.status_code == 200, revised.text
    assert revised.json()["data"]["current_version"] == 2
    tenant_policy = client.get(
        f"/api/v1/engagement/tenant/policies/{policy['id']}", headers=headers
    )
    assert tenant_policy.status_code == 200
    assert tenant_policy.json()["data"]["version"]["title"] == policy_payload["title"]

    service_payload = {
        "park_id": seed["park_id"],
        "code": f"SVC_{uuid4().hex[:6]}",
        "title": "HTTP 企业服务",
        "description": "园区内部服务，不连接外部供应商。",
        "category": "ADVISORY",
        "provider_type": "INTERNAL",
        "provider_name": "园区服务中心",
        "provider_state": "LOCAL",
        "sla_hours": 24,
        "appointment_required": False,
        "eligibility": [],
        "evidence_rules": [],
        "price_amount": None,
        "currency": "CNY",
    }
    service_response = client.post(
        "/api/v1/engagement/staff/services", headers=headers, json=service_payload
    )
    assert service_response.status_code == 200, service_response.text
    catalog = service_response.json()["data"]
    service_definition = _approval_definition(client, headers, "ENGAGEMENT_SERVICE")
    submitted = client.post(
        f"/api/v1/engagement/staff/services/{catalog['id']}/submit",
        headers=_key(headers, f"service-submit-{uuid4().hex}"),
        json={
            "expected_version": catalog["lock_version"],
            "definition_code": service_definition,
        },
    )
    assert submitted.status_code == 200, submitted.text
    catalog = submitted.json()["data"]
    _approve(client, headers, catalog["version"]["approval_id"])
    published_service = client.post(
        f"/api/v1/engagement/staff/services/{catalog['id']}/publish",
        headers=headers,
        json={"expected_version": catalog["lock_version"]},
    )
    assert published_service.status_code == 200, published_service.text
    catalog = published_service.json()["data"]
    case_key = f"service-case-{uuid4().hex}"
    case_body = {
        "catalog_id": catalog["id"],
        "priority": "MEDIUM",
        "subject": "HTTP 服务申请",
        "description": "需要工作人员形成本地处理结果。",
        "contact_last4": "1234",
    }
    case_response = client.post(
        "/api/v1/engagement/tenant/service-cases",
        headers=_key(headers, case_key),
        json=case_body,
    )
    assert case_response.status_code == 200, case_response.text
    case = case_response.json()["data"]
    case_replay = client.post(
        "/api/v1/engagement/tenant/service-cases",
        headers=_key(headers, case_key),
        json=case_body,
    )
    assert case_replay.status_code == 200
    assert case_replay.json()["data"]["id"] == case["id"]
    for target, extra in (
        ("ACCEPTED", {}),
        ("ASSIGNED", {"assigned_to": seed["user_id"]}),
        ("IN_PROGRESS", {}),
        ("RESULT_READY", {"result_summary": "HTTP 本地服务结果"}),
    ):
        response = client.post(
            f"/api/v1/engagement/staff/service-cases/{case['id']}/transition",
            headers=_key(headers, f"case-{target.lower()}-{uuid4().hex}"),
            json={
                "expected_version": case["lock_version"],
                "target_status": target,
                **extra,
            },
        )
        assert response.status_code == 200, response.text
        case = response.json()["data"]
    confirmed = client.post(
        f"/api/v1/engagement/tenant/service-cases/{case['id']}/transition",
        headers=_key(headers, f"case-confirm-{uuid4().hex}"),
        json={"expected_version": case["lock_version"], "target_status": "CONFIRMED"},
    )
    assert confirmed.status_code == 200, confirmed.text
    feedback = client.post(
        f"/api/v1/engagement/tenant/service-cases/{case['id']}/feedback",
        headers=headers,
        json={"score": 5, "comment": "HTTP 服务完成"},
    )
    assert feedback.status_code == 200, feedback.text

    activity_payload = {
        "park_id": seed["park_id"],
        "code": f"ACT_{uuid4().hex[:6]}",
        "title": "HTTP 园区活动",
        "description": "真实 HTTP 报名和签到验收。",
        "location": "HTTP 会议室",
        "starts_at": (now + timedelta(hours=3)).isoformat(),
        "ends_at": (now + timedelta(hours=5)).isoformat(),
        "registration_opens_at": (now - timedelta(hours=1)).isoformat(),
        "registration_closes_at": (now + timedelta(hours=1)).isoformat(),
        "capacity": 2,
        "attendee_rules": [],
        "audience": [],
        "attachment_ids": [],
        "cancellation_terms": "开始前允许取消。",
    }
    activity_response = client.post(
        "/api/v1/engagement/staff/activities", headers=headers, json=activity_payload
    )
    assert activity_response.status_code == 200, activity_response.text
    activity = activity_response.json()["data"]
    activity_definition = _approval_definition(client, headers, "ENGAGEMENT_ACTIVITY")
    submitted = client.post(
        f"/api/v1/engagement/staff/activities/{activity['id']}/submit",
        headers=_key(headers, f"activity-submit-{uuid4().hex}"),
        json={
            "expected_version": activity["lock_version"],
            "definition_code": activity_definition,
        },
    )
    assert submitted.status_code == 200, submitted.text
    activity = submitted.json()["data"]
    _approve(client, headers, activity["version"]["approval_id"])
    published_activity = client.post(
        f"/api/v1/engagement/staff/activities/{activity['id']}/publish",
        headers=headers,
        json={"expected_version": activity["lock_version"]},
    )
    assert published_activity.status_code == 200, published_activity.text
    activity = published_activity.json()["data"]
    registration = client.post(
        f"/api/v1/engagement/tenant/activities/{activity['id']}/registrations",
        headers=_key(headers, f"registration-{uuid4().hex}"),
        json={"attendee_count": 1},
    )
    assert registration.status_code == 200, registration.text
    registration_data = registration.json()["data"]
    checked_in = client.post(
        f"/api/v1/engagement/staff/activity-registrations/{registration_data['id']}/check-in",
        headers=_key(headers, f"checkin-{uuid4().hex}"),
        json={
            "expected_version": registration_data["lock_version"],
            "evidence_note": "HTTP 现场核验",
        },
    )
    assert checked_in.status_code == 200, checked_in.text
    activity_feedback = client.post(
        f"/api/v1/engagement/tenant/activity-registrations/{registration_data['id']}/feedback",
        headers=headers,
        json={"score": 5, "comment": "HTTP 活动有效"},
    )
    assert activity_feedback.status_code == 200, activity_feedback.text

    announcement_payload = {
        "park_id": seed["park_id"],
        "code": f"ANN_{uuid4().hex[:6]}",
        "title": "HTTP 园区公告",
        "content_text": "仅验证站内信，不代表外部渠道送达。",
        "priority": "IMPORTANT",
        "pin_from": None,
        "pin_to": None,
        "publish_at": now.isoformat(),
        "expires_at": (now + timedelta(days=7)).isoformat(),
        "attachment_ids": [],
        "audience": [{"type": "TENANT_PRINCIPAL", "ids": [], "codes": []}],
    }
    announcement_response = client.post(
        "/api/v1/engagement/staff/announcements",
        headers=headers,
        json=announcement_payload,
    )
    assert announcement_response.status_code == 200, announcement_response.text
    announcement = announcement_response.json()["data"]
    announcement_definition = _approval_definition(
        client, headers, "ENGAGEMENT_ANNOUNCEMENT"
    )
    submitted = client.post(
        f"/api/v1/engagement/staff/announcements/{announcement['id']}/submit",
        headers=_key(headers, f"announcement-submit-{uuid4().hex}"),
        json={
            "expected_version": announcement["lock_version"],
            "definition_code": announcement_definition,
        },
    )
    assert submitted.status_code == 200, submitted.text
    announcement = submitted.json()["data"]
    _approve(client, headers, announcement["version"]["approval_id"])
    published_announcement = client.post(
        f"/api/v1/engagement/staff/announcements/{announcement['id']}/publish",
        headers=headers,
        json={"expected_version": announcement["lock_version"]},
    )
    assert published_announcement.status_code == 200, published_announcement.text
    fanout = client.post(
        "/api/v1/engagement/staff/announcements/fanout",
        headers=headers,
        json={"limit": 10},
    )
    assert fanout.status_code == 200, fanout.text
    assert fanout.json()["data"]["production_contacted"] is False
    inbox = client.get("/api/v1/engagement/tenant/announcement-inbox", headers=headers)
    assert inbox.status_code == 200, inbox.text
    delivery = inbox.json()["data"][0]
    read = client.post(
        f"/api/v1/engagement/tenant/announcement-inbox/{delivery['delivery_id']}/read",
        headers=headers,
    )
    assert read.status_code == 200, read.text
    assert read.json()["data"]["status"] == "READ"


def test_engagement_http_rejects_forgery_xss_ssrf_and_foreign_scope(
    client, db_session: Session
) -> None:
    seed = _seed_principal(db_session)
    admin = _headers(user_id=seed["user_id"], tenant_id=seed["tenant_id"])
    base = {
        "park_id": seed["park_id"],
        "code": f"POL_{uuid4().hex[:6]}",
        "title": "严格政策",
        "summary": None,
        "content_text": "安全正文",
        "category": "GENERAL",
        "region_code": None,
        "source_type": "LOCAL",
        "source_system": "KWZY",
        "source_identifier": "STRICT-HTTP",
        "source_publisher": "园区",
        "source_url": None,
        "allowed_hosts": [],
        "source_published_at": None,
        "effective_on": None,
        "expires_on": None,
        "attachment_ids": [],
        "applicability": [],
    }
    unknown = client.post(
        "/api/v1/engagement/staff/policies",
        headers=admin,
        json={**base, "unexpected": True},
    )
    assert unknown.status_code == 422
    duplicate_query = client.get(
        "/api/v1/engagement/overview?view=staff&view=tenant", headers=admin
    )
    assert duplicate_query.status_code == 400
    assert duplicate_query.json()["code"] == "DUPLICATE_QUERY_PARAMETER"
    forged_party = client.post(
        "/api/v1/engagement/tenant/service-cases",
        headers=_key(admin, f"forged-party-{uuid4().hex}"),
        json={
            "catalog_id": 1,
            "party_id": seed["party_id"],
            "subject": "伪造 Party",
            "description": "tenant body 不得接收 party_id",
        },
    )
    assert forged_party.status_code == 422
    xss = client.post(
        "/api/v1/engagement/staff/policies",
        headers=admin,
        json={**base, "content_text": "<script>alert(1)</script>"},
    )
    assert xss.status_code == 400
    ssrf = client.post(
        "/api/v1/engagement/staff/policies",
        headers=admin,
        json={
            **base,
            "source_url": "https://127.0.0.1/internal",
            "allowed_hosts": ["127.0.0.1"],
        },
    )
    assert ssrf.status_code == 400
    denied = _headers(
        user_id=seed["user_id"],
        tenant_id=seed["tenant_id"],
        permissions=["engagement:read"],
    )
    denied.update({"X-Permissions": "engagement:policy_manage", "X-Tenant-Id": "999"})
    forbidden = client.post(
        "/api/v1/engagement/staff/policies", headers=denied, json=base
    )
    assert forbidden.status_code == 403

    created = client.post(
        "/api/v1/engagement/staff/policies", headers=admin, json=base
    )
    assert created.status_code == 200, created.text
    other_park = Park(
        tenant_id=seed["tenant_id"], name=f"隔离园-{uuid4().hex[:8]}", status="ACTIVE"
    )
    db_session.add(other_park)
    db_session.commit()
    scoped = _headers(
        user_id=seed["user_id"],
        tenant_id=seed["tenant_id"],
        permissions=["*"],
        park_ids=[int(other_park.id)],
        mode="LIST",
    )
    hidden = client.get(
        f"/api/v1/engagement/staff/policies/{created.json()['data']['id']}",
        headers=scoped,
    )
    assert hidden.status_code == 404

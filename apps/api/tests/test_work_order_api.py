"""Tenant-service and work-order lifecycle API regression tests."""

from __future__ import annotations

from uuid import uuid4

from app.core.security import create_access_token


def _headers(
    *,
    uid: int = 1,
    username: str = "admin",
    permissions: list[str] | None = None,
    park_ids: list[int] | None = None,
    mode: str = "ALL",
) -> dict[str, str]:
    token = create_access_token(
        subject=username,
        claims={
            "uid": uid,
            "tenant_id": 1,
            "permissions": permissions or ["*"],
            "park_ids": park_ids or [],
            "park_scope_mode": mode,
        },
    )
    return {"Authorization": f"Bearer {token}"}


def _idempotent(headers: dict[str, str], value: str) -> dict[str, str]:
    return {**headers, "Idempotency-Key": value}


def _create_party(client, headers: dict[str, str], park_id: int, name: str) -> dict:
    response = client.post(
        "/api/v1/parties",
        headers=headers,
        json={
            "name": name,
            "party_type": "ORGANIZATION",
            "initial_park_relation": {"park_id": park_id, "role_code": "LESSEE"},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _create_portal_user(
    client,
    admin_headers: dict[str, str],
    *,
    park_id: int,
    suffix: str,
) -> tuple[dict, dict[str, str]]:
    permissions = [
        "tenant_service:request",
        "tenant_service:read_own",
        "tenant_service:quote_decide",
        "tenant_service:accept",
        "tenant_service:rate",
    ]
    role = client.post(
        "/api/v1/system/roles",
        headers=admin_headers,
        json={
            "code": f"TENANT_PORTAL_{suffix}",
            "name": f"租户门户 {suffix}",
            "all_parks": False,
            "permission_codes": permissions,
            "park_ids": [park_id],
        },
    )
    assert role.status_code == 200, role.text
    user = client.post(
        "/api/v1/system/users",
        headers=admin_headers,
        json={
            "username": f"tenant_{suffix}",
            "password": "Tenant-Test-123!",
            "real_name": f"租户 {suffix}",
            "role_ids": [role.json()["data"]["id"]],
            "park_ids": [park_id],
            "all_parks": False,
        },
    )
    assert user.status_code == 200, user.text
    data = user.json()["data"]
    return data, _headers(
        uid=data["id"],
        username=data["username"],
        permissions=permissions,
        park_ids=[park_id],
        mode="LIST",
    )


def _create_assignee(client, admin_headers: dict[str, str], *, suffix: str) -> dict:
    response = client.post(
        "/api/v1/system/users",
        headers=admin_headers,
        json={
            "username": f"operator_{suffix}",
            "password": "Operator-Test-123!",
            "real_name": f"维修人员 {suffix}",
            "role_ids": [],
            "park_ids": [],
            "all_parks": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_tenant_service_quote_rework_acceptance_and_rating(client) -> None:
    admin = _headers()
    park_response = client.post(
        "/api/v1/parks", headers=admin, json={"name": "工单园", "address": "测试地址"}
    )
    assert park_response.status_code == 200, park_response.text
    park_id = park_response.json()["data"]["id"]
    assignee = _create_assignee(client, admin, suffix=uuid4().hex[:8])
    party = _create_party(client, admin, park_id, "承租企业 A")
    tenant_user, tenant = _create_portal_user(
        client,
        admin,
        park_id=park_id,
        suffix=uuid4().hex[:8],
    )
    principal = client.post(
        "/api/v1/tenant-service/principals",
        headers=admin,
        json={
            "user_id": tenant_user["id"],
            "party_id": party["id"],
            "park_ids": [park_id],
        },
    )
    assert principal.status_code == 200, principal.text

    request_key = f"tenant-request-{uuid4()}"
    created = client.post(
        "/api/v1/tenant-service/requests",
        headers=_idempotent(tenant, request_key),
        json={
            "park_id": park_id,
            "title": "电梯异响",
            "description": "电梯运行时有持续异响",
            "contact_name": "王女士",
            "contact_phone": "13800138000",
            "priority": "HIGH",
            "category": "MAINTENANCE",
            "quote_required": True,
        },
    )
    assert created.status_code == 200, created.text
    order = created.json()["data"]
    order_id = order["id"]
    assert order["status"] == "SUBMITTED"
    assert order["contact_phone_masked"] == "138****8000"

    replay = client.post(
        "/api/v1/tenant-service/requests",
        headers=_idempotent(tenant, request_key),
        json={
            "park_id": park_id,
            "title": "电梯异响",
            "description": "电梯运行时有持续异响",
            "contact_name": "王女士",
            "contact_phone": "13800138000",
            "priority": "HIGH",
            "category": "MAINTENANCE",
            "quote_required": True,
        },
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["id"] == order_id

    reused = client.post(
        "/api/v1/tenant-service/requests",
        headers=_idempotent(tenant, request_key),
        json={"park_id": park_id, "title": "不同请求"},
    )
    assert reused.status_code == 409, reused.text
    assert reused.json()["code"] == "IDEMPOTENCY_KEY_REUSED"

    dispatched = client.post(
        f"/api/v1/work-orders/{order_id}/dispatch",
        headers=admin,
        json={
            "expected_version": order["lock_version"],
            "assignee_user_id": assignee["id"],
            "reason": "值班管理员接单",
        },
    )
    assert dispatched.status_code == 200, dispatched.text
    order = dispatched.json()["data"]
    assert order["status"] == "ASSIGNED"

    stale = client.post(
        f"/api/v1/work-orders/{order_id}/start",
        headers=admin,
        json={"expected_version": 1},
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "WORK_ORDER_VERSION_CONFLICT"

    started = client.post(
        f"/api/v1/work-orders/{order_id}/start",
        headers=admin,
        json={"expected_version": order["lock_version"]},
    )
    assert started.status_code == 200, started.text
    order = started.json()["data"]
    assert order["status"] == "IN_PROGRESS"

    quote = client.post(
        f"/api/v1/work-orders/{order_id}/quotes",
        headers=admin,
        json={
            "expected_version": order["lock_version"],
            "currency": "CNY",
            "total_amount": "120.00",
            "remark": "更换导靴",
            "lines": [
                {
                    "line_type": "MATERIAL",
                    "description": "电梯导靴",
                    "quantity": "2",
                    "unit": "个",
                    "unit_price": "60.00",
                    "amount": "120.00",
                }
            ],
        },
    )
    assert quote.status_code == 200, quote.text
    quote_id = quote.json()["data"]["id"]
    submitted = client.post(
        f"/api/v1/work-orders/{order_id}/quotes/{quote_id}/submit",
        headers=admin,
        json={"expected_version": order["lock_version"]},
    )
    assert submitted.status_code == 200, submitted.text
    order = submitted.json()["data"]
    assert order["status"] == "WAITING_QUOTE_APPROVAL"

    quote_decision_key = f"quote-decision-{uuid4()}"
    decided = client.post(
        f"/api/v1/tenant-service/requests/{order_id}/quotes/{quote_id}/decision",
        headers=_idempotent(tenant, quote_decision_key),
        json={"expected_version": order["lock_version"], "decision": "ACCEPT"},
    )
    assert decided.status_code == 200, decided.text
    order = decided.json()["data"]
    assert order["status"] == "IN_PROGRESS_AFTER_QUOTE"
    quote_replay = client.post(
        f"/api/v1/tenant-service/requests/{order_id}/quotes/{quote_id}/decision",
        headers=_idempotent(tenant, quote_decision_key),
        json={"expected_version": order["lock_version"] - 1, "decision": "ACCEPT"},
    )
    assert quote_replay.status_code == 200, quote_replay.text
    quote_key_conflict = client.post(
        f"/api/v1/tenant-service/requests/{order_id}/quotes/{quote_id}/decision",
        headers=_idempotent(tenant, quote_decision_key),
        json={
            "expected_version": order["lock_version"],
            "decision": "REJECT",
            "remark": "同一幂等键不得改变决定",
        },
    )
    assert quote_key_conflict.status_code == 409, quote_key_conflict.text
    assert quote_key_conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert all("actor_user_id" not in event for event in order["timeline"])
    assert all(
        "to_user_id" not in event["detail"] and "from_user_id" not in event["detail"]
        for event in order["timeline"]
    )

    cost_key = f"cost-{uuid4()}"
    cost_body = {
        "expected_version": order["lock_version"],
        "entry_type": "MATERIAL",
        "description": "电梯导靴",
        "quantity": "2",
        "unit": "个",
        "unit_price": "55.00",
    }
    cost = client.post(
        f"/api/v1/work-orders/{order_id}/cost-entries",
        headers=_idempotent(admin, cost_key),
        json=cost_body,
    )
    assert cost.status_code == 200, cost.text
    cost_id = cost.json()["data"]["id"]
    cost_replay = client.post(
        f"/api/v1/work-orders/{order_id}/cost-entries",
        headers=_idempotent(admin, cost_key),
        json=cost_body,
    )
    assert cost_replay.status_code == 200, cost_replay.text
    assert cost_replay.json()["data"]["id"] == cost_id
    conflicting_cost = client.post(
        f"/api/v1/work-orders/{order_id}/cost-entries",
        headers=_idempotent(admin, cost_key),
        json={**cost_body, "quantity": "3"},
    )
    assert conflicting_cost.status_code == 409, conflicting_cost.text

    completion = client.post(
        f"/api/v1/work-orders/{order_id}/complete",
        headers=admin,
        json={
            "expected_version": order["lock_version"],
            "resolution_summary": "已更换导靴并试运行",
            "evidence_refs": ["attachment://synthetic-maintenance-photo"],
        },
    )
    assert completion.status_code == 200, completion.text
    order = completion.json()["data"]
    assert order["status"] == "WAITING_ACCEPTANCE"

    reworked = client.post(
        f"/api/v1/tenant-service/requests/{order_id}/acceptance",
        headers=_idempotent(tenant, f"acceptance-rework-{uuid4()}"),
        json={
            "expected_version": order["lock_version"],
            "decision": "REWORK",
            "comment": "仍有轻微异响，请复检",
        },
    )
    assert reworked.status_code == 200, reworked.text
    order = reworked.json()["data"]
    assert order["status"] == "IN_PROGRESS_AFTER_QUOTE"

    completion = client.post(
        f"/api/v1/work-orders/{order_id}/complete",
        headers=admin,
        json={
            "expected_version": order["lock_version"],
            "resolution_summary": "复检并重新校准",
            "no_evidence_reason": "复检参数记录于现场纸质设备卡",
        },
    )
    assert completion.status_code == 200, completion.text
    order = completion.json()["data"]

    acceptance_key = f"acceptance-pass-{uuid4()}"
    accepted = client.post(
        f"/api/v1/tenant-service/requests/{order_id}/acceptance",
        headers=_idempotent(tenant, acceptance_key),
        json={
            "expected_version": order["lock_version"],
            "decision": "ACCEPTED",
            "comment": "复检通过",
        },
    )
    assert accepted.status_code == 200, accepted.text
    order = accepted.json()["data"]
    assert order["status"] == "COMPLETED"
    assert len(order["acceptances"]) == 2
    acceptance_replay = client.post(
        f"/api/v1/tenant-service/requests/{order_id}/acceptance",
        headers=_idempotent(tenant, acceptance_key),
        json={
            "expected_version": order["lock_version"] - 1,
            "decision": "ACCEPTED",
            "comment": "复检通过",
        },
    )
    assert acceptance_replay.status_code == 200, acceptance_replay.text
    acceptance_key_conflict = client.post(
        f"/api/v1/tenant-service/requests/{order_id}/acceptance",
        headers=_idempotent(tenant, acceptance_key),
        json={
            "expected_version": order["lock_version"],
            "decision": "REWORK",
            "comment": "同一幂等键不得改变决定",
        },
    )
    assert acceptance_key_conflict.status_code == 409, acceptance_key_conflict.text
    assert acceptance_key_conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSED"

    rating_key = f"rating-{uuid4()}"
    rating_body = {"score": 5, "tags": ["及时", "专业"], "comment": "处理规范"}
    rating = client.post(
        f"/api/v1/tenant-service/requests/{order_id}/rating",
        headers=_idempotent(tenant, rating_key),
        json=rating_body,
    )
    assert rating.status_code == 200, rating.text
    rating_replay = client.post(
        f"/api/v1/tenant-service/requests/{order_id}/rating",
        headers=_idempotent(tenant, rating_key),
        json=rating_body,
    )
    assert rating_replay.status_code == 200, rating_replay.text
    changed_rating = client.post(
        f"/api/v1/tenant-service/requests/{order_id}/rating",
        headers=_idempotent(tenant, f"rating-change-{uuid4()}"),
        json={"score": 4},
    )
    assert changed_rating.status_code == 409, changed_rating.text

    todos = client.get(
        "/api/v1/work-items",
        headers=admin,
        params={"source_type": "WORK_ORDER", "source_id": str(order_id)},
    )
    assert todos.status_code == 200, todos.text
    assert all(item["status"] != "OPEN" for item in todos.json()["data"]["items"])


def test_auto_dispatch_sla_and_cross_party_isolation(client) -> None:
    admin = _headers()
    park = client.post(
        "/api/v1/parks", headers=admin, json={"name": "SLA 园", "address": "测试地址"}
    ).json()["data"]
    assignee = _create_assignee(client, admin, suffix=uuid4().hex[:8])
    party_a = _create_party(client, admin, park["id"], "承租企业 SLA-A")
    party_b = _create_party(client, admin, park["id"], "承租企业 SLA-B")
    suffix_a = uuid4().hex[:8]
    suffix_b = uuid4().hex[:8]
    user_a, tenant_a = _create_portal_user(client, admin, park_id=park["id"], suffix=suffix_a)
    user_b, tenant_b = _create_portal_user(client, admin, park_id=park["id"], suffix=suffix_b)
    for user, party in ((user_a, party_a), (user_b, party_b)):
        response = client.post(
            "/api/v1/tenant-service/principals",
            headers=admin,
            json={"user_id": user["id"], "party_id": party["id"], "park_ids": [park["id"]]},
        )
        assert response.status_code == 200, response.text

    rule = client.post(
        "/api/v1/work-order-assignment-rules",
        headers=admin,
        json={
            "code": "URGENT_MAINTENANCE",
            "name": "紧急维修自动派单",
            "park_id": park["id"],
            "category": "MAINTENANCE",
            "priority": "URGENT",
            "assignee_user_id": assignee["id"],
            "response_minutes": 5,
            "resolution_minutes": 30,
            "sort_order": 1,
        },
    )
    assert rule.status_code == 200, rule.text
    published = client.post(
        f"/api/v1/work-order-assignment-rules/{rule.json()['data']['id']}/publish",
        headers=admin,
    )
    assert published.status_code == 200, published.text

    auto_key = f"auto-{uuid4()}"
    created = client.post(
        "/api/v1/tenant-service/requests",
        headers=_idempotent(tenant_a, auto_key),
        json={
            "park_id": park["id"],
            "title": "消防泵告警",
            "category": "MAINTENANCE",
            "priority": "URGENT",
        },
    )
    assert created.status_code == 200, created.text
    order = created.json()["data"]
    assert order["status"] == "ASSIGNED"
    assert order["response_due_at"] is not None
    assert order["resolution_due_at"] is not None

    replay_by_other_party = client.post(
        "/api/v1/tenant-service/requests",
        headers=_idempotent(tenant_b, auto_key),
        json={
            "park_id": park["id"],
            "title": "消防泵告警",
            "category": "MAINTENANCE",
            "priority": "URGENT",
        },
    )
    assert replay_by_other_party.status_code == 409, replay_by_other_party.text
    assert replay_by_other_party.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert str(order["order_no"]) not in replay_by_other_party.text

    forged_dispatch = client.post(
        f"/api/v1/work-orders/{order['id']}/dispatch",
        headers=_headers(
            uid=user_a["id"],
            username=user_a["username"],
            permissions=["work_order:dispatch"],
            park_ids=[park["id"]],
            mode="LIST",
        ),
        json={
            "expected_version": order["lock_version"],
            "assignee_user_id": assignee["id"],
            "reason": "伪造令牌权限不应生效",
        },
    )
    assert forged_dispatch.status_code == 403, forged_dispatch.text

    unknown_field = client.post(
        "/api/v1/tenant-service/requests",
        headers=_idempotent(tenant_a, f"unknown-{uuid4()}"),
        json={"park_id": park["id"], "title": "未知字段", "unexpected": True},
    )
    assert unknown_field.status_code == 422, unknown_field.text

    duplicate_query = client.get(
        "/api/v1/work-orders?page=1&page=2",
        headers=admin,
    )
    assert duplicate_query.status_code == 400, duplicate_query.text

    denied = client.get(f"/api/v1/tenant-service/requests/{order['id']}", headers=tenant_b)
    assert denied.status_code == 404, denied.text

    swept = client.post(
        "/api/v1/work-orders/sla/sweep",
        headers=admin,
        json={"as_of": "2100-01-01T00:00:00Z"},
    )
    assert swept.status_code == 200, swept.text
    assert swept.json()["data"]["response_breaches_created"] == 1
    assert swept.json()["data"]["resolution_breaches_created"] == 1
    replay = client.post(
        "/api/v1/work-orders/sla/sweep",
        headers=admin,
        json={"as_of": "2100-01-01T00:00:00Z"},
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["response_breaches_created"] == 0
    assert replay.json()["data"]["resolution_breaches_created"] == 0

    retired = client.post(
        f"/api/v1/work-order-assignment-rules/{rule.json()['data']['id']}/retire",
        headers=admin,
        json={"reason": "派单策略调整，显式停止该版本"},
    )
    assert retired.status_code == 200, retired.text
    assert retired.json()["data"]["status"] == "RETIRED"
    assert retired.json()["data"]["retired_at"] is not None
    second_retire = client.post(
        f"/api/v1/work-order-assignment-rules/{rule.json()['data']['id']}/retire",
        headers=admin,
        json={"reason": "不得重复退役"},
    )
    assert second_retire.status_code == 409, second_retire.text
    assert second_retire.json()["code"] == "ASSIGNMENT_RULE_STATUS_INVALID"

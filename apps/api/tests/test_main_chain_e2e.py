"""端到端主链：登录 → 园区/单元 → 线索转化 → 合同激活 → 账单收款 → 工单/待办。

使用 TestClient + 内存 SQLite，不依赖外部服务。
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.infrastructure.database.models.identity import Tenant, User


def _bearer(*, permissions: list[str] | None = None) -> dict:
    token = create_access_token(
        subject="admin",
        claims={
            "uid": 1,
            "tenant_id": 1,
            "permissions": permissions or ["*"],
            "park_ids": [],
            "park_scope_mode": "ALL",
        },
    )
    return {"Authorization": f"Bearer {token}"}


def _idempotent(headers: dict[str, str], prefix: str) -> dict[str, str]:
    return {**headers, "Idempotency-Key": f"{prefix}-{uuid4()}"}


def test_main_chain_happy_path(client, governed_activate, approved_intent) -> None:
    h = _bearer()

    # 健康
    assert client.get("/health").json()["status"] == "up"

    # 园区 + 单元
    park = client.post(
        "/api/v1/parks", headers=h, json={"name": "E2E园", "address": "e2e-road"}
    ).json()["data"]
    unit = client.post(
        "/api/v1/units",
        headers=h,
        json={
            "park_id": park["id"],
            "name": "E-101",
            "code": "E101",
            "rentable_area": 200,
            "status": "VACANT",
        },
    ).json()["data"]

    # 招商线索 → 转化（主体 + 合同草稿）
    lead = client.post(
        "/api/v1/leads",
        headers=h,
        json={
            "park_id": park["id"],
            "name": "E2E客户",
            "contact_phone": "13600136000",
            "intent_level": "HIGH",
        },
    ).json()["data"]
    intent = approved_intent(lead_id=lead["id"], unit_ids=[unit["id"]])
    lock = client.post(
        f"/api/v1/leads/{lead['id']}/unit-locks",
        headers=h,
        json={
            "expected_version": lead["lock_version"],
            "unit_id": unit["id"],
            "intent_id": intent["id"],
        },
    )
    assert lock.status_code == 200, lock.text
    lead_version = lock.json()["data"]["lead_lock_version"]
    conv = client.post(
        f"/api/v1/leads/{lead['id']}/convert",
        headers=h,
        json={
            "expected_version": lead_version,
            "unit_ids": [unit["id"]],
            "start_date": "2026-06-01",
            "end_date": "2027-05-31",
            "occupied_area": "150",
            "unit_rent_price": "45",
            "deposit_amount": "9000",
        },
    )
    assert conv.status_code == 200, conv.text
    party_id = conv.json()["data"]["party"]["id"]
    lease_id = conv.json()["data"]["lease"]["id"]
    assert conv.json()["data"]["lead"]["status"] == "WON"

    # 合同费用、审批、主文档和激活均走 V2 治理链
    act = governed_activate(client, h, lease_id)
    assert act.status_code == 200, act.text
    assert act.json()["data"]["contract"]["status"] == "ACTIVE"
    lead_after_activation = client.get(f"/api/v1/leads/{lead['id']}", headers=h).json()["data"]
    assert lead_after_activation["unit_locks"][0]["status"] == "CONSUMED"
    assert lead_after_activation["unit_locks"][0]["consumed_at"] is not None

    # 到期待办已开
    todos = client.get(
        "/api/v1/work-items",
        headers=h,
        params={"item_type": "CONTRACT_EXPIRING", "status": "OPEN"},
    ).json()["data"]
    assert any(x["source_id"] == str(lease_id) for x in todos["items"])

    # 账单签发 → 收款待办 → 全额核销
    bill = client.post(
        "/api/v1/bills",
        headers=h,
        json={
            "park_id": park["id"],
            "party_id": party_id,
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "lines": [{"fee_code": "RENT", "quantity": "1", "unit_price": "300"}],
        },
    ).json()["data"]
    assert client.post(f"/api/v1/bills/{bill['id']}/issue", headers=h).status_code == 200

    unpaid = client.get(
        "/api/v1/work-items",
        headers=h,
        params={"item_type": "BILL_UNPAID", "status": "OPEN"},
    ).json()["data"]
    assert any(x["source_id"] == str(bill["id"]) for x in unpaid["items"])

    # 催缴必须基于尚有可收余额的账单；全额到账后应自动关闭案件。
    case = client.post(
        "/api/v1/collection/cases",
        headers=h,
        json={
            "park_id": park["id"],
            "party_id": party_id,
            "bill_id": bill["id"],
            "level": "L1",
        },
    )
    assert case.status_code == 200, case.text
    case_id = case.json()["data"]["id"]

    pay = client.post(
        "/api/v1/payments",
        headers=h,
        json={
            "park_id": park["id"],
            "party_id": party_id,
            "amount": "300",
            "method": "TRANSFER",
            "paid_at": "2026-06-15T12:00:00",
            "allocations": [{"bill_id": bill["id"], "amount": "300"}],
        },
    )
    assert pay.status_code == 200, pay.text

    bill_after = client.get(f"/api/v1/bills/{bill['id']}", headers=h).json()["data"]
    assert bill_after["status"] == "PAID"
    closed_case = client.get(f"/api/v1/collection/cases/{case_id}", headers=h)
    assert closed_case.status_code == 200, closed_case.text
    assert closed_case.json()["data"]["status"] == "CLOSED"
    assert closed_case.json()["data"]["resolution_code"] == "RECEIVABLE_SETTLED"

    operator = client.post(
        "/api/v1/system/users",
        headers=h,
        json={
            "username": f"main_chain_operator_{uuid4().hex[:8]}",
            "password": "Main-Chain-Operator-123!",
            "real_name": "主链维修人员",
            "role_ids": [],
            "park_ids": [],
            "all_parks": True,
        },
    )
    assert operator.status_code == 200, operator.text
    wo = client.post(
        "/api/v1/work-orders",
        headers=_idempotent(h, "main-chain-work-order"),
        json={"park_id": park["id"], "title": "E2E巡检", "priority": "MEDIUM"},
    )
    assert wo.status_code == 200, wo.text
    work_order = wo.json()["data"]
    wid = work_order["id"]
    dispatched = client.post(
        f"/api/v1/work-orders/{wid}/dispatch",
        headers=h,
        json={
            "expected_version": work_order["lock_version"],
            "assignee_user_id": operator.json()["data"]["id"],
            "reason": "主链测试人工派单",
        },
    )
    assert dispatched.status_code == 200, dispatched.text
    started = client.post(
        f"/api/v1/work-orders/{wid}/start",
        headers=h,
        json={"expected_version": dispatched.json()["data"]["lock_version"]},
    )
    assert started.status_code == 200, started.text
    completed = client.post(
        f"/api/v1/work-orders/{wid}/complete",
        headers=h,
        json={
            "expected_version": started.json()["data"]["lock_version"],
            "resolution_summary": "主链巡检处理完毕",
            "no_evidence_reason": "合成主链未生成附件",
        },
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["data"]["status"] == "WAITING_ACCEPTANCE"

    # 工作台聚合
    summary = client.get("/api/v1/workbench/summary", headers=h)
    assert summary.status_code == 200, summary.text
    metrics = summary.json()["data"]["metrics"]
    assert "open_todos" in metrics
    assert "unpaid_bills" in metrics

    # 系统配置
    org = client.post(
        "/api/v1/system/org-units",
        headers=h,
        json={"code": "E2E-ORG", "name": "E2E组织"},
    )
    assert org.status_code == 200, org.text


def test_main_chain_permission_denies(client) -> None:
    h = _bearer(permissions=["park:read"])
    r = client.get("/api/v1/parties", headers=h)
    assert r.status_code == 403
    r2 = client.get("/api/v1/work-items", headers=h)
    assert r2.status_code == 403


def test_cross_tenant_isolation_on_party(client, db_session: Session) -> None:
    h1 = _bearer()
    park = client.post("/api/v1/parks", headers=h1, json={"name": "T1园", "address": "a"}).json()[
        "data"
    ]
    party = client.post(
        "/api/v1/parties",
        headers=h1,
        json={"name": "仅租户1可见", "party_type": "ORGANIZATION"},
    ).json()["data"]

    # 使用真实存在且会话版本有效的其他租户用户，业务资源仍必须 404 隔离。
    other_tenant = Tenant(code="main-chain-other", name="其他租户", status="ACTIVE")
    db_session.add(other_tenant)
    db_session.flush()
    other_user = User(
        tenant_id=other_tenant.id,
        username="other",
        password_hash=hash_password("unused-secret"),
        real_name="其他租户用户",
        status="ACTIVE",
        token_version=0,
    )
    db_session.add(other_user)
    db_session.commit()
    h2 = {
        "Authorization": "Bearer "
        + create_access_token(
            subject="other",
            claims={
                "uid": other_user.id,
                "tenant_id": other_tenant.id,
                "permissions": ["*"],
                "park_ids": [],
                "park_scope_mode": "ALL",
            },
        )
    }
    r = client.get(f"/api/v1/parties/{party['id']}", headers=h2)
    assert r.status_code == 404

    # 园区 scope LIST 拒绝
    h3 = {
        "Authorization": "Bearer "
        + create_access_token(
            subject="scoped",
            claims={
                "uid": 1,
                "tenant_id": 1,
                "permissions": ["*"],
                "park_ids": [park["id"] + 9999],
                "park_scope_mode": "LIST",
            },
        )
    }
    r2 = client.post(
        "/api/v1/work-orders",
        headers=_idempotent(h3, "main-chain-scope-denied"),
        json={"park_id": park["id"], "title": "跨园拒绝"},
    )
    assert r2.status_code == 403
    assert r2.json()["code"] == "PARK_SCOPE_DENIED"

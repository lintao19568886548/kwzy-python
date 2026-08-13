"""端到端主链：登录 → 园区/单元 → 线索转化 → 合同激活 → 账单收款 → 工单/待办。

使用 TestClient + 内存 SQLite，不依赖外部服务。
"""

from __future__ import annotations

from app.core.security import create_access_token


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


def test_main_chain_happy_path(client) -> None:
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
    conv = client.post(
        f"/api/v1/leads/{lead['id']}/convert",
        headers=h,
        json={
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

    # 合同提交 + 激活
    assert client.post(f"/api/v1/leases/{lease_id}/submit", headers=h).status_code == 200
    act = client.post(f"/api/v1/leases/{lease_id}/activate", headers=h)
    assert act.status_code == 200, act.text
    assert act.json()["data"]["status"] == "ACTIVE"

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

    # 催缴案件（过程）+ 工单
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

    wo = client.post(
        "/api/v1/work-orders",
        headers=h,
        json={"park_id": park["id"], "title": "E2E巡检", "priority": "MEDIUM"},
    )
    assert wo.status_code == 200, wo.text
    wid = wo.json()["data"]["id"]
    assert client.post(f"/api/v1/work-orders/{wid}/complete", headers=h).status_code == 200

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


def test_cross_tenant_isolation_on_party(client) -> None:
    h1 = _bearer()
    park = client.post(
        "/api/v1/parks", headers=h1, json={"name": "T1园", "address": "a"}
    ).json()["data"]
    party = client.post(
        "/api/v1/parties",
        headers=h1,
        json={"name": "仅租户1可见", "party_type": "ORGANIZATION"},
    ).json()["data"]

    # 伪造其他租户 token（同库无该租户数据）
    h2 = {
        "Authorization": "Bearer "
        + create_access_token(
            subject="other",
            claims={
                "uid": 9,
                "tenant_id": 999,
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
        headers=h3,
        json={"park_id": park["id"], "title": "跨园拒绝"},
    )
    assert r2.status_code == 403
    assert r2.json()["code"] == "PARK_SCOPE_DENIED"

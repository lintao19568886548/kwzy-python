"""Investment leads API tests."""

from __future__ import annotations

from app.core.security import create_access_token


def _h(*, permissions: list[str] | None = None) -> dict:
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


def test_lead_create_list_follow_lose(client) -> None:
    h = _h()
    park = client.post(
        "/api/v1/parks", headers=h, json={"name": "招商园", "address": "t"}
    ).json()["data"]

    created = client.post(
        "/api/v1/leads",
        headers=h,
        json={
            "park_id": park["id"],
            "name": "意向客户甲",
            "contact_phone": "13800138000",
            "intent_level": "HIGH",
            "intent_area": "500",
            "agent_name": "中介小王",
        },
    )
    assert created.status_code == 200, created.text
    lead = created.json()["data"]
    assert lead["status"] == "NEW"
    assert lead["id"] > 0
    lid = lead["id"]

    listed = client.get("/api/v1/leads", headers=h, params={"status": "NEW"})
    assert listed.status_code == 200
    assert any(x["id"] == lid for x in listed.json()["data"]["items"])

    # 创建时应打开跟进待办
    todos = client.get(
        "/api/v1/work-items",
        headers=h,
        params={"item_type": "LEAD_FOLLOW", "status": "OPEN"},
    ).json()["data"]
    assert any(x["source_id"] == str(lid) for x in todos["items"])

    updated = client.patch(
        f"/api/v1/leads/{lid}",
        headers=h,
        json={"status": "FOLLOWING", "remark": "已约看房"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["status"] == "FOLLOWING"

    lost = client.post(
        f"/api/v1/leads/{lid}/lose",
        headers=h,
        json={"reason": "预算不够"},
    )
    assert lost.status_code == 200
    assert lost.json()["data"]["status"] == "LOST"
    assert lost.json()["data"]["lost_reason"] == "预算不够"


def test_lead_convert_to_party_and_lease(client) -> None:
    h = _h()
    park = client.post(
        "/api/v1/parks", headers=h, json={"name": "转化园", "address": "t"}
    ).json()["data"]
    unit = client.post(
        "/api/v1/units",
        headers=h,
        json={
            "park_id": park["id"],
            "name": "L-1",
            "code": "L1",
            "rentable_area": 120,
            "status": "VACANT",
        },
    ).json()["data"]
    lead = client.post(
        "/api/v1/leads",
        headers=h,
        json={
            "park_id": park["id"],
            "name": "转化客户",
            "contact_phone": "13900139000",
            "contact_name": "张三",
        },
    ).json()["data"]

    conv = client.post(
        f"/api/v1/leads/{lead['id']}/convert",
        headers=h,
        json={
            "unit_ids": [unit["id"]],
            "start_date": "2026-04-01",
            "end_date": "2027-03-31",
            "occupied_area": "100",
            "unit_rent_price": "40",
            "deposit_amount": "5000",
        },
    )
    assert conv.status_code == 200, conv.text
    body = conv.json()["data"]
    assert body["lead"]["status"] == "WON"
    assert body["party"]["id"] > 0
    assert body["party"]["name"] == "转化客户"
    assert body["lease"] is not None
    assert body["lease"]["status"] == "DRAFT"
    assert body["lead"]["party_id"] == body["party"]["id"]
    assert body["lead"]["lease_id"] == body["lease"]["id"]

    # 待办应完成
    todos = client.get(
        "/api/v1/work-items",
        headers=h,
        params={"item_type": "LEAD_FOLLOW"},
    ).json()["data"]
    match = [x for x in todos["items"] if x["source_id"] == str(lead["id"])]
    assert match
    assert match[0]["status"] == "DONE"


def test_lead_convert_party_only(client) -> None:
    h = _h()
    park = client.post(
        "/api/v1/parks", headers=h, json={"name": "仅主体园", "address": "t"}
    ).json()["data"]
    lead = client.post(
        "/api/v1/leads",
        headers=h,
        json={
            "park_id": park["id"],
            "name": "仅建主体",
            "contact_phone": "13700137000",
        },
    ).json()["data"]
    conv = client.post(f"/api/v1/leads/{lead['id']}/convert", headers=h, json={})
    assert conv.status_code == 200, conv.text
    assert conv.json()["data"]["lead"]["status"] == "WON"
    assert conv.json()["data"]["party"]["id"] > 0
    assert conv.json()["data"]["lease"] is None


def test_lead_permission_denied(client) -> None:
    h = _h(permissions=["park:read"])
    r = client.get("/api/v1/leads", headers=h)
    assert r.status_code == 403

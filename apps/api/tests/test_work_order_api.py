"""Work order API tests."""

from __future__ import annotations

from app.core.security import create_access_token


def _h() -> dict:
    token = create_access_token(
        subject="admin",
        claims={
            "uid": 1,
            "tenant_id": 1,
            "permissions": ["*"],
            "park_ids": [],
            "park_scope_mode": "ALL",
        },
    )
    return {"Authorization": f"Bearer {token}"}


def test_work_order_lifecycle_and_todo(client) -> None:
    h = _h()
    park = client.post(
        "/api/v1/parks", headers=h, json={"name": "工单园", "address": "t"}
    ).json()["data"]
    created = client.post(
        "/api/v1/work-orders",
        headers=h,
        json={
            "park_id": park["id"],
            "title": "电梯检修",
            "priority": "HIGH",
            "category": "MAINTENANCE",
        },
    )
    assert created.status_code == 200, created.text
    wid = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "OPEN"

    todos = client.get(
        "/api/v1/work-items",
        headers=h,
        params={"item_type": "WORK_ORDER_FOLLOW", "status": "OPEN"},
    ).json()["data"]
    assert any(x["source_id"] == str(wid) for x in todos["items"])

    started = client.post(f"/api/v1/work-orders/{wid}/start", headers=h)
    assert started.status_code == 200
    assert started.json()["data"]["status"] == "IN_PROGRESS"

    done = client.post(f"/api/v1/work-orders/{wid}/complete", headers=h)
    assert done.status_code == 200
    assert done.json()["data"]["status"] == "DONE"

    todos2 = client.get(
        "/api/v1/work-items", headers=h, params={"item_type": "WORK_ORDER_FOLLOW"}
    ).json()["data"]
    match = [x for x in todos2["items"] if x["source_id"] == str(wid)]
    assert match and match[0]["status"] == "DONE"

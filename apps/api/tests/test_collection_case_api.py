"""Collection case API tests."""

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


def test_collection_case_create_list(client) -> None:
    h = _h()
    park = client.post("/api/v1/parks", headers=h, json={"name": "催缴园", "address": "t"}).json()[
        "data"
    ]
    party = client.post(
        "/api/v1/parties",
        headers=h,
        json={"name": "欠费主体", "party_type": "ORGANIZATION"},
    ).json()["data"]
    bill = client.post(
        "/api/v1/bills",
        headers=h,
        json={
            "park_id": park["id"],
            "party_id": party["id"],
            "period_start": "2026-05-01",
            "period_end": "2026-05-31",
            "lines": [{"fee_code": "RENT", "quantity": "1", "unit_price": "800"}],
        },
    ).json()["data"]
    client.post(f"/api/v1/bills/{bill['id']}/issue", headers=h)

    case = client.post(
        "/api/v1/collection/cases",
        headers=h,
        json={
            "park_id": park["id"],
            "party_id": party["id"],
            "bill_id": bill["id"],
            "level": "L2",
        },
    )
    assert case.status_code == 200, case.text
    assert case.json()["data"]["status"] == "OPEN"
    cid = case.json()["data"]["id"]

    listed = client.get("/api/v1/collection/cases", headers=h)
    assert listed.status_code == 200
    assert any(x["id"] == cid for x in listed.json()["data"]["items"])

    patched = client.patch(
        f"/api/v1/collection/cases/{cid}",
        headers=h,
        json={
            "expected_version": case.json()["data"]["lock_version"],
            "status": "CLOSED",
            "remark": "已结清",
        },
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["status"] == "CLOSED"

    stale = client.patch(
        f"/api/v1/collection/cases/{cid}",
        headers=h,
        json={"expected_version": case.json()["data"]["lock_version"], "status": "OPEN"},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "COLLECTION_CASE_VERSION_CONFLICT"

"""Approval workflow minimal API tests."""

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


def test_approval_create_and_decide(client) -> None:
    h = _h()
    created = client.post(
        "/api/v1/approvals",
        headers=h,
        json={
            "biz_type": "LEASE",
            "biz_id": "99",
            "title": "合同折扣审批",
            "remark": "9折",
        },
    )
    assert created.status_code == 200, created.text
    aid = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "PENDING"

    listed = client.get("/api/v1/approvals", headers=h, params={"status": "PENDING"})
    assert listed.status_code == 200
    assert any(x["id"] == aid for x in listed.json()["data"]["items"])

    ok = client.post(f"/api/v1/approvals/{aid}/approve", headers=h, json={"remark": "同意"})
    assert ok.status_code == 200
    assert ok.json()["data"]["status"] == "APPROVED"

    again = client.post(
        "/api/v1/approvals",
        headers=h,
        json={"biz_type": "LEASE", "biz_id": "99", "title": "重复"},
    )
    assert again.status_code == 409
    assert again.json()["code"] == "APPROVAL_DUPLICATE"

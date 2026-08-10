"""Bill API tests."""

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


def test_bill_create_issue_void(client) -> None:
    h = _h()
    park = client.post("/api/v1/parks", headers=h, json={"name": "账单园", "address": "t"}).json()["data"]
    party = client.post(
        "/api/v1/parties", headers=h, json={"name": "账单主体", "party_type": "ORGANIZATION"}
    ).json()["data"]
    created = client.post(
        "/api/v1/bills",
        headers=h,
        json={
            "park_id": park["id"],
            "party_id": party["id"],
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "due_date": "2026-02-10",
            "lines": [
                {"fee_code": "RENT", "description": "房租", "quantity": "1", "unit_price": "1000"}
            ],
        },
    )
    assert created.status_code == 200, created.text
    bid = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "DRAFT"
    assert created.json()["data"]["total_amount"] == "1000.00"
    assert "OVERDUE" not in created.json()["data"]["status"]

    issued = client.post(f"/api/v1/bills/{bid}/issue", headers=h)
    assert issued.status_code == 200
    assert issued.json()["data"]["status"] == "ISSUED"
    assert issued.json()["data"]["is_overdue"] in (True, False)

    voided = client.post(f"/api/v1/bills/{bid}/void", headers=h)
    assert voided.status_code == 200
    assert voided.json()["data"]["status"] == "VOID"


def test_bill_reject_overdue_status_value(client) -> None:
    # status OVERDUE never accepted via domain
    from app.modules.billing.domain.rules import assert_bill_status
    import pytest

    with pytest.raises(ValueError):
        assert_bill_status("OVERDUE")

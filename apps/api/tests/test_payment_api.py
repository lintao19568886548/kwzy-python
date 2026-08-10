"""Payment allocation API tests."""

from __future__ import annotations

from decimal import Decimal

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


def test_payment_allocate_and_reverse(client) -> None:
    h = _h()
    park = client.post("/api/v1/parks", headers=h, json={"name": "收款园", "address": "t"}).json()["data"]
    party = client.post(
        "/api/v1/parties", headers=h, json={"name": "收款主体", "party_type": "ORGANIZATION"}
    ).json()["data"]
    bill = client.post(
        "/api/v1/bills",
        headers=h,
        json={
            "park_id": park["id"],
            "party_id": party["id"],
            "period_start": "2026-02-01",
            "period_end": "2026-02-28",
            "lines": [{"fee_code": "RENT", "quantity": "1", "unit_price": "500"}],
        },
    ).json()["data"]
    client.post(f"/api/v1/bills/{bill['id']}/issue", headers=h)

    pay = client.post(
        "/api/v1/payments",
        headers=h,
        json={
            "park_id": park["id"],
            "party_id": party["id"],
            "amount": "200",
            "method": "TRANSFER",
            "allocations": [{"bill_id": bill["id"], "amount": "200"}],
        },
    )
    assert pay.status_code == 200, pay.text
    pid = pay.json()["data"]["id"]
    assert pay.json()["data"]["status"] == "CONFIRMED"

    got = client.get(f"/api/v1/bills/{bill['id']}", headers=h).json()["data"]
    assert got["paid_amount"] == "200.00"
    assert got["status"] == "PARTIALLY_PAID"

    rev = client.post(f"/api/v1/payments/{pid}/reverse", headers=h)
    assert rev.status_code == 200
    assert rev.json()["data"]["status"] == "REVERSED"
    got2 = client.get(f"/api/v1/bills/{bill['id']}", headers=h).json()["data"]
    assert Decimal(str(got2["paid_amount"])) == Decimal("0")
    assert got2["status"] == "ISSUED"

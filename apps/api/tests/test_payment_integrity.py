"""Payment park match, idempotency, and paid_at contract tests (SQLite)."""

from __future__ import annotations

from decimal import Decimal

from app.core.security import create_access_token


def _token(*, park_ids: list[int] | None = None, mode: str = "ALL") -> dict:
    claims = {
        "uid": 1,
        "tenant_id": 1,
        "permissions": ["*"],
        "park_ids": park_ids or [],
        "park_scope_mode": mode,
    }
    token = create_access_token(subject="admin", claims=claims)
    return {"Authorization": f"Bearer {token}"}


def _seed_two_parks_same_party(client, h: dict) -> dict:
    park_a = client.post("/api/v1/parks", headers=h, json={"name": "园A-核销", "address": "a"}).json()[
        "data"
    ]
    park_b = client.post("/api/v1/parks", headers=h, json={"name": "园B-核销", "address": "b"}).json()[
        "data"
    ]
    party = client.post(
        "/api/v1/parties",
        headers=h,
        json={"name": "双园主体", "party_type": "ORGANIZATION"},
    ).json()["data"]
    bill_a = client.post(
        "/api/v1/bills",
        headers=h,
        json={
            "park_id": park_a["id"],
            "party_id": party["id"],
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "lines": [{"fee_code": "RENT", "quantity": "1", "unit_price": "1000"}],
        },
    ).json()["data"]
    client.post(f"/api/v1/bills/{bill_a['id']}/issue", headers=h)
    # Different period: duplicate-period check is party-scoped (not park-scoped).
    bill_b = client.post(
        "/api/v1/bills",
        headers=h,
        json={
            "park_id": park_b["id"],
            "party_id": party["id"],
            "period_start": "2026-04-01",
            "period_end": "2026-04-30",
            "lines": [{"fee_code": "RENT", "quantity": "1", "unit_price": "800"}],
        },
    ).json()["data"]
    client.post(f"/api/v1/bills/{bill_b['id']}/issue", headers=h)
    return {
        "park_a": park_a,
        "park_b": park_b,
        "party": party,
        "bill_a": bill_a,
        "bill_b": bill_b,
    }


def test_cross_park_allocation_rejected_with_all_scope(client) -> None:
    """User has ALL parks; still cannot allocate bill from park B to payment on park A."""
    h = _token(mode="ALL")
    seed = _seed_two_parks_same_party(client, h)

    # snapshot before failed payment
    bill_before = client.get(f"/api/v1/bills/{seed['bill_b']['id']}", headers=h).json()["data"]
    pays_before = client.get("/api/v1/payments", headers=h).json()["data"]["total"]

    bad = client.post(
        "/api/v1/payments",
        headers=h,
        json={
            "park_id": seed["park_a"]["id"],
            "party_id": seed["party"]["id"],
            "amount": "100",
            "method": "TRANSFER",
            "paid_at": "2026-03-10T12:00:00",
            "allocations": [{"bill_id": seed["bill_b"]["id"], "amount": "100"}],
        },
    )
    assert bad.status_code == 409, bad.text
    assert bad.json()["code"] == "PAYMENT_BILL_PARK_MISMATCH"
    assert "x-request-id" in {k.lower() for k in bad.headers.keys()}

    bill_after = client.get(f"/api/v1/bills/{seed['bill_b']['id']}", headers=h).json()["data"]
    assert bill_after["paid_amount"] == bill_before["paid_amount"]
    pays_after = client.get("/api/v1/payments", headers=h).json()["data"]["total"]
    assert pays_after == pays_before


def test_cross_park_allocation_rejected_with_list_scope(client) -> None:
    """LIST scope covering both parks still rejects cross-park allocation."""
    h_admin = _token(mode="ALL")
    seed = _seed_two_parks_same_party(client, h_admin)
    h = _token(
        park_ids=[seed["park_a"]["id"], seed["park_b"]["id"]],
        mode="LIST",
    )
    bad = client.post(
        "/api/v1/payments",
        headers=h,
        json={
            "park_id": seed["park_a"]["id"],
            "party_id": seed["party"]["id"],
            "amount": "50",
            "method": "CASH",
            "paid_at": "2026-03-11T09:00:00",
            "allocations": [{"bill_id": seed["bill_b"]["id"], "amount": "50"}],
        },
    )
    assert bad.status_code == 409
    assert bad.json()["code"] == "PAYMENT_BILL_PARK_MISMATCH"


def test_same_park_payment_succeeds(client) -> None:
    h = _token(mode="ALL")
    seed = _seed_two_parks_same_party(client, h)
    ok = client.post(
        "/api/v1/payments",
        headers=h,
        json={
            "park_id": seed["park_a"]["id"],
            "party_id": seed["party"]["id"],
            "amount": "300",
            "method": "TRANSFER",
            "paid_at": "2026-03-12T10:00:00",
            "allocations": [{"bill_id": seed["bill_a"]["id"], "amount": "300"}],
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["code"] == "OK"
    data = ok.json()["data"]
    assert data["status"] == "CONFIRMED"
    assert data["park_id"] == seed["park_a"]["id"]
    bill = client.get(f"/api/v1/bills/{seed['bill_a']['id']}", headers=h).json()["data"]
    assert Decimal(str(bill["paid_amount"])) == Decimal("300.00")


def test_paid_at_required(client) -> None:
    h = _token()
    park = client.post("/api/v1/parks", headers=h, json={"name": "必填园", "address": "t"}).json()[
        "data"
    ]
    party = client.post(
        "/api/v1/parties", headers=h, json={"name": "必填主体", "party_type": "ORGANIZATION"}
    ).json()["data"]
    r = client.post(
        "/api/v1/payments",
        headers=h,
        json={
            "park_id": park["id"],
            "party_id": party["id"],
            "amount": "10",
            "method": "TRANSFER",
            "allocations": [],
        },
    )
    assert r.status_code == 422
    assert r.json()["code"] == "VALIDATION_ERROR"


def test_idempotency_replay_same_body(client) -> None:
    h = _token()
    park = client.post("/api/v1/parks", headers=h, json={"name": "幂等园", "address": "t"}).json()[
        "data"
    ]
    party = client.post(
        "/api/v1/parties", headers=h, json={"name": "幂等主体", "party_type": "ORGANIZATION"}
    ).json()["data"]
    bill = client.post(
        "/api/v1/bills",
        headers=h,
        json={
            "park_id": park["id"],
            "party_id": party["id"],
            "period_start": "2026-04-01",
            "period_end": "2026-04-30",
            "lines": [{"fee_code": "RENT", "quantity": "1", "unit_price": "500"}],
        },
    ).json()["data"]
    client.post(f"/api/v1/bills/{bill['id']}/issue", headers=h)

    body = {
        "park_id": park["id"],
        "party_id": party["id"],
        "amount": "200",
        "method": "TRANSFER",
        "paid_at": "2026-04-05T10:00:00",
        "allocations": [{"bill_id": bill["id"], "amount": "200"}],
    }
    headers = {**h, "Idempotency-Key": "pay-idem-001"}
    r1 = client.post("/api/v1/payments", headers=headers, json=body)
    assert r1.status_code == 200, r1.text
    pid = r1.json()["data"]["id"]
    r2 = client.post("/api/v1/payments", headers=headers, json=body)
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["id"] == pid
    # only one payment and paid once
    total = client.get("/api/v1/payments", headers=h).json()["data"]["total"]
    assert total == 1
    got = client.get(f"/api/v1/bills/{bill['id']}", headers=h).json()["data"]
    assert Decimal(str(got["paid_amount"])) == Decimal("200.00")


def test_idempotency_key_conflict_different_body(client) -> None:
    h = _token()
    park = client.post("/api/v1/parks", headers=h, json={"name": "冲突园", "address": "t"}).json()[
        "data"
    ]
    party = client.post(
        "/api/v1/parties", headers=h, json={"name": "冲突主体", "party_type": "ORGANIZATION"}
    ).json()["data"]
    bill = client.post(
        "/api/v1/bills",
        headers=h,
        json={
            "park_id": park["id"],
            "party_id": party["id"],
            "period_start": "2026-05-01",
            "period_end": "2026-05-31",
            "lines": [{"fee_code": "RENT", "quantity": "1", "unit_price": "500"}],
        },
    ).json()["data"]
    client.post(f"/api/v1/bills/{bill['id']}/issue", headers=h)
    headers = {**h, "Idempotency-Key": "pay-idem-conflict"}
    body1 = {
        "park_id": park["id"],
        "party_id": party["id"],
        "amount": "100",
        "method": "TRANSFER",
        "paid_at": "2026-05-05T10:00:00",
        "allocations": [{"bill_id": bill["id"], "amount": "100"}],
    }
    body2 = {**body1, "amount": "150", "allocations": [{"bill_id": bill["id"], "amount": "150"}]}
    assert client.post("/api/v1/payments", headers=headers, json=body1).status_code == 200
    r2 = client.post("/api/v1/payments", headers=headers, json=body2)
    assert r2.status_code == 409
    assert r2.json()["code"] == "IDEMPOTENCY_KEY_CONFLICT"


def test_payment_list_park_id_filter(client) -> None:
    h = _token()
    seed = _seed_two_parks_same_party(client, h)
    client.post(
        "/api/v1/payments",
        headers=h,
        json={
            "park_id": seed["park_a"]["id"],
            "party_id": seed["party"]["id"],
            "amount": "10",
            "method": "TRANSFER",
            "paid_at": "2026-03-20T10:00:00",
            "allocations": [{"bill_id": seed["bill_a"]["id"], "amount": "10"}],
        },
    )
    client.post(
        "/api/v1/payments",
        headers=h,
        json={
            "park_id": seed["park_b"]["id"],
            "party_id": seed["party"]["id"],
            "amount": "20",
            "method": "TRANSFER",
            "paid_at": "2026-03-20T11:00:00",
            "allocations": [{"bill_id": seed["bill_b"]["id"], "amount": "20"}],
        },
    )
    only_a = client.get(
        f"/api/v1/payments?park_id={seed['park_a']['id']}", headers=h
    ).json()["data"]
    assert only_a["total"] == 1
    assert only_a["items"][0]["park_id"] == seed["park_a"]["id"]


def test_bill_issue_idempotency(client) -> None:
    h = _token()
    park = client.post("/api/v1/parks", headers=h, json={"name": "签发园", "address": "t"}).json()[
        "data"
    ]
    party = client.post(
        "/api/v1/parties", headers=h, json={"name": "签发主体", "party_type": "ORGANIZATION"}
    ).json()["data"]
    bill = client.post(
        "/api/v1/bills",
        headers=h,
        json={
            "park_id": park["id"],
            "party_id": party["id"],
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "lines": [{"fee_code": "RENT", "quantity": "1", "unit_price": "100"}],
        },
    ).json()["data"]
    headers = {**h, "Idempotency-Key": "bill-issue-1"}
    r1 = client.post(f"/api/v1/bills/{bill['id']}/issue", headers=headers)
    assert r1.status_code == 200
    assert r1.json()["data"]["status"] == "ISSUED"
    r2 = client.post(f"/api/v1/bills/{bill['id']}/issue", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["data"]["id"] == bill["id"]
    assert r2.json()["data"]["status"] == "ISSUED"


def test_idempotency_remark_change_conflicts(client) -> None:
    """Same key with only remark changed → 409 (full body hash)."""
    h = _token()
    park = client.post("/api/v1/parks", headers=h, json={"name": "备注园", "address": "t"}).json()[
        "data"
    ]
    party = client.post(
        "/api/v1/parties", headers=h, json={"name": "备注主体", "party_type": "ORGANIZATION"}
    ).json()["data"]
    bill = client.post(
        "/api/v1/bills",
        headers=h,
        json={
            "park_id": park["id"],
            "party_id": party["id"],
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "lines": [{"fee_code": "RENT", "quantity": "1", "unit_price": "100"}],
        },
    ).json()["data"]
    client.post(f"/api/v1/bills/{bill['id']}/issue", headers=h)
    key_headers = {**h, "Idempotency-Key": "pay-remark-hash"}
    body1 = {
        "park_id": park["id"],
        "party_id": party["id"],
        "amount": "50",
        "method": "TRANSFER",
        "paid_at": "2026-07-05T10:00:00",
        "remark": "first",
        "allocations": [{"bill_id": bill["id"], "amount": "50"}],
    }
    assert client.post("/api/v1/payments", headers=key_headers, json=body1).status_code == 200
    body2 = {**body1, "remark": "second"}
    r2 = client.post("/api/v1/payments", headers=key_headers, json=body2)
    assert r2.status_code == 409, r2.text
    assert r2.json()["code"] == "IDEMPOTENCY_KEY_CONFLICT"


def test_idempotency_key_length_and_empty(client) -> None:
    h = _token()
    park = client.post("/api/v1/parks", headers=h, json={"name": "键长园", "address": "t"}).json()[
        "data"
    ]
    party = client.post(
        "/api/v1/parties", headers=h, json={"name": "键长主体", "party_type": "ORGANIZATION"}
    ).json()["data"]
    body = {
        "park_id": park["id"],
        "party_id": party["id"],
        "amount": "1",
        "method": "TRANSFER",
        "paid_at": "2026-07-06T10:00:00",
        "allocations": [],
    }
    empty = client.post("/api/v1/payments", headers={**h, "Idempotency-Key": "   "}, json=body)
    assert empty.status_code == 422, empty.text
    assert empty.json()["code"] == "VALIDATION_ERROR"
    too_long = client.post(
        "/api/v1/payments",
        headers={**h, "Idempotency-Key": "k" * 129},
        json=body,
    )
    assert too_long.status_code == 422, too_long.text
    assert too_long.json()["code"] == "VALIDATION_ERROR"
    ok = client.post(
        "/api/v1/payments",
        headers={**h, "Idempotency-Key": "k" * 128},
        json=body,
    )
    assert ok.status_code == 200, ok.text


def test_payment_idempotency_cache_not_bypass_park_scope(client) -> None:
    """User B (park B only) cannot replay user A's payment idempotency cache."""
    h_admin = _token(mode="ALL")
    seed = _seed_two_parks_same_party(client, h_admin)
    h_a = _token(park_ids=[seed["park_a"]["id"]], mode="LIST")
    h_b = _token(park_ids=[seed["park_b"]["id"]], mode="LIST")

    body = {
        "park_id": seed["park_a"]["id"],
        "party_id": seed["party"]["id"],
        "amount": "30",
        "method": "TRANSFER",
        "paid_at": "2026-03-15T10:00:00",
        "remark": "scope-a",
        "allocations": [{"bill_id": seed["bill_a"]["id"], "amount": "30"}],
    }
    key = "cross-user-pay-cache"
    r1 = client.post("/api/v1/payments", headers={**h_a, "Idempotency-Key": key}, json=body)
    assert r1.status_code == 200, r1.text
    pid = r1.json()["data"]["id"]

    r2 = client.post("/api/v1/payments", headers={**h_b, "Idempotency-Key": key}, json=body)
    assert r2.status_code in {403, 404}, r2.text
    assert r2.json()["code"] in {"PARK_SCOPE_DENIED", "BILL_NOT_FOUND", "PAYMENT_NOT_FOUND"}
    # must not leak cached payload
    data = r2.json().get("data")
    assert data is None or data.get("id") != pid


def test_payment_idempotency_replay_after_reverse_returns_first_response(client) -> None:
    """Create → reverse → replay key returns first CONFIRMED snapshot, no new side effects."""
    h = _token()
    park = client.post("/api/v1/parks", headers=h, json={"name": "冲正重放园", "address": "t"}).json()[
        "data"
    ]
    party = client.post(
        "/api/v1/parties", headers=h, json={"name": "冲正重放主体", "party_type": "ORGANIZATION"}
    ).json()["data"]
    bill = client.post(
        "/api/v1/bills",
        headers=h,
        json={
            "park_id": park["id"],
            "party_id": party["id"],
            "period_start": "2026-11-01",
            "period_end": "2026-11-30",
            "lines": [{"fee_code": "RENT", "quantity": "1", "unit_price": "400"}],
        },
    ).json()["data"]
    client.post(f"/api/v1/bills/{bill['id']}/issue", headers=h)
    body = {
        "park_id": park["id"],
        "party_id": party["id"],
        "amount": "120",
        "method": "TRANSFER",
        "paid_at": "2026-11-05T10:00:00",
        "remark": "first-pay",
        "allocations": [{"bill_id": bill["id"], "amount": "120"}],
    }
    key_h = {**h, "Idempotency-Key": "pay-after-reverse"}
    r1 = client.post("/api/v1/payments", headers=key_h, json=body)
    assert r1.status_code == 200, r1.text
    first = r1.json()["data"]
    assert first["status"] == "CONFIRMED"
    pid = first["id"]
    paid_after_create = client.get(f"/api/v1/bills/{bill['id']}", headers=h).json()["data"][
        "paid_amount"
    ]
    assert Decimal(str(paid_after_create)) == Decimal("120.00")

    rev = client.post(f"/api/v1/payments/{pid}/reverse", headers=h)
    assert rev.status_code == 200
    assert rev.json()["data"]["status"] == "REVERSED"
    assert Decimal(
        str(client.get(f"/api/v1/bills/{bill['id']}", headers=h).json()["data"]["paid_amount"])
    ) == Decimal("0")

    pays_before = client.get("/api/v1/payments", headers=h).json()["data"]["total"]
    r2 = client.post("/api/v1/payments", headers=key_h, json=body)
    assert r2.status_code == 200, r2.text
    replay = r2.json()["data"]
    # First-response snapshot, not current REVERSED state.
    assert replay["status"] == "CONFIRMED"
    assert replay["id"] == pid
    assert replay.get("remark") == "first-pay"
    pays_after = client.get("/api/v1/payments", headers=h).json()["data"]["total"]
    assert pays_after == pays_before == 1
    # No new allocation / amount change from replay
    assert Decimal(
        str(client.get(f"/api/v1/bills/{bill['id']}", headers=h).json()["data"]["paid_amount"])
    ) == Decimal("0")
    current = client.get(f"/api/v1/payments/{pid}", headers=h).json()["data"]
    assert current["status"] == "REVERSED"


def test_bill_issue_idempotency_replay_after_void_returns_first_response(client) -> None:
    """Issue → void → replay key returns first ISSUED snapshot, no re-issue."""
    h = _token()
    park = client.post("/api/v1/parks", headers=h, json={"name": "作废重发园", "address": "t"}).json()[
        "data"
    ]
    party = client.post(
        "/api/v1/parties", headers=h, json={"name": "作废重发主体", "party_type": "ORGANIZATION"}
    ).json()["data"]
    bill = client.post(
        "/api/v1/bills",
        headers=h,
        json={
            "park_id": park["id"],
            "party_id": party["id"],
            "period_start": "2026-12-01",
            "period_end": "2026-12-31",
            "lines": [{"fee_code": "RENT", "quantity": "1", "unit_price": "10"}],
        },
    ).json()["data"]
    key_h = {**h, "Idempotency-Key": "bill-issue-after-void"}
    r1 = client.post(f"/api/v1/bills/{bill['id']}/issue", headers=key_h)
    assert r1.status_code == 200
    assert r1.json()["data"]["status"] == "ISSUED"
    void = client.post(f"/api/v1/bills/{bill['id']}/void", headers=h)
    assert void.status_code == 200
    assert void.json()["data"]["status"] == "VOID"

    r2 = client.post(f"/api/v1/bills/{bill['id']}/issue", headers=key_h)
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["status"] == "ISSUED"
    assert r2.json()["data"]["id"] == bill["id"]
    # Live resource remains VOID
    live = client.get(f"/api/v1/bills/{bill['id']}", headers=h).json()["data"]
    assert live["status"] == "VOID"


def test_bill_issue_idempotency_cache_not_bypass_park_scope(client) -> None:
    """User B without park scope cannot replay bill issue cache."""
    h_admin = _token(mode="ALL")
    seed = _seed_two_parks_same_party(client, h_admin)
    # create a DRAFT on park A for issue test (seed bills already issued — make another)
    draft = client.post(
        "/api/v1/bills",
        headers=h_admin,
        json={
            "park_id": seed["park_a"]["id"],
            "party_id": seed["party"]["id"],
            "period_start": "2026-10-01",
            "period_end": "2026-10-31",
            "lines": [{"fee_code": "RENT", "quantity": "1", "unit_price": "10"}],
        },
    ).json()["data"]
    h_a = _token(park_ids=[seed["park_a"]["id"]], mode="LIST")
    h_b = _token(park_ids=[seed["park_b"]["id"]], mode="LIST")
    key = "cross-user-bill-issue"
    r1 = client.post(
        f"/api/v1/bills/{draft['id']}/issue",
        headers={**h_a, "Idempotency-Key": key},
    )
    assert r1.status_code == 200, r1.text
    r2 = client.post(
        f"/api/v1/bills/{draft['id']}/issue",
        headers={**h_b, "Idempotency-Key": key},
    )
    assert r2.status_code in {403, 404}, r2.text
    assert r2.json()["code"] in {"BILL_NOT_FOUND", "PARK_SCOPE_DENIED", "PERMISSION_DENIED"}
    assert r2.json().get("data") is None or r2.json()["data"].get("id") != draft["id"]

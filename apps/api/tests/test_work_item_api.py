"""Workbench work-items API tests."""

from __future__ import annotations

from app.core.security import create_access_token


def _h(*, permissions: list[str] | None = None, park_scope_mode: str = "ALL", park_ids: list | None = None) -> dict:
    token = create_access_token(
        subject="admin",
        claims={
            "uid": 1,
            "tenant_id": 1,
            "permissions": permissions or ["*"],
            "park_ids": park_ids or [],
            "park_scope_mode": park_scope_mode,
        },
    )
    return {"Authorization": f"Bearer {token}"}


def test_work_item_create_list_complete_reopen(client) -> None:
    h = _h()
    park = client.post(
        "/api/v1/parks", headers=h, json={"name": "待办园", "address": "t"}
    ).json()["data"]

    created = client.post(
        "/api/v1/work-items",
        headers=h,
        json={
            "title": "跟进合同续签",
            "description": "客户本月到期",
            "park_id": park["id"],
            "priority": "HIGH",
            "item_type": "CONTRACT_FOLLOW",
            "due_at": "2026-08-20T10:00:00",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["code"] == "OK"
    item = body["data"]
    assert item["status"] == "OPEN"
    assert item["priority"] == "HIGH"
    assert item["source_type"] == "MANUAL"
    assert item["source_id"].startswith("m-")
    wid = item["id"]

    listed = client.get("/api/v1/work-items", headers=h, params={"status": "OPEN"})
    assert listed.status_code == 200
    data = listed.json()["data"]
    assert data["total"] >= 1
    assert any(x["id"] == wid for x in data["items"])

    got = client.get(f"/api/v1/work-items/{wid}", headers=h)
    assert got.status_code == 200
    assert got.json()["data"]["title"] == "跟进合同续签"

    done = client.post(f"/api/v1/work-items/{wid}/complete", headers=h)
    assert done.status_code == 200, done.text
    assert done.json()["data"]["status"] == "DONE"
    assert done.json()["data"]["completed_at"] is not None
    assert done.json()["data"]["completed_by"] == 1

    # idempotent complete
    again = client.post(f"/api/v1/work-items/{wid}/complete", headers=h)
    assert again.status_code == 200
    assert again.json()["data"]["status"] == "DONE"

    reopened = client.post(f"/api/v1/work-items/{wid}/reopen", headers=h)
    assert reopened.status_code == 200
    assert reopened.json()["data"]["status"] == "OPEN"
    assert reopened.json()["data"]["completed_at"] is None

    cancelled = client.post(f"/api/v1/work-items/{wid}/cancel", headers=h)
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "CANCELLED"

    # cannot complete cancelled
    bad = client.post(f"/api/v1/work-items/{wid}/complete", headers=h)
    assert bad.status_code == 400
    assert bad.json()["code"] == "WORK_ITEM_STATUS_INVALID"


def test_work_item_permission_denied(client) -> None:
    h = _h(permissions=["park:read"])
    r = client.get("/api/v1/work-items", headers=h)
    assert r.status_code == 403
    assert r.json()["code"] == "PERMISSION_DENIED"

    r2 = client.post(
        "/api/v1/work-items",
        headers=h,
        json={"title": "无权限创建"},
    )
    assert r2.status_code == 403


def test_work_item_park_scope_denied_on_create(client) -> None:
    h_all = _h()
    park = client.post(
        "/api/v1/parks", headers=h_all, json={"name": "外园", "address": "x"}
    ).json()["data"]

    h_scoped = _h(
        permissions=["work_item:read", "work_item:write"],
        park_scope_mode="LIST",
        park_ids=[99999],
    )
    r = client.post(
        "/api/v1/work-items",
        headers=h_scoped,
        json={"title": "跨园", "park_id": park["id"]},
    )
    assert r.status_code == 403
    assert r.json()["code"] == "PARK_SCOPE_DENIED"


def test_work_item_ensure_from_source_idempotent(client, db_session) -> None:
    """来源幂等 upsert（应用服务内部 API，供事件调用）。"""

    from app.modules.workbench.application.work_item_service import WorkItemService
    from app.shared.tenant_context import ParkScopeMode, TenantContext

    ctx = TenantContext(
        tenant_id=1,
        user_id=1,
        username="admin",
        permissions=["*"],
        park_scope_mode=ParkScopeMode.ALL,
    )
    svc = WorkItemService(db_session, ctx)
    first = svc.ensure_from_source(
        source_type="BILL",
        source_id="42",
        item_type="BILL_UNPAID",
        title="账单未结清",
        priority="URGENT",
    )
    assert first["status"] == "OPEN"
    assert first["source_type"] == "BILL"
    second = svc.ensure_from_source(
        source_type="BILL",
        source_id="42",
        item_type="BILL_UNPAID",
        title="账单未结清（更新）",
        priority="HIGH",
    )
    assert second["id"] == first["id"]
    assert second["title"] == "账单未结清（更新）"
    assert second["priority"] == "HIGH"

    # complete then ensure reopens
    svc.complete_work_item(int(first["id"]))
    third = svc.ensure_from_source(
        source_type="BILL",
        source_id="42",
        item_type="BILL_UNPAID",
        title="账单未结清",
    )
    assert third["id"] == first["id"]
    assert third["status"] == "OPEN"


def test_work_item_not_found(client) -> None:
    h = _h()
    r = client.get("/api/v1/work-items/999999", headers=h)
    assert r.status_code == 404
    assert r.json()["code"] == "WORK_ITEM_NOT_FOUND"


def test_lease_activate_opens_and_terminate_closes_expiring_todo(client) -> None:
    """合同激活打开到期待办；终止取消待办。"""

    h = _h()
    park = client.post(
        "/api/v1/parks", headers=h, json={"name": "合同待办园", "address": "t"}
    ).json()["data"]
    unit = client.post(
        "/api/v1/units",
        headers=h,
        json={
            "park_id": park["id"],
            "name": "T-1",
            "code": "T1",
            "rentable_area": 50,
            "status": "VACANT",
        },
    ).json()["data"]
    party = client.post(
        "/api/v1/parties",
        headers=h,
        json={"name": "到期主体", "party_type": "ORGANIZATION"},
    ).json()["data"]
    lease = client.post(
        "/api/v1/leases",
        headers=h,
        json={
            "park_id": park["id"],
            "party_id": party["id"],
            "start_date": "2026-01-01",
            "end_date": "2026-09-30",
            "deposit_amount": "1000",
            "units": [
                {"unit_id": unit["id"], "occupied_area": "40", "unit_rent_price": "30"}
            ],
        },
    )
    assert lease.status_code == 200, lease.text
    cid = lease.json()["data"]["id"]
    assert client.post(f"/api/v1/leases/{cid}/submit", headers=h).status_code == 200
    act = client.post(f"/api/v1/leases/{cid}/activate", headers=h)
    assert act.status_code == 200, act.text

    todos = client.get(
        "/api/v1/work-items",
        headers=h,
        params={"item_type": "CONTRACT_EXPIRING", "status": "OPEN"},
    ).json()["data"]
    match = [x for x in todos["items"] if x["source_id"] == str(cid)]
    assert len(match) == 1
    assert match[0]["source_type"] == "LEASE"

    summary = client.get("/api/v1/workbench/summary", headers=h)
    assert summary.status_code == 200, summary.text
    metrics = summary.json()["data"]["metrics"]
    assert metrics["open_todos"] >= 1
    assert "expiring_contracts" in metrics

    term = client.post(f"/api/v1/leases/{cid}/terminate", headers=h)
    assert term.status_code == 200, term.text
    after = client.get(
        "/api/v1/work-items",
        headers=h,
        params={"item_type": "CONTRACT_EXPIRING"},
    ).json()["data"]
    match2 = [x for x in after["items"] if x["source_id"] == str(cid)]
    assert len(match2) == 1
    assert match2[0]["status"] == "CANCELLED"


def test_bill_issue_opens_and_payment_closes_collect_todo(client) -> None:
    """账单签发自动开待办；全额核销自动完成；冲正重新打开。"""

    h = _h()
    park = client.post(
        "/api/v1/parks", headers=h, json={"name": "待办联动园", "address": "t"}
    ).json()["data"]
    party = client.post(
        "/api/v1/parties",
        headers=h,
        json={"name": "待办主体", "party_type": "ORGANIZATION"},
    ).json()["data"]
    bill = client.post(
        "/api/v1/bills",
        headers=h,
        json={
            "park_id": park["id"],
            "party_id": party["id"],
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "lines": [{"fee_code": "RENT", "quantity": "1", "unit_price": "100"}],
        },
    ).json()["data"]

    issued = client.post(f"/api/v1/bills/{bill['id']}/issue", headers=h)
    assert issued.status_code == 200, issued.text

    todos = client.get(
        "/api/v1/work-items",
        headers=h,
        params={"item_type": "BILL_UNPAID", "status": "OPEN"},
    ).json()["data"]
    match = [x for x in todos["items"] if x["source_type"] == "BILL" and x["source_id"] == str(bill["id"])]
    assert len(match) == 1
    assert match[0]["status"] == "OPEN"
    assert "待收款" in match[0]["title"]

    pay = client.post(
        "/api/v1/payments",
        headers=h,
        json={
            "park_id": park["id"],
            "party_id": party["id"],
            "amount": "100",
            "method": "TRANSFER",
            "paid_at": "2026-03-15T10:00:00",
            "allocations": [{"bill_id": bill["id"], "amount": "100"}],
        },
    )
    assert pay.status_code == 200, pay.text
    pid = pay.json()["data"]["id"]

    done_list = client.get(
        "/api/v1/work-items",
        headers=h,
        params={"item_type": "BILL_UNPAID"},
    ).json()["data"]
    match2 = [x for x in done_list["items"] if x["source_id"] == str(bill["id"])]
    assert len(match2) == 1
    assert match2[0]["status"] == "DONE"

    rev = client.post(f"/api/v1/payments/{pid}/reverse", headers=h)
    assert rev.status_code == 200, rev.text
    reopen = client.get(
        "/api/v1/work-items",
        headers=h,
        params={"item_type": "BILL_UNPAID", "status": "OPEN"},
    ).json()["data"]
    match3 = [x for x in reopen["items"] if x["source_id"] == str(bill["id"])]
    assert len(match3) == 1
    assert match3[0]["status"] == "OPEN"

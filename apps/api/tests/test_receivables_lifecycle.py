"""Independent receivables lifecycle regressions on an isolated relational database."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.infrastructure.database.models.billing import Bill, BillLine
from app.infrastructure.database.models.collection import Payment, PaymentAllocation
from app.infrastructure.database.models.collection_case import CollectionCase
from app.infrastructure.database.models.identity import Tenant
from app.infrastructure.database.models.lease import LeaseContract, LeasePerformanceSchedule
from app.infrastructure.database.models.park_property import Park
from app.infrastructure.database.models.receivables import CollectionRecord, ReceiptTransaction


def _headers(
    permissions: list[str] | None = None,
    *,
    park_scope_mode: str = "ALL",
    park_ids: list[int] | None = None,
) -> dict[str, str]:
    token = create_access_token(
        subject="receivables-auditor",
        claims={
            "uid": 1,
            "tenant_id": 1,
            "permissions": permissions or ["*"],
            "park_ids": park_ids or [],
            "park_scope_mode": park_scope_mode,
        },
    )
    return {"Authorization": f"Bearer {token}"}


def _seed_party_park(client, *, suffix: str = "A") -> tuple[dict, dict]:
    headers = _headers()
    park = client.post(
        "/api/v1/parks",
        headers=headers,
        json={"name": f"应收园区{suffix}", "address": "独立验收"},
    ).json()["data"]
    party = client.post(
        "/api/v1/parties",
        headers=headers,
        json={"name": f"应收企业{suffix}", "party_type": "ORGANIZATION"},
    ).json()["data"]
    return park, party


def _bill(
    client,
    *,
    park_id: int,
    party_id: int,
    amount: str,
    due_date: str = "2026-01-01",
    period_start: str = "2026-01-01",
    period_end: str = "2026-01-31",
) -> dict:
    headers = _headers()
    response = client.post(
        "/api/v1/bills",
        headers=headers,
        json={
            "park_id": park_id,
            "party_id": party_id,
            "period_start": period_start,
            "period_end": period_end,
            "due_date": due_date,
            "lines": [{"fee_code": "RENT", "quantity": "1", "unit_price": amount}],
        },
    )
    assert response.status_code == 200, response.text
    bill = response.json()["data"]
    issued = client.post(f"/api/v1/bills/{bill['id']}/issue", headers=headers)
    assert issued.status_code == 200, issued.text
    return issued.json()["data"]


def _receipt_payload(*, park_id: int, party_id: int, source_ref: str, amount: str) -> dict:
    return {
        "park_id": park_id,
        "party_id": party_id,
        "amount": amount,
        "currency": "CNY",
        "received_at": "2026-03-05T10:20:30",
        "channel": "BANK_IMPORT",
        "source_provider": "SYNTHETIC_BANK_FILE",
        "source_ref": source_ref,
        "payer_name": "应收企业A",
        "payer_account": "6222021234567890",
    }


def test_schedule_billing_is_current_version_deterministic_and_idempotent(
    client, db_session: Session
) -> None:
    headers = _headers()
    park, party = _seed_party_park(client, suffix="计划")
    contract = LeaseContract(
        tenant_id=1,
        park_id=park["id"],
        party_id=party["id"],
        contract_no="LEASE-SCHEDULE-001",
        status="ACTIVE",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        current_version_no=2,
        lock_version=1,
        deposit_amount=Decimal(0),
        created_by=1,
    )
    db_session.add(contract)
    db_session.flush()
    current = LeasePerformanceSchedule(
        tenant_id=1,
        contract_id=contract.id,
        contract_version_no=2,
        charge_code="RENT",
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        due_date=date(2026, 3, 5),
        currency="CNY",
        area=Decimal(100),
        unit_price=Decimal(10),
        net_amount=Decimal(1000),
        tax_amount=Decimal(60),
        gross_amount=Decimal(1060),
        deterministic_key="contract-1-v2-202603-rent",
        status="PLANNED",
    )
    obsolete = LeasePerformanceSchedule(
        tenant_id=1,
        contract_id=contract.id,
        contract_version_no=1,
        charge_code="RENT",
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        due_date=date(2026, 3, 5),
        currency="CNY",
        area=Decimal(100),
        unit_price=Decimal(9),
        net_amount=Decimal(900),
        tax_amount=Decimal(54),
        gross_amount=Decimal(954),
        deterministic_key="contract-1-v1-202603-rent",
        status="SUPERSEDED",
    )
    db_session.add_all([current, obsolete])
    db_session.commit()

    schedule_selects: list[str] = []

    def capture_schedule_selects(_conn, _cursor, statement, _parameters, _context, _many):
        normalized = statement.lower()
        if normalized.lstrip().startswith("select") and "lease_performance_schedules" in normalized:
            schedule_selects.append(normalized)

    event.listen(db_session.get_bind(), "before_cursor_execute", capture_schedule_selects)
    try:
        preview = client.get(
            "/api/v1/billing/runs/preview",
            headers=headers,
            params={"as_of": "2026-03-31", "park_id": park["id"]},
        )
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", capture_schedule_selects)
    assert preview.status_code == 200, preview.text
    assert preview.json()["data"]["schedule_count"] == 1
    assert preview.json()["data"]["total_amount"] == "1060.00"
    assert len(schedule_selects) == 2

    run_headers = {**headers, "Idempotency-Key": "schedule-run-202603"}
    first = client.post(
        "/api/v1/billing/runs",
        headers=run_headers,
        json={"as_of": "2026-03-31", "park_id": park["id"]},
    )
    assert first.status_code == 200, first.text
    assert first.json()["data"]["created_count"] == 1
    replay = client.post(
        "/api/v1/billing/runs",
        headers=run_headers,
        json={"as_of": "2026-03-31", "park_id": park["id"]},
    )
    assert replay.status_code == 200
    assert replay.json()["data"] == first.json()["data"]
    conflict = client.post(
        "/api/v1/billing/runs",
        headers=run_headers,
        json={"as_of": "2026-04-30", "park_id": park["id"]},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_KEY_CONFLICT"

    db_session.expire_all()
    created_bill = db_session.scalar(
        select(Bill).where(Bill.source == "LEASE_SCHEDULE", Bill.contract_id == contract.id)
    )
    assert created_bill is not None
    assert created_bill.status == "ISSUED"
    assert Decimal(str(created_bill.total_amount)) == Decimal("1060.00")
    assert (
        db_session.scalar(
            select(func.count()).select_from(BillLine).where(BillLine.bill_id == created_bill.id)
        )
        == 1
    )
    assert db_session.get(LeasePerformanceSchedule, current.id).bill_id == created_bill.id
    assert db_session.get(LeasePerformanceSchedule, obsolete.id).bill_id is None


def test_receipt_match_confirm_multi_bill_and_later_allocation(client, db_session: Session) -> None:
    headers = _headers()
    park, party = _seed_party_park(client)
    first_bill = _bill(client, park_id=park["id"], party_id=party["id"], amount="300")
    second_bill = _bill(
        client,
        park_id=park["id"],
        party_id=party["id"],
        amount="500",
        period_start="2026-02-01",
        period_end="2026-02-28",
    )
    payload = _receipt_payload(
        park_id=park["id"], party_id=party["id"], source_ref="BANK-0001", amount="1000"
    )
    ingested = client.post("/api/v1/receipts", headers=headers, json=payload)
    assert ingested.status_code == 200, ingested.text
    receipt = ingested.json()["data"]
    assert "1234567890" not in receipt["payer_account_masked"]
    assert receipt["payer_account_masked"].endswith("7890")

    replay = client.post("/api/v1/receipts", headers=headers, json=payload)
    assert replay.status_code == 200
    assert replay.json()["data"]["id"] == receipt["id"]
    changed = client.post("/api/v1/receipts", headers=headers, json={**payload, "amount": "999"})
    assert changed.status_code == 409
    assert changed.json()["code"] == "RECEIPT_SOURCE_CONFLICT"

    matched = client.post(
        f"/api/v1/receipts/{receipt['id']}/match",
        headers=headers,
        json={"expected_version": receipt["lock_version"]},
    )
    assert matched.status_code == 200, matched.text
    matched_data = matched.json()["data"]
    assert matched_data["status"] == "SUGGESTED"
    assert len(matched_data["candidates"]) == 2
    assert (
        client.get(f"/api/v1/bills/{first_bill['id']}", headers=headers).json()["data"][
            "paid_amount"
        ]
        == "0.00"
    )

    confirmed = client.post(
        f"/api/v1/receipts/{receipt['id']}/confirm",
        headers=headers,
        json={
            "expected_version": matched_data["lock_version"],
            "party_id": party["id"],
            "allocations": [
                {"bill_id": first_bill["id"], "amount": "300"},
                {"bill_id": second_bill["id"], "amount": "400"},
            ],
            "remark": "财务人工复核",
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    payment = confirmed.json()["data"]["payment"]
    assert payment["allocated_amount"] == "700.00"
    assert payment["unapplied_amount"] == "300.00"

    allocated = client.post(
        f"/api/v1/payments/{payment['id']}/allocations",
        headers={**headers, "Idempotency-Key": "later-allocation-0001"},
        json={"allocations": [{"bill_id": second_bill["id"], "amount": "100"}]},
    )
    assert allocated.status_code == 200, allocated.text
    assert allocated.json()["data"]["unapplied_amount"] == "200.00"
    replay_allocation = client.post(
        f"/api/v1/payments/{payment['id']}/allocations",
        headers={**headers, "Idempotency-Key": "later-allocation-0001"},
        json={"allocations": [{"bill_id": second_bill["id"], "amount": "100"}]},
    )
    assert replay_allocation.status_code == 200
    assert replay_allocation.json()["data"] == allocated.json()["data"]

    db_session.expire_all()
    persisted = db_session.get(Payment, payment["id"])
    assert persisted.source_receipt_id == receipt["id"]
    assert db_session.scalar(
        select(func.sum(PaymentAllocation.amount)).where(
            PaymentAllocation.payment_id == payment["id"],
            PaymentAllocation.reversed_at.is_(None),
        )
    ) == Decimal("800.00")
    assert db_session.get(ReceiptTransaction, receipt["id"]).status == "CONFIRMED"


def test_provider_fail_closed_and_receipt_dispute_review(client) -> None:
    headers = _headers()
    park, party = _seed_party_park(client, suffix="争议")
    payload = _receipt_payload(
        park_id=park["id"], party_id=party["id"], source_ref="BANK-DISPUTE", amount="88"
    )
    not_connected = client.post(
        "/api/v1/receipts", headers=headers, json={**payload, "channel": "WECHAT"}
    )
    assert not_connected.status_code == 409
    assert not_connected.json()["code"] == "RECEIPT_PROVIDER_NOT_CONNECTED"
    strict = client.post(
        "/api/v1/receipts", headers=headers, json={**payload, "hidden_admin": True}
    )
    assert strict.status_code == 422

    created = client.post("/api/v1/receipts", headers=headers, json=payload).json()["data"]
    disputed = client.post(
        f"/api/v1/receipts/{created['id']}/dispute",
        headers=headers,
        json={"expected_version": created["lock_version"], "reason": "付款人否认流水"},
    )
    assert disputed.status_code == 200, disputed.text
    disputed_data = disputed.json()["data"]
    resolved = client.post(
        f"/api/v1/receipts/{created['id']}/dispute/resolve",
        headers=headers,
        json={
            "expected_version": disputed_data["lock_version"],
            "decision": "RETURN_TO_FINANCE",
            "remark": "银行回单已核实",
        },
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["data"]["status"] == "PENDING"


def test_receipt_batch_is_atomic_and_datetime_errors_are_controlled(
    client, db_session: Session
) -> None:
    headers = _headers()
    park, party = _seed_party_park(client, suffix="批量")
    first = _receipt_payload(
        park_id=park["id"], party_id=party["id"], source_ref="BATCH-ROLLBACK", amount="10"
    )
    invalid = {**first, "amount": "11"}
    failed = client.post(
        "/api/v1/receipts/import",
        headers=headers,
        json={"rows": [first, invalid]},
    )
    assert failed.status_code == 409
    assert failed.json()["code"] == "RECEIPT_SOURCE_CONFLICT"
    db_session.expire_all()
    assert db_session.scalar(select(func.count()).select_from(ReceiptTransaction)) == 0

    invalid_receipt = client.post(
        "/api/v1/receipts",
        headers=headers,
        json={**first, "source_ref": "BAD-DATE", "received_at": "not-a-date"},
    )
    assert invalid_receipt.status_code == 400
    assert invalid_receipt.json()["code"] == "VALIDATION_ERROR"
    invalid_payment = client.post(
        "/api/v1/payments",
        headers=headers,
        json={
            "park_id": park["id"],
            "party_id": party["id"],
            "amount": "10",
            "paid_at": "not-a-date",
            "allocations": [],
        },
    )
    assert invalid_payment.status_code == 422
    assert invalid_payment.json()["code"] == "VALIDATION_ERROR"


def test_dunning_levels_permission_idempotency_and_no_fake_delivery(
    client, db_session: Session
) -> None:
    admin = _headers()
    park, party = _seed_party_park(client, suffix="催缴")
    bill = _bill(
        client,
        park_id=park["id"],
        party_id=party["id"],
        amount="600",
        due_date="2026-01-01",
    )
    run_only = _headers(["collection:run"])
    applied = client.post(
        "/api/v1/collection/runs",
        headers={**run_only, "Idempotency-Key": "dunning-run-0001"},
        json={"as_of": "2026-03-05", "park_id": park["id"]},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["data"]["created"] == 1

    second = client.post(
        "/api/v1/collection/runs",
        headers={**run_only, "Idempotency-Key": "dunning-run-0002"},
        json={"as_of": "2026-03-05", "park_id": park["id"]},
    )
    assert second.status_code == 200, second.text
    assert second.json()["data"]["unchanged"] == 1
    conflict = client.post(
        "/api/v1/collection/runs",
        headers={**run_only, "Idempotency-Key": "dunning-run-0002"},
        json={"as_of": "2026-03-06", "park_id": park["id"]},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_KEY_CONFLICT"

    db_session.expire_all()
    case = db_session.scalar(select(CollectionCase).where(CollectionCase.bill_id == bill["id"]))
    assert case is not None
    assert case.level == "L4"
    assert case.overdue_days == 63
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(CollectionRecord)
            .where(CollectionRecord.case_id == case.id)
        )
        == 1
    )

    manual = client.post(
        f"/api/v1/collection/cases/{case.id}/records",
        headers=admin,
        json={"action_type": "SMS", "note": "发送催缴提醒"},
    )
    assert manual.status_code == 200, manual.text
    assert manual.json()["data"]["status"] == "NOT_CONFIGURED"


def test_waiver_requires_approval_and_stale_bill_is_rejected(client) -> None:
    headers = _headers()
    park, party = _seed_party_park(client, suffix="减免")
    bill = _bill(client, park_id=park["id"], party_id=party["id"], amount="1000")
    requested = client.post(
        "/api/v1/receivable-adjustments",
        headers={**headers, "Idempotency-Key": "waiver-request-0001"},
        json={
            "bill_id": bill["id"],
            "adjustment_type": "WAIVER",
            "amount": "100",
            "reason": "经核实的服务中断补偿",
        },
    )
    assert requested.status_code == 200, requested.text
    adjustment = requested.json()["data"]
    blocked = client.post(
        f"/api/v1/receivable-adjustments/{adjustment['id']}/apply",
        headers=headers,
        json={"expected_version": adjustment["lock_version"]},
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "ADJUSTMENT_APPROVAL_REQUIRED"

    approved = client.post(
        f"/api/v1/approvals/{adjustment['approval_id']}/approve",
        headers=headers,
        json={"remark": "验收审批"},
    )
    assert approved.status_code == 200, approved.text
    applied = client.post(
        f"/api/v1/receivable-adjustments/{adjustment['id']}/apply",
        headers=headers,
        json={"expected_version": adjustment["lock_version"]},
    )
    assert applied.status_code == 200, applied.text
    updated = client.get(f"/api/v1/bills/{bill['id']}", headers=headers).json()["data"]
    assert updated["waiver_amount"] == "100.00"
    assert updated["open_amount"] == "900.00"

    stale = client.post(
        "/api/v1/receivable-adjustments",
        headers={**headers, "Idempotency-Key": "bad-debt-request-0001"},
        json={
            "bill_id": bill["id"],
            "adjustment_type": "BAD_DEBT",
            "amount": "50",
            "reason": "仅测试过期快照",
        },
    ).json()["data"]
    paid = client.post(
        "/api/v1/payments",
        headers=headers,
        json={
            "park_id": park["id"],
            "party_id": party["id"],
            "amount": "10",
            "paid_at": "2026-03-06T09:00:00",
            "allocations": [{"bill_id": bill["id"], "amount": "10"}],
        },
    )
    assert paid.status_code == 200, paid.text
    assert (
        client.post(
            f"/api/v1/approvals/{stale['approval_id']}/approve",
            headers=headers,
            json={"remark": "验收审批"},
        ).status_code
        == 200
    )
    rejected = client.post(
        f"/api/v1/receivable-adjustments/{stale['id']}/apply",
        headers=headers,
        json={"expected_version": stale["lock_version"]},
    )
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "ADJUSTMENT_BILL_STALE"


def test_bill_dispute_and_resolution_each_require_approval(client) -> None:
    headers = _headers()
    park, party = _seed_party_park(client, suffix="账单争议")
    bill = _bill(client, park_id=park["id"], party_id=party["id"], amount="680")

    dispute = client.post(
        "/api/v1/receivable-adjustments",
        headers={**headers, "Idempotency-Key": "bill-dispute-open-0001"},
        json={
            "bill_id": bill["id"],
            "adjustment_type": "DISPUTE",
            "reason": "租户对本期面积计费提出异议",
        },
    ).json()["data"]
    assert (
        client.post(
            f"/api/v1/receivable-adjustments/{dispute['id']}/apply",
            headers=headers,
            json={"expected_version": dispute["lock_version"]},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/approvals/{dispute['approval_id']}/approve",
            headers=headers,
            json={"remark": "同意暂停催缴并核查"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/receivable-adjustments/{dispute['id']}/apply",
            headers=headers,
            json={"expected_version": dispute["lock_version"]},
        ).status_code
        == 200
    )
    opened = client.get(f"/api/v1/bills/{bill['id']}", headers=headers).json()["data"]
    assert opened["collection_hold"] is True
    assert opened["dispute_status"] == "OPEN"

    resolution = client.post(
        "/api/v1/receivable-adjustments",
        headers={**headers, "Idempotency-Key": "bill-dispute-resolve-0001"},
        json={
            "bill_id": bill["id"],
            "adjustment_type": "DISPUTE_RESOLUTION",
            "reason": "双方完成计费依据复核，维持原账单",
        },
    ).json()["data"]
    blocked = client.post(
        f"/api/v1/receivable-adjustments/{resolution['id']}/apply",
        headers=headers,
        json={"expected_version": resolution["lock_version"]},
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "ADJUSTMENT_APPROVAL_REQUIRED"
    assert (
        client.post(
            f"/api/v1/approvals/{resolution['approval_id']}/approve",
            headers=headers,
            json={"remark": "复核证据完整，同意解除"},
        ).status_code
        == 200
    )
    applied = client.post(
        f"/api/v1/receivable-adjustments/{resolution['id']}/apply",
        headers=headers,
        json={"expected_version": resolution["lock_version"]},
    )
    assert applied.status_code == 200, applied.text
    resolved = client.get(f"/api/v1/bills/{bill['id']}", headers=headers).json()["data"]
    assert resolved["collection_hold"] is False
    assert resolved["dispute_status"] == "RESOLVED"

    duplicate_resolution = client.post(
        "/api/v1/receivable-adjustments",
        headers={**headers, "Idempotency-Key": "bill-dispute-resolve-0002"},
        json={
            "bill_id": bill["id"],
            "adjustment_type": "DISPUTE_RESOLUTION",
            "reason": "不得重复解除",
        },
    )
    assert duplicate_resolution.status_code == 409
    assert duplicate_resolution.json()["code"] == "BILL_DISPUTE_NOT_OPEN"


def test_receipts_fail_closed_for_tenant_park_scope_permissions_and_query_pollution(
    client, db_session: Session
) -> None:
    admin = _headers()
    park, party = _seed_party_park(client, suffix="安全")
    hidden_park, _ = _seed_party_park(client, suffix="范围外")
    created = client.post(
        "/api/v1/receipts",
        headers=admin,
        json=_receipt_payload(
            park_id=park["id"],
            party_id=party["id"],
            source_ref="SECURITY-RECEIPT-0001",
            amount="99",
        ),
    ).json()["data"]

    read_only = _headers(["payment:read"])
    assert client.get("/api/v1/receipts", headers=read_only).status_code == 200
    denied_match = client.post(
        f"/api/v1/receipts/{created['id']}/match",
        headers=read_only,
        json={"expected_version": created["lock_version"]},
    )
    assert denied_match.status_code == 403
    assert denied_match.json()["code"] == "PERMISSION_DENIED"

    scoped = _headers(
        ["payment:read", "payment:review", "payment:import"],
        park_scope_mode="LIST",
        park_ids=[hidden_park["id"]],
    )
    invisible = client.get(f"/api/v1/receipts/{created['id']}", headers=scoped)
    assert invisible.status_code == 404
    assert invisible.json()["code"] == "RECEIPT_NOT_FOUND"
    scoped_list = client.get("/api/v1/receipts", headers=scoped).json()["data"]
    assert scoped_list["total"] == 0
    denied_import = client.post(
        "/api/v1/receipts",
        headers=scoped,
        json=_receipt_payload(
            park_id=park["id"],
            party_id=party["id"],
            source_ref="SECURITY-RECEIPT-0002",
            amount="20",
        ),
    )
    assert denied_import.status_code == 403
    assert denied_import.json()["code"] == "PARK_SCOPE_DENIED"

    foreign_tenant = Tenant(code="receivables-foreign", name="应收隔离租户", status="ACTIVE")
    db_session.add(foreign_tenant)
    db_session.flush()
    foreign_park = Park(
        tenant_id=foreign_tenant.id,
        name="外租户园区",
        address="不得访问",
        status="ACTIVE",
    )
    db_session.add(foreign_park)
    db_session.commit()
    cross_tenant = client.post(
        "/api/v1/receipts",
        headers=admin,
        json={
            **_receipt_payload(
                park_id=foreign_park.id,
                party_id=party["id"],
                source_ref="SECURITY-CROSS-TENANT",
                amount="20",
            ),
            "party_id": None,
        },
    )
    assert cross_tenant.status_code == 404
    assert cross_tenant.json()["code"] == "PARK_NOT_FOUND"

    duplicate_query = client.get(
        "/api/v1/receipts?page=1&page=2&page_size=20",
        headers=read_only,
    )
    assert duplicate_query.status_code == 400
    assert duplicate_query.json() == {
        "code": "DUPLICATE_QUERY_PARAMETER",
        "message": "查询参数不得重复",
        "data": {"parameter": "page"},
    }


def test_payment_page_batches_active_allocation_totals(client, db_session: Session) -> None:
    headers = _headers()
    park, party = _seed_party_park(client, suffix="批量余额")
    bill = _bill(client, park_id=park["id"], party_id=party["id"], amount="1000")
    payments: list[Payment] = []
    for index in range(3):
        payment = Payment(
            tenant_id=1,
            park_id=park["id"],
            party_id=party["id"],
            payment_no=f"PAY-BATCH-{index}",
            amount=Decimal("100.00"),
            method="BANK_TRANSFER",
            paid_at=datetime(2026, 3, 5, 10, index),
            status="CONFIRMED",
            operator_id=1,
        )
        db_session.add(payment)
        payments.append(payment)
    db_session.flush()
    for payment in payments:
        db_session.add(
            PaymentAllocation(
                tenant_id=1,
                payment_id=payment.id,
                bill_id=bill["id"],
                amount=Decimal("25.00"),
                created_at=datetime(2026, 3, 5, 11, 0),
            )
        )
    db_session.commit()

    allocation_selects: list[str] = []

    def capture_allocation_selects(_conn, _cursor, statement, _parameters, _context, _many):
        normalized = statement.lower()
        if normalized.lstrip().startswith("select") and "payment_allocations" in normalized:
            allocation_selects.append(normalized)

    event.listen(db_session.get_bind(), "before_cursor_execute", capture_allocation_selects)
    try:
        response = client.get(
            "/api/v1/payments",
            headers=headers,
            params={"page": 1, "page_size": 100, "park_id": park["id"]},
        )
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", capture_allocation_selects)
    assert response.status_code == 200, response.text
    items = response.json()["data"]["items"]
    assert len(items) == 3
    assert {item["allocated_amount"] for item in items} == {"25.00"}
    assert {item["unapplied_amount"] for item in items} == {"75.00"}
    assert len(allocation_selects) == 1

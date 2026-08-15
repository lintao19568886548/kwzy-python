"""Supply lifecycle, isolation, privacy, idempotency, and stock-truth acceptance."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.security import create_access_token


def _headers(
    *, permissions: list[str] | None = None, park_ids: list[int] | None = None, mode: str = "ALL"
) -> dict[str, str]:
    token = create_access_token(
        subject="supply-acceptance",
        claims={
            "uid": 1,
            "tenant_id": 1,
            "permissions": permissions or ["*"],
            "park_ids": park_ids or [],
            "park_scope_mode": mode,
            "tv": 0,
        },
    )
    return {"Authorization": f"Bearer {token}"}


def _key(headers: dict[str, str], value: str) -> dict[str, str]:
    return {**headers, "Idempotency-Key": value}


def _park(client, headers: dict[str, str], label: str) -> dict:
    response = client.post(
        "/api/v1/parks",
        headers=headers,
        json={"name": f"{label}-{uuid4().hex[:8]}", "address": "合成供应链验收地址"},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _supplier_party(client, headers: dict[str, str]) -> dict:
    suffix = uuid4().hex[:10].upper()
    response = client.post(
        "/api/v1/parties",
        headers=headers,
        json={
            "name": f"合成供应商{suffix}",
            "party_type": "ORGANIZATION",
            "credit_code": f"91310000{suffix}",
        },
    )
    assert response.status_code == 200, response.text
    party = response.json()["data"]
    role = client.post(
        f"/api/v1/parties/{party['id']}/roles",
        headers=headers,
        json={"role_code": "SUPPLIER"},
    )
    assert role.status_code == 200, role.text
    return party


def _approval_definition(client, headers: dict[str, str], biz_type: str) -> str:
    code = f"SUPPLY_{biz_type}_{uuid4().hex[:6]}".upper()
    response = client.post(
        "/api/v1/approval-definitions",
        headers=headers,
        json={
            "code": code,
            "name": f"{biz_type} 合成验收审批",
            "biz_type": biz_type,
            "steps": [
                {
                    "step_order": 1,
                    "name": "负责人复核",
                    "approval_mode": "ANY",
                    "min_approvals": 1,
                    "sla_hours": 24,
                    "assignees": [{"user_id": 1}],
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    definition = response.json()["data"]
    draft = next(row for row in definition["versions"] if row["status"] == "DRAFT")
    published = client.post(
        f"/api/v1/approval-definitions/{definition['id']}/publish",
        headers=headers,
        json={"version_id": draft["id"], "expected_lock_version": 0},
    )
    assert published.status_code == 200, published.text
    return code


def _approve(client, headers: dict[str, str], approval_id: int, key: str) -> None:
    detail_response = client.get(f"/api/v1/approvals/{approval_id}", headers=headers)
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()["data"]
    task = next(row for row in detail["tasks"] if row["status"] == "PENDING")
    response = client.post(
        f"/api/v1/approval-tasks/{task['id']}/decide",
        headers=headers,
        json={
            "action": "APPROVE",
            "expected_version": detail["lock_version"],
            "idempotency_key": key,
            "override_reason": "供应链独立验收管理员审批门禁",
        },
    )
    assert response.status_code == 200, response.text


def test_supply_procurement_inventory_and_outsourcing_lifecycle(client) -> None:
    admin = _headers()
    park = _park(client, admin, "供应园")
    other = _park(client, admin, "隔离园")
    party = _supplier_party(client, admin)

    supplier_response = client.post(
        "/api/v1/supply/suppliers",
        headers=admin,
        json={
            "party_id": party["id"],
            "code": f"SUP_{uuid4().hex[:6]}",
            "display_name": "本地受控供应商",
        },
    )
    assert supplier_response.status_code == 200, supplier_response.text
    supplier = supplier_response.json()["data"]
    scope = client.post(
        f"/api/v1/supply/suppliers/{supplier['id']}/scopes",
        headers=admin,
        json={"park_id": park["id"], "service_type": "GENERAL"},
    )
    assert scope.status_code == 200, scope.text
    qualification = client.post(
        f"/api/v1/supply/suppliers/{supplier['id']}/qualifications",
        headers=admin,
        json={
            "qualification_type": "SERVICE_LICENSE",
            "credential_number": "SUPPLY-SECRET-99887766",
            "issuer": "合成发证机构",
            "effective_on": datetime.now(timezone.utc).date().isoformat(),
            "expires_on": (datetime.now(timezone.utc).date() + timedelta(days=365)).isoformat(),
        },
    )
    assert qualification.status_code == 200, qualification.text
    assert "SUPPLY-SECRET-99887766" not in qualification.text
    assert qualification.json()["data"]["qualifications"][0]["credential_masked"].endswith("7766")

    material_response = client.post(
        "/api/v1/supply/materials",
        headers=admin,
        json={
            "code": f"MAT_{uuid4().hex[:6]}",
            "name": "防水材料",
            "category": "维修耗材",
            "unit": "箱",
            "reorder_point": "2",
        },
    )
    assert material_response.status_code == 200, material_response.text
    material = material_response.json()["data"]
    material_query = client.get(
        f"/api/v1/supply/materials?keyword={material['code'].lower()}&status=ACTIVE&page=1&page_size=1",
        headers=admin,
    )
    assert material_query.status_code == 200, material_query.text
    assert [row["id"] for row in material_query.json()["data"]] == [material["id"]]
    assert client.get("/api/v1/supply/materials?page_size=201", headers=admin).status_code == 422
    warehouse_response = client.post(
        "/api/v1/supply/warehouses",
        headers=admin,
        json={"park_id": park["id"], "code": f"WH_{uuid4().hex[:6]}", "name": "维修主仓"},
    )
    assert warehouse_response.status_code == 200, warehouse_response.text
    warehouse = warehouse_response.json()["data"]
    warehouse_query = client.get(
        f"/api/v1/supply/warehouses?park_id={park['id']}&keyword=维修主仓&status=ACTIVE&page_size=1",
        headers=admin,
    )
    assert warehouse_query.status_code == 200, warehouse_query.text
    assert [row["id"] for row in warehouse_query.json()["data"]] == [warehouse["id"]]

    procurement_key = f"proc-{uuid4().hex}"
    procurement_payload = {
        "park_id": park["id"],
        "purpose": "季度维修材料采购",
        "lines": [
            {"material_id": material["id"], "quantity": "10", "estimated_unit_price": "35.50"}
        ],
    }
    procurement_response = client.post(
        "/api/v1/supply/procurement/requisitions",
        headers=_key(admin, procurement_key),
        json=procurement_payload,
    )
    assert procurement_response.status_code == 200, procurement_response.text
    procurement = procurement_response.json()["data"]
    replay = client.post(
        "/api/v1/supply/procurement/requisitions",
        headers=_key(admin, procurement_key),
        json=procurement_payload,
    )
    assert replay.status_code == 200
    assert replay.json()["data"]["id"] == procurement["id"]
    conflict = client.post(
        "/api/v1/supply/procurement/requisitions",
        headers=_key(admin, procurement_key),
        json={**procurement_payload, "purpose": "不同采购"},
    )
    assert conflict.status_code == 409

    procurement_definition = _approval_definition(client, admin, "PROCUREMENT_REQUISITION")
    cancellable = client.post(
        "/api/v1/supply/procurement/requisitions",
        headers=_key(admin, f"cancel-proc-{uuid4().hex}"),
        json={**procurement_payload, "purpose": "待撤回采购"},
    ).json()["data"]
    editable_payload = {
        **procurement_payload,
        "purpose": "更新后的待撤回采购",
        "expected_version": cancellable["lock_version"],
    }
    editable = client.put(
        f"/api/v1/supply/procurement/requisitions/{cancellable['id']}/draft",
        headers=admin,
        json=editable_payload,
    )
    assert editable.status_code == 200, editable.text
    cancellable = editable.json()["data"]
    assert cancellable["purpose"] == "更新后的待撤回采购"
    cancellable = client.post(
        f"/api/v1/supply/procurement/requisitions/{cancellable['id']}/submit",
        headers=_key(admin, f"cancel-submit-{uuid4().hex}"),
        json={
            "expected_version": cancellable["lock_version"],
            "definition_code": procurement_definition,
        },
    ).json()["data"]
    frozen = client.put(
        f"/api/v1/supply/procurement/requisitions/{cancellable['id']}/draft",
        headers=admin,
        json={**editable_payload, "expected_version": cancellable["lock_version"]},
    )
    assert frozen.status_code == 409
    cancel_key = f"cancel-{'x' * 100}"
    cancelled = client.post(
        f"/api/v1/supply/procurement/requisitions/{cancellable['id']}/cancel",
        headers=_key(admin, cancel_key),
        json={
            "expected_version": cancellable["lock_version"],
            "reason": "需求已由现有库存满足",
        },
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == "CANCELLED"
    withdrawn = client.get(f"/api/v1/approvals/{cancellable['approval_id']}", headers=admin)
    assert withdrawn.status_code == 200, withdrawn.text
    assert withdrawn.json()["data"]["status"] == "WITHDRAWN"
    submitted = client.post(
        f"/api/v1/supply/procurement/requisitions/{procurement['id']}/submit",
        headers=_key(admin, f"proc-submit-{uuid4().hex}"),
        json={
            "expected_version": procurement["lock_version"],
            "definition_code": procurement_definition,
            "priority": "HIGH",
        },
    )
    assert submitted.status_code == 200, submitted.text
    submitted_data = submitted.json()["data"]
    _approve(client, admin, submitted_data["approval_id"], f"proc-approve-{uuid4().hex}")
    synced = client.post(
        f"/api/v1/supply/procurement/requisitions/{procurement['id']}/sync", headers=admin
    )
    assert synced.status_code == 200, synced.text
    assert synced.json()["data"]["status"] == "APPROVED"

    request_line = synced.json()["data"]["lines"][0]
    order_response = client.post(
        "/api/v1/supply/procurement/orders",
        headers=_key(admin, f"order-{uuid4().hex}"),
        json={
            "requisition_id": procurement["id"],
            "supplier_id": supplier["id"],
            "truth_mode": "LOCAL",
            "currency": "CNY",
            "required_qualification": "SERVICE_LICENSE",
            "lines": [{"requisition_line_id": request_line["id"], "unit_price": "34.00"}],
        },
    )
    assert order_response.status_code == 200, order_response.text
    order = order_response.json()["data"]
    acknowledged = client.post(
        f"/api/v1/supply/procurement/orders/{order['id']}/acknowledge",
        headers=admin,
        json={"expected_version": order["lock_version"], "accepted": True},
    )
    assert acknowledged.status_code == 200, acknowledged.text
    order = acknowledged.json()["data"]

    receipt_key = f"receipt-{uuid4().hex}"
    receipt_payload = {
        "warehouse_id": warehouse["id"],
        "lines": [
            {"order_line_id": order["lines"][0]["id"], "quantity": "6", "batch_no": "BATCH-01"}
        ],
    }
    receipt = client.post(
        f"/api/v1/supply/procurement/orders/{order['id']}/receipts",
        headers=_key(admin, receipt_key),
        json=receipt_payload,
    )
    assert receipt.status_code == 200, receipt.text
    receipt_replay = client.post(
        f"/api/v1/supply/procurement/orders/{order['id']}/receipts",
        headers=_key(admin, receipt_key),
        json=receipt_payload,
    )
    assert receipt_replay.status_code == 200
    assert receipt_replay.json()["data"]["id"] == receipt.json()["data"]["id"]
    over_receipt = client.post(
        f"/api/v1/supply/procurement/orders/{order['id']}/receipts",
        headers=_key(admin, f"over-{uuid4().hex}"),
        json={
            "warehouse_id": warehouse["id"],
            "lines": [{"order_line_id": order["lines"][0]["id"], "quantity": "5"}],
        },
    )
    assert over_receipt.status_code == 409
    final_receipt = client.post(
        f"/api/v1/supply/procurement/orders/{order['id']}/receipts",
        headers=_key(admin, f"final-{uuid4().hex}"),
        json={
            "warehouse_id": warehouse["id"],
            "lines": [{"order_line_id": order["lines"][0]["id"], "quantity": "4"}],
        },
    )
    assert final_receipt.status_code == 200, final_receipt.text
    balances = client.get(
        f"/api/v1/supply/inventory/balances?park_id={park['id']}&warehouse_id={warehouse['id']}",
        headers=admin,
    ).json()["data"]
    assert balances[0]["on_hand_qty"] == "10.0000"

    inventory_definition = _approval_definition(client, admin, "INVENTORY_REQUISITION")
    inventory_response = client.post(
        "/api/v1/supply/inventory/requisitions",
        headers=_key(admin, f"inventory-{uuid4().hex}"),
        json={
            "park_id": park["id"],
            "purpose": "现场维修领料",
            "lines": [
                {"warehouse_id": warehouse["id"], "material_id": material["id"], "quantity": "5"}
            ],
        },
    )
    assert inventory_response.status_code == 200, inventory_response.text
    inventory = inventory_response.json()["data"]
    inventory_submit = client.post(
        f"/api/v1/supply/inventory/requisitions/{inventory['id']}/submit",
        headers=_key(admin, f"inventory-submit-{uuid4().hex}"),
        json={
            "expected_version": inventory["lock_version"],
            "definition_code": inventory_definition,
        },
    )
    assert inventory_submit.status_code == 200, inventory_submit.text
    inventory = inventory_submit.json()["data"]
    _approve(client, admin, inventory["approval_id"], f"inventory-approve-{uuid4().hex}")
    inventory_sync = client.post(
        f"/api/v1/supply/inventory/requisitions/{inventory['id']}/sync", headers=admin
    )
    assert inventory_sync.status_code == 200, inventory_sync.text
    inventory = inventory_sync.json()["data"]
    assert inventory["lines"][0]["reserved_qty"] == "5.0000"
    issue_key = f"issue-{uuid4().hex}"
    issue_payload = {"lines": [{"line_id": inventory["lines"][0]["id"], "quantity": "3"}]}
    issued = client.post(
        f"/api/v1/supply/inventory/requisitions/{inventory['id']}/issue",
        headers=_key(admin, issue_key),
        json=issue_payload,
    )
    assert issued.status_code == 200, issued.text
    issue_replay = client.post(
        f"/api/v1/supply/inventory/requisitions/{inventory['id']}/issue",
        headers=_key(admin, issue_key),
        json=issue_payload,
    )
    assert issue_replay.status_code == 200
    returned = client.post(
        f"/api/v1/supply/inventory/requisitions/{inventory['id']}/return",
        headers=_key(admin, f"return-{uuid4().hex}"),
        json={"line_id": inventory["lines"][0]["id"], "quantity": "1"},
    )
    assert returned.status_code == 200, returned.text

    current_balance = client.get(
        f"/api/v1/supply/inventory/balances?park_id={park['id']}&warehouse_id={warehouse['id']}",
        headers=admin,
    ).json()["data"][0]
    stocktake = client.post(
        "/api/v1/supply/inventory/stocktakes",
        headers=_key(admin, f"stocktake-{uuid4().hex}"),
        json={
            "warehouse_id": warehouse["id"],
            "lines": [
                {"material_id": material["id"], "counted_qty": current_balance["on_hand_qty"]}
            ],
        },
    )
    assert stocktake.status_code == 200, stocktake.text
    stocktake_data = stocktake.json()["data"]
    submitted_stocktake = client.post(
        f"/api/v1/supply/inventory/stocktakes/{stocktake_data['id']}/submit",
        headers=_key(admin, f"stocktake-submit-{uuid4().hex}"),
        json={
            "expected_version": stocktake_data["lock_version"],
            "definition_code": procurement_definition,
        },
    )
    assert submitted_stocktake.status_code == 200, submitted_stocktake.text
    posted_stocktake = client.post(
        f"/api/v1/supply/inventory/stocktakes/{stocktake_data['id']}/post",
        headers=_key(admin, f"stocktake-post-{uuid4().hex}"),
    )
    assert posted_stocktake.status_code == 200, posted_stocktake.text
    assert posted_stocktake.json()["data"]["status"] == "POSTED"

    outsourcing_definition = _approval_definition(client, admin, "OUTSOURCING_ORDER")
    outsourcing_response = client.post(
        "/api/v1/supply/outsourcing/orders",
        headers=_key(admin, f"outsource-{uuid4().hex}"),
        json={
            "park_id": park["id"],
            "supplier_id": supplier["id"],
            "title": "屋面防水外包",
            "deliverables": [{"code": "REPORT", "name": "完工报告", "required": True}],
            "sla_due_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "amount": "3000.00",
            "required_qualification": "SERVICE_LICENSE",
        },
    )
    assert outsourcing_response.status_code == 200, outsourcing_response.text
    outsourcing = outsourcing_response.json()["data"]
    outsourcing_submit = client.post(
        f"/api/v1/supply/outsourcing/orders/{outsourcing['id']}/submit",
        headers=_key(admin, f"outsource-submit-{uuid4().hex}"),
        json={
            "expected_version": outsourcing["lock_version"],
            "definition_code": outsourcing_definition,
            "required_qualification": "SERVICE_LICENSE",
        },
    )
    assert outsourcing_submit.status_code == 200, outsourcing_submit.text
    outsourcing = outsourcing_submit.json()["data"]
    _approve(client, admin, outsourcing["approval_id"], f"outsource-approve-{uuid4().hex}")
    outsourcing_sync = client.post(
        f"/api/v1/supply/outsourcing/orders/{outsourcing['id']}/sync", headers=admin
    )
    assert outsourcing_sync.status_code == 200, outsourcing_sync.text
    for event_type, evidence in [
        ("STARTED", None),
        ("COMPLETED", [{"type": "REPORT", "reference": "attachment://synthetic/report-1"}]),
    ]:
        event = client.post(
            f"/api/v1/supply/outsourcing/orders/{outsourcing['id']}/events",
            headers=_key(admin, f"outsource-event-{event_type}-{uuid4().hex}"),
            json={"event_type": event_type, "note": "合成履约证据", "evidence": evidence},
        )
        assert event.status_code == 200, event.text
    rework = client.post(
        f"/api/v1/supply/outsourcing/orders/{outsourcing['id']}/acceptance",
        headers=_key(admin, f"outsource-rework-{uuid4().hex}"),
        json={"accepted": False, "reason": "防水收边不符合验收要求"},
    )
    assert rework.status_code == 200, rework.text
    assert rework.json()["data"]["status"] == "REWORK"
    for event_type, evidence in [
        ("STARTED", None),
        ("COMPLETED", [{"type": "REPORT", "reference": "attachment://synthetic/report-2"}]),
    ]:
        event = client.post(
            f"/api/v1/supply/outsourcing/orders/{outsourcing['id']}/events",
            headers=_key(admin, f"outsource-rework-event-{event_type}-{uuid4().hex}"),
            json={"event_type": event_type, "note": "返工完成", "evidence": evidence},
        )
        assert event.status_code == 200, event.text
    accepted = client.post(
        f"/api/v1/supply/outsourcing/orders/{outsourcing['id']}/acceptance",
        headers=_key(admin, f"outsource-accept-{uuid4().hex}"),
        json={"accepted": True, "score": 5, "comment": "返工后验收通过"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["data"]["status"] == "ACCEPTED"
    assert accepted.json()["data"]["settlement_state"] == "NOT_INTEGRATED"

    scoped = _headers(permissions=["supply:read"], park_ids=[other["id"]], mode="LIST")
    hidden = client.get(f"/api/v1/supply/warehouses?park_id={park['id']}", headers=scoped)
    assert hidden.status_code == 404
    overview = client.get("/api/v1/supply/overview", headers=admin)
    assert overview.status_code == 200
    assert overview.json()["data"]["external_integrations"]["erp"] == "NOT_CONNECTED"
    assert overview.json()["data"]["legacy_data_migration"]["status"] == "BLOCKED"


def test_supply_rejects_unknown_fields_and_permission_forgery(client) -> None:
    admin = _headers()
    park = _park(client, admin, "严格契约园")
    unknown = client.post(
        "/api/v1/supply/materials",
        headers=admin,
        json={
            "code": "MAT_STRICT",
            "name": "严格物料",
            "category": "验收",
            "unit": "件",
            "unexpected": True,
        },
    )
    assert unknown.status_code == 422

    forged = _headers(permissions=["supply:read"], park_ids=[park["id"]], mode="LIST")
    forged.update({"X-Permissions": "inventory:manage", "X-Tenant-Id": "999"})
    denied = client.post(
        "/api/v1/supply/warehouses",
        headers=forged,
        json={"park_id": park["id"], "code": "WH_DENIED", "name": "不得创建"},
    )
    assert denied.status_code == 403

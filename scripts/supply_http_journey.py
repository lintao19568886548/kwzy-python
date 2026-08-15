#!/usr/bin/env python3
"""Loopback-only real HTTP acceptance for supply, procurement, inventory and outsourcing."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import urlparse

import httpx

T = TypeVar("T")


class JourneyFailure(RuntimeError):
    """A supply business-stage assertion failed."""


def loopback_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise argparse.ArgumentTypeError("journey is restricted to loopback targets")
    return value.rstrip("/")


def expect_ok(response: httpx.Response, label: str) -> Any:
    try:
        body = response.json()
    except ValueError as exc:
        raise JourneyFailure(
            f"{label}: non-JSON response {response.status_code}"
        ) from exc
    if response.status_code != 200 or body.get("code") != "OK":
        raise JourneyFailure(
            f"{label}: HTTP {response.status_code} code={body.get('code')} "
            f"message={body.get('message')}"
        )
    return body.get("data")


def expect_error(response: httpx.Response, status: int, code: str, label: str) -> None:
    try:
        body = response.json()
    except ValueError as exc:
        raise JourneyFailure(
            f"{label}: non-JSON response {response.status_code}"
        ) from exc
    if response.status_code != status or body.get("code") != code:
        raise JourneyFailure(
            f"{label}: expected {status}/{code}, got {response.status_code}/{body.get('code')}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url", type=loopback_url, default="http://127.0.0.1:8010/api/v1"
    )
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    suffix = uuid.uuid4().hex[:10].upper()
    now = datetime.now(timezone.utc)
    stages: list[dict[str, Any]] = []

    def stage(name: str, operation: Callable[[], T]) -> T:
        tick = time.perf_counter()
        result = operation()
        stages.append(
            {
                "name": name,
                "passed": True,
                "ms": round((time.perf_counter() - tick) * 1000, 2),
            }
        )
        return result

    def key() -> str:
        return f"supply-http-{uuid.uuid4().hex}"

    with httpx.Client(base_url=args.base_url, timeout=30.0) as client:
        login = stage(
            "login",
            lambda: expect_ok(
                client.post(
                    "/auth/login",
                    json={
                        "username": args.username,
                        "password": args.password,
                        "tenant_code": "default",
                    },
                ),
                "login",
            ),
        )
        client.headers.update(
            {
                "Authorization": f"Bearer {login['access_token']}",
                "X-Client-Platform": "supply-acceptance-http",
            }
        )
        me = stage("identity", lambda: expect_ok(client.get("/auth/me"), "identity"))
        park = stage(
            "create_park",
            lambda: expect_ok(
                client.post(
                    "/parks",
                    json={"name": f"HTTP 供应园 {suffix}", "address": "合成验收地址"},
                ),
                "create park",
            ),
        )
        party = stage(
            "create_supplier_party",
            lambda: expect_ok(
                client.post(
                    "/parties",
                    json={
                        "name": f"HTTP 供应商主体 {suffix}",
                        "party_type": "ORGANIZATION",
                        "credit_code": f"91310000{suffix}",
                    },
                ),
                "create supplier party",
            ),
        )
        stage(
            "assign_supplier_party_role",
            lambda: expect_ok(
                client.post(
                    f"/parties/{party['id']}/roles", json={"role_code": "SUPPLIER"}
                ),
                "assign supplier role",
            ),
        )
        supplier = stage(
            "create_local_supplier",
            lambda: expect_ok(
                client.post(
                    "/supply/suppliers",
                    json={
                        "party_id": party["id"],
                        "code": f"SUP_{suffix}",
                        "display_name": f"HTTP 受控供应商 {suffix}",
                    },
                ),
                "create supplier",
            ),
        )
        stage(
            "scope_supplier_to_park",
            lambda: expect_ok(
                client.post(
                    f"/supply/suppliers/{supplier['id']}/scopes",
                    json={"park_id": park["id"], "service_type": "GENERAL"},
                ),
                "supplier scope",
            ),
        )
        raw_credential = f"HTTP-SECRET-{suffix}"
        qualified = stage(
            "mask_supplier_credential",
            lambda: expect_ok(
                client.post(
                    f"/supply/suppliers/{supplier['id']}/qualifications",
                    json={
                        "qualification_type": "SERVICE_LICENSE",
                        "credential_number": raw_credential,
                        "issuer": "合成发证机构",
                        "effective_on": now.date().isoformat(),
                        "expires_on": (now.date() + timedelta(days=365)).isoformat(),
                    },
                ),
                "supplier qualification",
            ),
        )
        if raw_credential in json.dumps(qualified, ensure_ascii=False):
            raise JourneyFailure("raw supplier credential leaked through real HTTP")

        material = stage(
            "create_material",
            lambda: expect_ok(
                client.post(
                    "/supply/materials",
                    json={
                        "code": f"MAT_{suffix}",
                        "name": "HTTP 防水材料",
                        "category": "维修耗材",
                        "unit": "箱",
                        "reorder_point": "2",
                    },
                ),
                "create material",
            ),
        )
        oversized_page = stage(
            "reject_unbounded_catalogue_page",
            lambda: client.get("/supply/materials?page_size=201"),
        )
        if oversized_page.status_code != 422:
            raise JourneyFailure(
                f"unbounded material page expected 422, got {oversized_page.status_code}"
            )
        material_filter = stage(
            "filter_material_catalogue",
            lambda: expect_ok(
                client.get(
                    f"/supply/materials?keyword={material['code'].lower()}&status=ACTIVE&page_size=1"
                ),
                "filter materials",
            ),
        )
        if [row["id"] for row in material_filter] != [material["id"]]:
            raise JourneyFailure("normalized material filter returned the wrong record")
        warehouse = stage(
            "create_park_warehouse",
            lambda: expect_ok(
                client.post(
                    "/supply/warehouses",
                    json={
                        "park_id": park["id"],
                        "code": f"WH_{suffix}",
                        "name": "HTTP 维修主仓",
                    },
                ),
                "create warehouse",
            ),
        )

        def approval_definition(biz_type: str) -> str:
            code = f"SUPPLY_HTTP_{biz_type}_{suffix}"
            definition = expect_ok(
                client.post(
                    "/approval-definitions",
                    json={
                        "code": code,
                        "name": f"HTTP {biz_type} 审批",
                        "biz_type": biz_type,
                        "steps": [
                            {
                                "step_order": 1,
                                "name": "HTTP 负责人复核",
                                "approval_mode": "ANY",
                                "min_approvals": 1,
                                "sla_hours": 24,
                                "assignees": [{"user_id": me["id"]}],
                            }
                        ],
                    },
                ),
                f"create {biz_type} definition",
            )
            draft = next(
                row for row in definition["versions"] if row["status"] == "DRAFT"
            )
            expect_ok(
                client.post(
                    f"/approval-definitions/{definition['id']}/publish",
                    json={"version_id": draft["id"], "expected_lock_version": 0},
                ),
                f"publish {biz_type} definition",
            )
            return code

        def approve(approval_id: int) -> None:
            detail = expect_ok(
                client.get(f"/approvals/{approval_id}"), "approval detail"
            )
            task = next(row for row in detail["tasks"] if row["status"] == "PENDING")
            expect_ok(
                client.post(
                    f"/approval-tasks/{task['id']}/decide",
                    json={
                        "action": "APPROVE",
                        "expected_version": detail["lock_version"],
                        "idempotency_key": key(),
                        "override_reason": "供应链真实HTTP独立验收",
                    },
                ),
                "approval decision",
            )

        procurement_payload = {
            "park_id": park["id"],
            "purpose": f"HTTP 维修采购 {suffix}",
            "lines": [
                {
                    "material_id": material["id"],
                    "quantity": "10",
                    "estimated_unit_price": "35.50",
                }
            ],
        }
        procurement_key = key()
        procurement = stage(
            "create_procurement_requisition",
            lambda: expect_ok(
                client.post(
                    "/supply/procurement/requisitions",
                    headers={"Idempotency-Key": procurement_key},
                    json=procurement_payload,
                ),
                "create procurement",
            ),
        )
        procurement_replay = stage(
            "procurement_idempotent_replay",
            lambda: expect_ok(
                client.post(
                    "/supply/procurement/requisitions",
                    headers={"Idempotency-Key": procurement_key},
                    json=procurement_payload,
                ),
                "procurement replay",
            ),
        )
        if procurement_replay["id"] != procurement["id"]:
            raise JourneyFailure("procurement replay created a new record")
        changed = stage(
            "reject_changed_procurement_replay",
            lambda: client.post(
                "/supply/procurement/requisitions",
                headers={"Idempotency-Key": procurement_key},
                json={**procurement_payload, "purpose": "changed"},
            ),
        )
        expect_error(changed, 409, "IDEMPOTENCY_CONFLICT", "changed procurement replay")

        procurement_definition = stage(
            "publish_procurement_approval_definition",
            lambda: approval_definition("PROCUREMENT_REQUISITION"),
        )
        cancellable = stage(
            "create_cancellable_procurement",
            lambda: expect_ok(
                client.post(
                    "/supply/procurement/requisitions",
                    headers={"Idempotency-Key": key()},
                    json={
                        **procurement_payload,
                        "purpose": f"HTTP 待撤回采购 {suffix}",
                    },
                ),
                "create cancellable procurement",
            ),
        )
        cancellable = stage(
            "edit_procurement_draft",
            lambda: expect_ok(
                client.put(
                    f"/supply/procurement/requisitions/{cancellable['id']}/draft",
                    json={
                        **procurement_payload,
                        "purpose": f"HTTP 更新后的待撤回采购 {suffix}",
                        "expected_version": cancellable["lock_version"],
                    },
                ),
                "edit procurement draft",
            ),
        )
        cancellable = stage(
            "submit_cancellable_procurement",
            lambda: expect_ok(
                client.post(
                    f"/supply/procurement/requisitions/{cancellable['id']}/submit",
                    headers={"Idempotency-Key": key()},
                    json={
                        "expected_version": cancellable["lock_version"],
                        "definition_code": procurement_definition,
                    },
                ),
                "submit cancellable procurement",
            ),
        )
        frozen_draft = stage(
            "reject_submitted_procurement_edit",
            lambda: client.put(
                f"/supply/procurement/requisitions/{cancellable['id']}/draft",
                json={
                    **procurement_payload,
                    "purpose": "不得覆盖已提交快照",
                    "expected_version": cancellable["lock_version"],
                },
            ),
        )
        expect_error(
            frozen_draft,
            409,
            "PROCUREMENT_STATE_INVALID",
            "submitted procurement edit",
        )
        cancellable = stage(
            "cancel_procurement_and_withdraw_approval",
            lambda: expect_ok(
                client.post(
                    f"/supply/procurement/requisitions/{cancellable['id']}/cancel",
                    headers={"Idempotency-Key": f"cancel-{suffix}-{'x' * 100}"},
                    json={
                        "expected_version": cancellable["lock_version"],
                        "reason": "需求已由现有库存满足",
                    },
                ),
                "cancel procurement",
            ),
        )
        withdrawn = stage(
            "verify_cancelled_procurement_approval_withdrawn",
            lambda: expect_ok(
                client.get(f"/approvals/{cancellable['approval_id']}"),
                "withdrawn procurement approval",
            ),
        )
        if cancellable["status"] != "CANCELLED" or withdrawn["status"] != "WITHDRAWN":
            raise JourneyFailure(
                "procurement cancellation did not withdraw native approval"
            )
        procurement = stage(
            "submit_procurement_for_native_approval",
            lambda: expect_ok(
                client.post(
                    f"/supply/procurement/requisitions/{procurement['id']}/submit",
                    headers={"Idempotency-Key": key()},
                    json={
                        "expected_version": procurement["lock_version"],
                        "definition_code": procurement_definition,
                        "priority": "HIGH",
                    },
                ),
                "submit procurement",
            ),
        )
        stage("approve_procurement", lambda: approve(procurement["approval_id"]))
        procurement = stage(
            "sync_approved_procurement",
            lambda: expect_ok(
                client.post(
                    f"/supply/procurement/requisitions/{procurement['id']}/sync"
                ),
                "sync procurement",
            ),
        )
        if procurement["status"] != "APPROVED":
            raise JourneyFailure("procurement did not reach APPROVED")
        order = stage(
            "create_local_purchase_order",
            lambda: expect_ok(
                client.post(
                    "/supply/procurement/orders",
                    headers={"Idempotency-Key": key()},
                    json={
                        "requisition_id": procurement["id"],
                        "supplier_id": supplier["id"],
                        "truth_mode": "LOCAL",
                        "currency": "CNY",
                        "required_qualification": "SERVICE_LICENSE",
                        "lines": [
                            {
                                "requisition_line_id": procurement["lines"][0]["id"],
                                "unit_price": "34.00",
                            }
                        ],
                    },
                ),
                "create order",
            ),
        )
        order = stage(
            "supplier_acknowledge_order",
            lambda: expect_ok(
                client.post(
                    f"/supply/procurement/orders/{order['id']}/acknowledge",
                    json={"expected_version": order["lock_version"], "accepted": True},
                ),
                "acknowledge order",
            ),
        )
        receipt_key = key()
        receipt_payload = {
            "warehouse_id": warehouse["id"],
            "lines": [{"order_line_id": order["lines"][0]["id"], "quantity": "6"}],
        }
        first_receipt = stage(
            "post_partial_goods_receipt",
            lambda: expect_ok(
                client.post(
                    f"/supply/procurement/orders/{order['id']}/receipts",
                    headers={"Idempotency-Key": receipt_key},
                    json=receipt_payload,
                ),
                "partial receipt",
            ),
        )
        replay_receipt = stage(
            "goods_receipt_idempotent_replay",
            lambda: expect_ok(
                client.post(
                    f"/supply/procurement/orders/{order['id']}/receipts",
                    headers={"Idempotency-Key": receipt_key},
                    json=receipt_payload,
                ),
                "receipt replay",
            ),
        )
        if replay_receipt["id"] != first_receipt["id"]:
            raise JourneyFailure("receipt replay created a new record")
        over_receipt = stage(
            "reject_over_receipt",
            lambda: client.post(
                f"/supply/procurement/orders/{order['id']}/receipts",
                headers={"Idempotency-Key": key()},
                json={
                    "warehouse_id": warehouse["id"],
                    "lines": [
                        {"order_line_id": order["lines"][0]["id"], "quantity": "5"}
                    ],
                },
            ),
        )
        expect_error(over_receipt, 409, "OVER_RECEIPT", "over receipt")
        stage(
            "post_final_goods_receipt",
            lambda: expect_ok(
                client.post(
                    f"/supply/procurement/orders/{order['id']}/receipts",
                    headers={"Idempotency-Key": key()},
                    json={
                        "warehouse_id": warehouse["id"],
                        "lines": [
                            {"order_line_id": order["lines"][0]["id"], "quantity": "4"}
                        ],
                    },
                ),
                "final receipt",
            ),
        )
        balances = stage(
            "reconcile_received_stock_balance",
            lambda: expect_ok(
                client.get(
                    f"/supply/inventory/balances?park_id={park['id']}&warehouse_id={warehouse['id']}"
                ),
                "inventory balances",
            ),
        )
        if len(balances) != 1 or balances[0]["on_hand_qty"] != "10.0000":
            raise JourneyFailure(f"unexpected received stock truth: {balances}")

        inventory_definition = stage(
            "publish_inventory_approval_definition",
            lambda: approval_definition("INVENTORY_REQUISITION"),
        )
        inventory = stage(
            "create_inventory_requisition",
            lambda: expect_ok(
                client.post(
                    "/supply/inventory/requisitions",
                    headers={"Idempotency-Key": key()},
                    json={
                        "park_id": park["id"],
                        "purpose": f"HTTP 现场领用 {suffix}",
                        "lines": [
                            {
                                "warehouse_id": warehouse["id"],
                                "material_id": material["id"],
                                "quantity": "5",
                            }
                        ],
                    },
                ),
                "create inventory requisition",
            ),
        )
        inventory = stage(
            "submit_inventory_for_native_approval",
            lambda: expect_ok(
                client.post(
                    f"/supply/inventory/requisitions/{inventory['id']}/submit",
                    headers={"Idempotency-Key": key()},
                    json={
                        "expected_version": inventory["lock_version"],
                        "definition_code": inventory_definition,
                    },
                ),
                "submit inventory requisition",
            ),
        )
        stage(
            "approve_inventory_requisition", lambda: approve(inventory["approval_id"])
        )
        inventory = stage(
            "sync_inventory_and_reserve_stock",
            lambda: expect_ok(
                client.post(f"/supply/inventory/requisitions/{inventory['id']}/sync"),
                "sync inventory requisition",
            ),
        )
        if inventory["lines"][0]["reserved_qty"] != "5.0000":
            raise JourneyFailure("approved inventory requisition did not reserve stock")
        issue_key = key()
        issue_payload = {
            "lines": [{"line_id": inventory["lines"][0]["id"], "quantity": "3"}]
        }
        issued = stage(
            "post_partial_inventory_issue",
            lambda: expect_ok(
                client.post(
                    f"/supply/inventory/requisitions/{inventory['id']}/issue",
                    headers={"Idempotency-Key": issue_key},
                    json=issue_payload,
                ),
                "issue stock",
            ),
        )
        issue_replay = stage(
            "inventory_issue_idempotent_replay",
            lambda: expect_ok(
                client.post(
                    f"/supply/inventory/requisitions/{inventory['id']}/issue",
                    headers={"Idempotency-Key": issue_key},
                    json=issue_payload,
                ),
                "issue replay",
            ),
        )
        if issue_replay["id"] != issued["id"]:
            raise JourneyFailure("inventory issue replay changed the requisition")
        stage(
            "return_issued_stock",
            lambda: expect_ok(
                client.post(
                    f"/supply/inventory/requisitions/{inventory['id']}/return",
                    headers={"Idempotency-Key": key()},
                    json={"line_id": inventory["lines"][0]["id"], "quantity": "1"},
                ),
                "return stock",
            ),
        )
        balances = expect_ok(
            client.get(
                f"/supply/inventory/balances?park_id={park['id']}&warehouse_id={warehouse['id']}"
            ),
            "post-return balances",
        )
        stocktake = stage(
            "create_zero_variance_stocktake",
            lambda: expect_ok(
                client.post(
                    "/supply/inventory/stocktakes",
                    headers={"Idempotency-Key": key()},
                    json={
                        "warehouse_id": warehouse["id"],
                        "lines": [
                            {
                                "material_id": material["id"],
                                "counted_qty": balances[0]["on_hand_qty"],
                            }
                        ],
                    },
                ),
                "create stocktake",
            ),
        )
        stocktake = stage(
            "submit_zero_variance_stocktake",
            lambda: expect_ok(
                client.post(
                    f"/supply/inventory/stocktakes/{stocktake['id']}/submit",
                    headers={"Idempotency-Key": key()},
                    json={
                        "expected_version": stocktake["lock_version"],
                        "definition_code": procurement_definition,
                    },
                ),
                "submit stocktake",
            ),
        )
        stage(
            "post_zero_variance_stocktake",
            lambda: expect_ok(
                client.post(
                    f"/supply/inventory/stocktakes/{stocktake['id']}/post",
                    headers={"Idempotency-Key": key()},
                ),
                "post stocktake",
            ),
        )

        outsourcing_definition = stage(
            "publish_outsourcing_approval_definition",
            lambda: approval_definition("OUTSOURCING_ORDER"),
        )
        outsourcing = stage(
            "create_outsourcing_order",
            lambda: expect_ok(
                client.post(
                    "/supply/outsourcing/orders",
                    headers={"Idempotency-Key": key()},
                    json={
                        "park_id": park["id"],
                        "supplier_id": supplier["id"],
                        "title": f"HTTP 防水外包 {suffix}",
                        "deliverables": [
                            {"code": "REPORT", "name": "完工报告", "required": True}
                        ],
                        "sla_due_at": (now + timedelta(days=7)).isoformat(),
                        "amount": "3000.00",
                        "required_qualification": "SERVICE_LICENSE",
                    },
                ),
                "create outsourcing order",
            ),
        )
        outsourcing = stage(
            "submit_outsourcing_for_native_approval",
            lambda: expect_ok(
                client.post(
                    f"/supply/outsourcing/orders/{outsourcing['id']}/submit",
                    headers={"Idempotency-Key": key()},
                    json={
                        "expected_version": outsourcing["lock_version"],
                        "definition_code": outsourcing_definition,
                        "required_qualification": "SERVICE_LICENSE",
                    },
                ),
                "submit outsourcing",
            ),
        )
        stage("approve_outsourcing_order", lambda: approve(outsourcing["approval_id"]))
        outsourcing = stage(
            "sync_approved_outsourcing",
            lambda: expect_ok(
                client.post(f"/supply/outsourcing/orders/{outsourcing['id']}/sync"),
                "sync outsourcing",
            ),
        )

        def event(event_type: str, evidence: list[dict[str, Any]] | None = None) -> Any:
            return expect_ok(
                client.post(
                    f"/supply/outsourcing/orders/{outsourcing['id']}/events",
                    headers={"Idempotency-Key": key()},
                    json={
                        "event_type": event_type,
                        "note": "HTTP 履约证据",
                        "evidence": evidence,
                    },
                ),
                f"outsourcing {event_type}",
            )

        stage("start_outsourcing", lambda: event("STARTED"))
        stage(
            "complete_outsourcing_with_evidence",
            lambda: event(
                "COMPLETED",
                [{"type": "REPORT", "reference": f"attachment://synthetic/{suffix}/1"}],
            ),
        )
        rework = stage(
            "reject_outsourcing_to_rework",
            lambda: expect_ok(
                client.post(
                    f"/supply/outsourcing/orders/{outsourcing['id']}/acceptance",
                    headers={"Idempotency-Key": key()},
                    json={"accepted": False, "reason": "收边不符合验收要求"},
                ),
                "reject outsourcing",
            ),
        )
        if rework["status"] != "REWORK":
            raise JourneyFailure("outsourcing did not enter REWORK")
        stage("restart_outsourcing_rework", lambda: event("STARTED"))
        stage(
            "recomplete_outsourcing_with_evidence",
            lambda: event(
                "COMPLETED",
                [{"type": "REPORT", "reference": f"attachment://synthetic/{suffix}/2"}],
            ),
        )
        accepted = stage(
            "accept_outsourcing_and_evaluate_supplier",
            lambda: expect_ok(
                client.post(
                    f"/supply/outsourcing/orders/{outsourcing['id']}/acceptance",
                    headers={"Idempotency-Key": key()},
                    json={"accepted": True, "score": 5, "comment": "返工后验收通过"},
                ),
                "accept outsourcing",
            ),
        )
        if (
            accepted["status"] != "ACCEPTED"
            or accepted["settlement_state"] != "NOT_INTEGRATED"
        ):
            raise JourneyFailure(
                "outsourcing acceptance or settlement truth is incorrect"
            )

        strict_response = stage(
            "reject_unknown_contract_field",
            lambda: client.post(
                "/supply/materials",
                json={
                    "code": f"MAT_STRICT_{suffix}",
                    "name": "严格契约物料",
                    "category": "验收",
                    "unit": "件",
                    "unexpected": True,
                },
            ),
        )
        if strict_response.status_code != 422:
            raise JourneyFailure(
                f"unknown field expected 422, got {strict_response.status_code}"
            )
        overview = stage(
            "verify_external_and_migration_truth",
            lambda: expect_ok(client.get("/supply/overview"), "supply overview"),
        )
        integrations = overview["external_integrations"]
        migration = overview["legacy_data_migration"]
        if (
            any(
                integrations.get(name) != "NOT_CONNECTED"
                for name in ("erp", "wms", "supplier_portal")
            )
            or integrations.get("production_contacted") is not False
        ):
            raise JourneyFailure(f"external integrations overclaimed: {integrations}")
        if migration["status"] != "BLOCKED":
            raise JourneyFailure(f"legacy migration overclaimed: {migration}")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "PASS",
        "base_url": args.base_url,
        "real_http": True,
        "postgresql_expected": True,
        "production_contacted": False,
        "production_authorized": False,
        "tenant_id": me["tenant_id"],
        "park_id": park["id"],
        "stages": stages,
        "stage_count": len(stages),
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "external_integrations": integrations,
        "legacy_data_migration": migration,
        "stock_truth": {
            "received": "10.0000",
            "issued": "3.0000",
            "returned": "1.0000",
            "expected_on_hand": "8.0000",
        },
        "outsourcing_settlement_state": accepted["settlement_state"],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""OpenAPI 3.1 严格校验与 Step1/Party 路由一致性检查。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]  # kwzy-python
OPENAPI_PATH = ROOT / "docs" / "04-api" / "openapi-v1-core.yaml"


def _iter_api_paths(app) -> set[str]:
    """收集运行时 /api/v1 路径（含 include_router 嵌套）。"""
    paths: set[str] = set()

    def walk(routes, prefix: str = "") -> None:
        for route in routes:
            path = getattr(route, "path", None)
            nested = getattr(route, "routes", None)
            if nested is not None and path is None:
                # FastAPI _IncludedRouter
                walk(nested, prefix)
                continue
            if path is None:
                continue
            full = prefix + path if not path.startswith(prefix) else path
            # include_router 挂在 prefix 上时，子路由 path 可能已是完整或相对
            paths.add(full)
            if nested is not None:
                walk(nested, full.rstrip("/"))

    walk(app.routes)
    # 补齐：从 openapi schema 导出更可靠
    schema = app.openapi()
    for path in schema.get("paths") or {}:
        paths.add(path)
    return {
        path
        for path in paths
        if path and ("/api/" in path or path.startswith(("/parties", "/parks", "/auth", "/units")))
    }


def test_openapi_v1_core_is_valid_openapi_31() -> None:
    pytest.importorskip("openapi_spec_validator")
    from openapi_spec_validator import validate
    from openapi_spec_validator.readers import read_from_filename

    assert OPENAPI_PATH.is_file(), f"missing {OPENAPI_PATH}"
    spec, _ = read_from_filename(str(OPENAPI_PATH))
    validate(spec)
    assert str(spec.get("openapi", "")).startswith("3.")


def test_party_schema_has_no_master_park_id_or_address() -> None:
    """契约：Party 主档不得含 park_id 归属字段与模糊 address。"""
    doc = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    schemas = (doc.get("components") or {}).get("schemas") or {}
    party = schemas.get("Party") or {}
    props = party.get("properties") or {}
    assert "park_id" not in props, "Party schema must not have master park_id"
    assert "address" not in props, "Party schema must not have master free-form address"
    create = schemas.get("PartyCreate") or {}
    cprops = create.get("properties") or {}
    assert "park_id" not in cprops
    assert "address" not in cprops
    assert "initial_park_relation" in cprops
    assert "InitialParkRelation" in schemas
    assert "/parties/{party_id}/addresses" in (doc.get("paths") or {})
    assert "/parties/{party_id}/park-relations" in (doc.get("paths") or {})


def test_party_enterprise_openapi_matches_every_runtime_method_and_strict_command() -> None:
    """Enterprise profile routes must be method-exact and reject hidden-field injection."""

    from app.main import create_app

    document = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    paths = document["paths"]
    runtime_paths = create_app().openapi()["paths"]
    expected_methods = {
        "/enterprise-parties": {"get"},
        "/parties/{party_id}/enterprise-profile": {"get", "put"},
        "/parties/{party_id}/enterprise-relationships": {"get", "post"},
        "/parties/{party_id}/enterprise-relationships/{relationship_id}/end": {"post"},
        "/parties/{party_id}/enterprise-credentials": {"get", "post"},
        "/parties/{party_id}/enterprise-credentials/{credential_id}/review": {"post"},
        "/parties/{party_id}/enterprise-credentials/{credential_id}/transition": {"post"},
        "/parties/{party_id}/enterprise-tags": {"get", "post"},
        "/parties/{party_id}/enterprise-tags/{tag_id}/deactivate": {"post"},
        "/parties/{party_id}/enterprise-risk-signals": {"get", "post"},
        "/parties/{party_id}/enterprise-risk-signals/{signal_id}/resolve": {"post"},
    }
    for path, methods in expected_methods.items():
        assert path in paths, path
        assert methods == {
            method.lower()
            for method in paths[path]
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }, path
        runtime_path = "/api/v1" + path
        assert runtime_path in runtime_paths, runtime_path
        assert methods == {
            method.lower()
            for method in runtime_paths[runtime_path]
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }, runtime_path

    schemas = document["components"]["schemas"]
    for command in (
        "EnterpriseProfileSave",
        "EnterpriseRelationshipCreate",
        "EnterpriseVersionReason",
        "EnterpriseCredentialCreate",
        "EnterpriseTagCreate",
        "EnterpriseRiskSignalCreate",
        "EnterpriseRiskResolve",
    ):
        assert schemas[command]["additionalProperties"] is False, command
    credential = schemas["EnterpriseCredentialCreate"]["properties"]
    assert credential["identifier"]["writeOnly"] is True
    assert "identifier_fingerprint" not in credential
    risk_description = paths["/parties/{party_id}/enterprise-risk-signals"]["get"]["description"]
    assert "不是外部信用评分" in risk_description


def test_step1_runtime_paths_covered_by_openapi() -> None:
    """运行时路由应出现在 OpenAPI 契约中。"""
    from app.main import create_app

    assert OPENAPI_PATH.is_file()
    doc = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    paths = set(doc.get("paths") or {})

    app = create_app()
    runtime = _iter_api_paths(app)
    # OpenAPI 可能省略 prefix；同时兼容带/不带 /api/v1
    openapi_with_prefix = set()
    for p in paths:
        openapi_with_prefix.add(p)
        if not p.startswith("/api/"):
            openapi_with_prefix.add("/api/v1" + p if p.startswith("/") else "/api/v1/" + p)
        openapi_with_prefix.add(p.replace("/api/v1", "", 1) if p.startswith("/api/v1") else p)

    required_markers = (
        "/auth/login",
        "/parks",
        "/units",
        "/parties",
        "/leases",
        "/bills",
        "/payments",
        "/work-items",
        "/workbench/summary",
        "/leads",
        "/work-orders",
        "/collection/cases",
        "/system/org-units",
        "/system/params",
        "/approvals",
        "/attachments",
    )
    for marker in required_markers:
        assert any(marker in p for p in paths) or any(marker in p for p in runtime), (
            f"missing coverage for {marker}"
        )

    # 每个 runtime path 的路径模板应能在 openapi 中找到对应资源
    for rp in runtime:
        if rp in {"/api/v1/openapi.json", "/openapi.json"}:
            continue
        bare = rp.replace("/api/v1", "") or "/"
        # path params: {id} vs concrete — use prefix match on resource root
        resource = bare.split("{")[0].rstrip("/")
        if not resource or resource == "/":
            continue
        # skip health and docs
        if resource in {"/health", "/docs", "/redoc"}:
            continue
        found = any(
            resource in op or resource in op.replace("/api/v1", "") for op in openapi_with_prefix
        )
        assert found, f"runtime route {rp} not reflected in OpenAPI ({resource})"


def test_workforce_openapi_matches_every_runtime_method_and_strict_command() -> None:
    """Every workforce route and sensitive command stays contract-controlled."""

    from app.main import create_app

    document = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    paths = document["paths"]
    runtime_paths = create_app().openapi()["paths"]
    expected_methods = {
        "/workforce/overview": {"get"},
        "/workforce/employees": {"get", "post"},
        "/workforce/employees/{employee_id}": {"get", "patch"},
        "/workforce/employees/{employee_id}/status": {"post"},
        "/workforce/shifts": {"get", "post"},
        "/workforce/shifts/{template_id}/versions": {"post"},
        "/workforce/assignments": {"get", "post"},
        "/workforce/assignments/{assignment_id}/cancel": {"post"},
        "/workforce/attendance/policies": {"get", "post"},
        "/workforce/attendance/locations": {"get", "post"},
        "/workforce/attendance/punches": {"post"},
        "/workforce/attendance/summaries": {"get"},
        "/workforce/attendance/summaries/generate": {"post"},
        "/workforce/attendance/summaries/{summary_id}/adjust": {"post"},
        "/workforce/leaves": {"get", "post"},
        "/workforce/leaves/{leave_id}/refresh-approval": {"post"},
        "/workforce/leaves/{leave_id}/cancel": {"post"},
        "/workforce/performance/cycles": {"get", "post"},
        "/workforce/performance/cycles/{cycle_id}/status": {"post"},
        "/workforce/performance/cycles/{cycle_id}/goals": {"get", "post"},
        "/workforce/performance/reviews": {"get", "post"},
        "/workforce/performance/reviews/{review_id}/publish": {"post"},
        "/workforce/performance/reviews/{review_id}/acknowledge": {"post"},
        "/workforce/qualification-types": {"get", "post"},
        "/workforce/qualifications": {"get", "post"},
        "/workforce/qualifications/{qualification_id}/verify": {"post"},
        "/workforce/qualifications/{qualification_id}/revoke": {"post"},
        "/workforce/qualifications/sweep": {"post"},
    }
    for path, methods in expected_methods.items():
        assert path in paths, path
        assert methods == {
            method.lower()
            for method in paths[path]
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }, path
        runtime_path = "/api/v1" + path
        assert runtime_path in runtime_paths, runtime_path
        assert methods == {
            method.lower()
            for method in runtime_paths[runtime_path]
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }, runtime_path

    schemas = document["components"]["schemas"]
    strict_commands = {
        "WorkforceExpectedReason",
        "WorkforceEmployeeCreate",
        "WorkforceEmployeeUpdate",
        "WorkforceEmployeeStatus",
        "WorkforceShiftCreate",
        "WorkforceShiftVersionCreate",
        "WorkforceAssignmentCreate",
        "WorkforcePolicyCreate",
        "WorkforceLocationCreate",
        "WorkforcePunchCreate",
        "WorkforceSummaryGenerate",
        "WorkforceSummaryAdjust",
        "WorkforceLeaveCreate",
        "WorkforcePerformanceCycleCreate",
        "WorkforceCycleStatus",
        "WorkforceGoalCreate",
        "WorkforceReviewCreate",
        "WorkforceReviewAcknowledge",
        "WorkforceQualificationTypeCreate",
        "WorkforceQualificationCreate",
        "WorkforceQualificationSweep",
    }
    assert all(schemas[name]["additionalProperties"] is False for name in strict_commands)
    assert schemas["WorkforceEmployeeCreate"]["properties"]["identity_number"]["writeOnly"]
    assert schemas["WorkforceQualificationCreate"]["properties"]["credential_number"]["writeOnly"]
    assert schemas["WorkforcePunchCreate"]["properties"]["latitude"]["writeOnly"]


def test_supply_openapi_matches_every_runtime_method_and_strict_command() -> None:
    """Supply stock-changing commands remain method-exact, strict and idempotent."""

    from app.main import create_app

    document = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    paths = document["paths"]
    runtime_paths = create_app().openapi()["paths"]
    expected_methods = {
        "/supply/overview": {"get"},
        "/supply/suppliers": {"get", "post"},
        "/supply/suppliers/{supplier_id}": {"get"},
        "/supply/suppliers/{supplier_id}/status": {"post"},
        "/supply/suppliers/{supplier_id}/scopes": {"post"},
        "/supply/suppliers/{supplier_id}/qualifications": {"post"},
        "/supply/suppliers/{supplier_id}/evaluations": {"post"},
        "/supply/materials": {"get", "post"},
        "/supply/warehouses": {"get", "post"},
        "/supply/inventory/balances": {"get"},
        "/supply/inventory/movements": {"get"},
        "/supply/inventory/movements/{movement_id}/reverse": {"post"},
        "/supply/procurement/requisitions": {"get", "post"},
        "/supply/procurement/requisitions/{requisition_id}/draft": {"put"},
        "/supply/procurement/requisitions/{requisition_id}/submit": {"post"},
        "/supply/procurement/requisitions/{requisition_id}/cancel": {"post"},
        "/supply/procurement/requisitions/{requisition_id}/sync": {"post"},
        "/supply/procurement/orders": {"get", "post"},
        "/supply/procurement/orders/{order_id}/acknowledge": {"post"},
        "/supply/procurement/orders/{order_id}/receipts": {"post"},
        "/supply/inventory/requisitions": {"get", "post"},
        "/supply/inventory/requisitions/{requisition_id}/submit": {"post"},
        "/supply/inventory/requisitions/{requisition_id}/sync": {"post"},
        "/supply/inventory/requisitions/{requisition_id}/issue": {"post"},
        "/supply/inventory/requisitions/{requisition_id}/return": {"post"},
        "/supply/inventory/stocktakes": {"get", "post"},
        "/supply/inventory/stocktakes/{stocktake_id}/submit": {"post"},
        "/supply/inventory/stocktakes/{stocktake_id}/post": {"post"},
        "/supply/outsourcing/orders": {"get", "post"},
        "/supply/outsourcing/orders/{order_id}/submit": {"post"},
        "/supply/outsourcing/orders/{order_id}/sync": {"post"},
        "/supply/outsourcing/orders/{order_id}/events": {"post"},
        "/supply/outsourcing/orders/{order_id}/acceptance": {"post"},
    }
    assert len(expected_methods) == 33
    assert sum(len(methods) for methods in expected_methods.values()) == 41
    for path, methods in expected_methods.items():
        assert path in paths, path
        assert methods == {
            method.lower()
            for method in paths[path]
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }, path
        runtime_path = "/api/v1" + path
        assert runtime_path in runtime_paths, runtime_path
        assert methods == {
            method.lower()
            for method in runtime_paths[runtime_path]
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }, runtime_path

    schemas = document["components"]["schemas"]
    strict_commands = {
        "SupplierCreate",
        "SupplierStatus",
        "SupplierScopeCreate",
        "SupplierQualificationCreate",
        "SupplierEvaluationCreate",
        "MaterialCreate",
        "WarehouseCreate",
        "ProcurementCreate",
        "ProcurementDraftUpdate",
        "ApprovalSubmit",
        "SupplyExpectedReason",
        "PurchaseOrderCreate",
        "PurchaseOrderAcknowledge",
        "app__modules__supply__interface__schemas__ReceiptCreate",
        "InventoryRequisitionCreate",
        "InventoryIssue",
        "InventoryReturn",
        "StocktakeCreate",
        "MovementReverse",
        "OutsourcingCreate",
        "OutsourcingSubmit",
        "OutsourcingEventCreate",
        "OutsourcingAcceptance",
    }
    assert all(schemas[name]["additionalProperties"] is False for name in strict_commands)
    assert schemas["SupplierQualificationCreate"]["properties"]["credential_number"]["writeOnly"]
    idempotent_paths = {
        "/supply/inventory/movements/{movement_id}/reverse",
        "/supply/procurement/requisitions",
        "/supply/procurement/requisitions/{requisition_id}/submit",
        "/supply/procurement/requisitions/{requisition_id}/cancel",
        "/supply/procurement/orders",
        "/supply/procurement/orders/{order_id}/receipts",
        "/supply/inventory/requisitions",
        "/supply/inventory/requisitions/{requisition_id}/submit",
        "/supply/inventory/requisitions/{requisition_id}/issue",
        "/supply/inventory/requisitions/{requisition_id}/return",
        "/supply/inventory/stocktakes",
        "/supply/inventory/stocktakes/{stocktake_id}/submit",
        "/supply/inventory/stocktakes/{stocktake_id}/post",
        "/supply/outsourcing/orders",
        "/supply/outsourcing/orders/{order_id}/submit",
        "/supply/outsourcing/orders/{order_id}/events",
        "/supply/outsourcing/orders/{order_id}/acceptance",
    }
    for path in idempotent_paths:
        parameters = paths[path]["post"]["parameters"]
        assert any(
            parameter["in"] == "header"
            and parameter["name"] == "Idempotency-Key"
            and parameter["required"] is True
            for parameter in parameters
        ), path


def test_receivables_openapi_matches_every_runtime_method_and_strict_command() -> None:
    """Every receivables write path is contract-controlled and rejects hidden fields."""

    from app.main import create_app

    document = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    paths = document["paths"]
    runtime_paths = create_app().openapi()["paths"]
    expected_methods = {
        "/billing/runs/preview": {"get"},
        "/billing/runs": {"post"},
        "/receipts/capabilities": {"get"},
        "/receipts": {"get", "post"},
        "/receipts/import": {"post"},
        "/receipts/{receipt_id}": {"get"},
        "/receipts/{receipt_id}/match": {"post"},
        "/receipts/{receipt_id}/confirm": {"post"},
        "/receipts/{receipt_id}/exception": {"post"},
        "/receipts/{receipt_id}/dispute": {"post"},
        "/receipts/{receipt_id}/dispute/resolve": {"post"},
        "/payments/{payment_id}/allocations": {"post"},
        "/collection/runs/preview": {"get"},
        "/collection/runs": {"post"},
        "/receivable-adjustments": {"get", "post"},
        "/receivable-adjustments/{adjustment_id}/apply": {"post"},
    }
    for path, methods in expected_methods.items():
        assert path in paths, path
        assert methods == {
            method.lower()
            for method in paths[path]
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }, path
        runtime_path = "/api/v1" + path
        assert runtime_path in runtime_paths, runtime_path
        assert methods == {
            method.lower()
            for method in runtime_paths[runtime_path]
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }, runtime_path

    schemas = document["components"]["schemas"]
    for command in (
        "ReceiptCreate",
        "ReceivableVersionCommand",
        "ReceiptConfirm",
        "ReceiptException",
        "ReceiptDispute",
        "ReceiptDisputeDecision",
        "PaymentAllocate",
        "DunningRunCommand",
        "ReceivableAdjustmentCreate",
        "CollectionCaseCreate",
        "CollectionCaseUpdate",
        "CollectionRecordCreate",
    ):
        assert schemas[command]["additionalProperties"] is False, command
    assert schemas["ReceiptCreate"]["properties"]["payer_account"]["writeOnly"] is True


def test_asset_portfolio_openapi_matches_every_runtime_method() -> None:
    """Asset-template lifecycle and every rent-control projection stay contract controlled."""

    from app.main import create_app

    document = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    paths = document["paths"]
    runtime_paths = create_app().openapi()["paths"]
    expected_methods = {
        "/asset-templates": {"get", "post"},
        "/asset-templates/{template_id}": {"get"},
        "/asset-templates/{template_id}/draft": {"put"},
        "/asset-templates/{template_id}/publish": {"post"},
        "/asset-templates/{template_id}/drafts": {"post"},
        "/asset-templates/{template_id}/retire": {"post"},
        "/rent-control/summary": {"get"},
        "/rent-control/units": {"get"},
        "/rent-control/matrix": {"get"},
        "/rent-control/map": {"get"},
        "/rent-control/vacancies": {"get"},
        "/rent-control/expiries": {"get"},
        "/rent-control/analysis": {"get"},
        "/rent-control/units/{unit_id}": {"get"},
    }
    for path, methods in expected_methods.items():
        assert path in paths, path
        assert methods == {
            key.lower()
            for key in paths[path]
            if key.lower() in {"get", "post", "put", "patch", "delete"}
        }, path
        runtime_path = "/api/v1" + path
        assert runtime_path in runtime_paths, runtime_path
        assert methods == {
            key.lower()
            for key in runtime_paths[runtime_path]
            if key.lower() in {"get", "post", "put", "patch", "delete"}
        }, runtime_path

    schemas = document["components"]["schemas"]
    for name in (
        "AssetTemplateField",
        "AssetTemplateCreate",
        "AssetTemplateDraftUpdate",
        "ExpectedVersionCommand",
        "GeoJsonGeometry",
    ):
        assert name in schemas, name
    assert schemas["AssetTemplateCreate"]["additionalProperties"] is False
    assert schemas["AssetTemplateDraftUpdate"]["required"] == ["expected_version"]
    assert schemas["GeoJsonGeometry"]["additionalProperties"] is False


def test_approval_audit_center_openapi_matches_runtime_methods_and_schemas() -> None:
    """Approval/audit routes are controlled method-by-method, not merely by resource prefix."""

    from app.main import create_app

    document = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    expected_methods = {
        "/approvals": {"get", "post"},
        "/approvals/{approval_id}": {"get"},
        "/approvals/{approval_id}/approve": {"post"},
        "/approvals/{approval_id}/reject": {"post"},
        "/approvals/{approval_id}/withdraw": {"post"},
        "/approvals/{approval_id}/resubmit": {"post"},
        "/approvals/{approval_id}/history": {"get"},
        "/approval-definitions": {"get", "post"},
        "/approval-definitions/{definition_id}": {"get", "patch"},
        "/approval-definitions/{definition_id}/draft": {"post"},
        "/approval-definitions/{definition_id}/publish": {"post"},
        "/approval-definitions/{definition_id}/retire": {"post"},
        "/approval-tasks": {"get"},
        "/approval-tasks/{task_id}/decide": {"post"},
        "/approval-tasks/sweep-overdue": {"post"},
        "/approval-delegations": {"get", "post"},
        "/approval-delegations/{delegation_id}/revoke": {"post"},
        "/audit-logs": {"get"},
        "/audit-logs/verify": {"get"},
        "/audit-logs/export": {"get"},
        "/audit-logs/{audit_id}": {"get"},
    }
    runtime_paths = create_app().openapi()["paths"]
    controlled_paths = document["paths"]
    for path, methods in expected_methods.items():
        assert path in controlled_paths, path
        assert methods == {
            method.lower()
            for method in controlled_paths[path]
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }, path
        runtime_path = "/api/v1" + path
        assert runtime_path in runtime_paths, runtime_path
        assert methods == {
            method.lower()
            for method in runtime_paths[runtime_path]
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }, runtime_path

    schemas = document["components"]["schemas"]
    for name in (
        "ApprovalCreate",
        "ApprovalTaskDecision",
        "ApprovalDefinitionCreate",
        "ApprovalDefinitionUpdate",
        "ApprovalDelegationCreate",
        "ApprovalInstance",
        "ApprovalTask",
        "AuditLogEvidence",
        "AuditIntegrityState",
    ):
        assert name in schemas, name
    assert schemas["ApprovalCreate"]["additionalProperties"] is False
    assert schemas["ApprovalTaskDecision"]["additionalProperties"] is False
    approval_query_names = {
        parameter.get("name")
        for parameter in controlled_paths["/approvals"]["get"]["parameters"]
        if isinstance(parameter, dict) and "name" in parameter
    }
    assert {
        "park_id",
        "status",
        "biz_type",
        "priority",
        "mine",
        "created_from",
        "created_to",
    } <= approval_query_names
    assert set(schemas["AuditIntegrityState"]["enum"]) == {
        "VERIFIED",
        "FAILED",
        "LEGACY_UNVERIFIED",
    }


def test_investment_crm_v2_openapi_matches_runtime_and_legacy_stage_mapping() -> None:
    """CRM V2 contract enumerates every route and makes FOLLOWING compatibility explicit."""
    from app.main import create_app

    document = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    paths = document["paths"]
    expected_methods = {
        "/leads": {"get", "post"},
        "/leads/duplicates/check": {"post"},
        "/crm/assignees": {"get"},
        "/crm/assignment-rules": {"get", "post"},
        "/crm/assignment-rules/preview": {"get"},
        "/crm/assignment-rules/{rule_id}": {"get"},
        "/crm/assignment-rules/{rule_id}/draft": {"patch", "post"},
        "/crm/assignment-rules/{rule_id}/publish": {"post"},
        "/crm/assignment-rules/{rule_id}/retire": {"post"},
        "/crm/viewings/{viewing_id}": {"get", "patch"},
        "/crm/viewings/{viewing_id}/transition": {"post"},
        "/crm/intents/{intent_id}": {"get"},
        "/crm/intents/{intent_id}/versions": {"post"},
        "/crm/intents/{intent_id}/submit": {"post"},
        "/crm/channels": {"get", "post"},
        "/crm/channels/{channel_id}": {"get", "patch"},
        "/crm/channels/{channel_id}/events": {"get"},
        "/crm/channels/{channel_id}/events/{event_id}/replay": {"post"},
        "/public/lead-channels/{public_id}/events": {"post"},
        "/crm/unit-locks/sweep": {"post"},
        "/crm/summary": {"get"},
        "/crm/board": {"get"},
        "/leads/{lead_id}": {"get", "patch"},
        "/leads/{lead_id}/activities": {"post"},
        "/leads/{lead_id}/viewings": {"get", "post"},
        "/leads/{lead_id}/intent": {"get", "post"},
        "/leads/{lead_id}/assign": {"post"},
        "/leads/{lead_id}/claim": {"post"},
        "/leads/{lead_id}/release": {"post"},
        "/leads/{lead_id}/recycle": {"post"},
        "/leads/{lead_id}/reopen": {"post"},
        "/leads/{lead_id}/merge": {"post"},
        "/leads/{lead_id}/unit-matches": {"get"},
        "/leads/{lead_id}/unit-locks": {"post"},
        "/leads/{lead_id}/unit-locks/{lock_id}/release": {"post"},
        "/leads/{lead_id}/unit-locks/{lock_id}/renew": {"post"},
        "/leads/{lead_id}/lose": {"post"},
        "/leads/{lead_id}/convert": {"post"},
    }
    runtime_paths = create_app().openapi()["paths"]
    for path, methods in expected_methods.items():
        assert path in paths, f"CRM path absent from controlled YAML: {path}"
        assert methods <= {key.lower() for key in paths[path]}, path
        runtime_path = "/api/v1" + path
        assert runtime_path in runtime_paths, f"CRM path absent at runtime: {runtime_path}"
        assert methods <= {key.lower() for key in runtime_paths[runtime_path]}, path

    schemas = document["components"]["schemas"]
    current_stages = set(schemas["LeadStage"]["enum"])
    accepted_filters = set(schemas["LeadStageFilter"]["enum"])
    assert "FOLLOWING" not in current_stages
    assert "CONTACTING" in current_stages
    assert "FOLLOWING" in accepted_filters
    assert schemas["LeadStageFilter"]["x-legacy-value-mapping"] == {"FOLLOWING": "CONTACTING"}
    for command in (
        "LeadUpdate",
        "LeadActivityCreate",
        "LeadAssign",
        "LeadVersionCommand",
        "LeadLose",
        "LeadReopen",
        "LeadMerge",
        "LeadUnitLockCreate",
        "LeadUnitLockCommand",
        "LeadConvert",
    ):
        assert "expected_version" in schemas[command]["required"], command


def test_contract_lifecycle_v2_openapi_matches_every_runtime_method() -> None:
    from app.main import create_app

    document = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    paths = document["paths"]
    runtime_paths = create_app().openapi()["paths"]
    expected_methods = {
        "/leases/summary": {"get"},
        "/leases/selectors": {"get"},
        "/parties/{party_id}/lease-profile": {"get"},
        "/leases/{contract_id}/lifecycle": {"get"},
        "/leases/{contract_id}/schedule-preview": {"post"},
        "/leases/{contract_id}/charges": {"put"},
        "/leases/{contract_id}/lifecycle/submit": {"post"},
        "/leases/{contract_id}/lifecycle/approve": {"post"},
        "/leases/{contract_id}/lifecycle/reject": {"post"},
        "/leases/{contract_id}/lifecycle/withdraw": {"post"},
        "/leases/{contract_id}/lifecycle/activate": {"post"},
        "/leases/{contract_id}/documents": {"post"},
        "/leases/{contract_id}/documents/{document_id}/approve": {"post"},
        "/leases/{contract_id}/documents/{document_id}/sign": {"post"},
        "/leases/{contract_id}/changes": {"post"},
        "/lease-changes/{change_id}": {"put"},
        "/lease-changes/apply-due": {"post"},
        "/lease-changes/{change_id}/submit": {"post"},
        "/lease-changes/{change_id}/approve": {"post"},
        "/lease-changes/{change_id}/reject": {"post"},
        "/lease-changes/{change_id}/withdraw": {"post"},
        "/lease-changes/{change_id}/cancel": {"post"},
        "/lease-changes/{change_id}/apply": {"post"},
        "/leases/{contract_id}/exit-settlements": {"post"},
        "/lease-exit-settlements/{settlement_id}": {"put"},
        "/lease-exit-settlements/{settlement_id}/submit": {"post"},
        "/lease-exit-settlements/{settlement_id}/approve": {"post"},
        "/lease-exit-settlements/{settlement_id}/reject": {"post"},
        "/lease-exit-settlements/{settlement_id}/withdraw": {"post"},
        "/lease-exit-settlements/{settlement_id}/clearance": {"post"},
        "/lease-exit-settlements/{settlement_id}/close": {"post"},
    }
    for path, methods in expected_methods.items():
        assert path in paths, f"contract V2 path absent from controlled YAML: {path}"
        assert methods <= {key.lower() for key in paths[path]}, path
        runtime_path = "/api/v1" + path
        assert runtime_path in runtime_paths, f"contract V2 path absent at runtime: {runtime_path}"
        assert methods <= {key.lower() for key in runtime_paths[runtime_path]}, path

    schemas = document["components"]["schemas"]
    for command in (
        "LeaseVersionCommandV2",
        "LeaseApprovalCommandV2",
        "LeaseChargeReplaceV2",
        "LeaseSchedulePreviewV2",
        "LeaseDocumentCreateV2",
        "LeaseDocumentCommandV2",
        "LeaseChangeCreateV2",
        "LeaseChangeDecisionV2",
        "LeaseChangeApplyV2",
        "LeaseExitCreateV2",
        "LeaseExitEditV2",
        "LeaseExitSubmitV2",
        "LeaseExitDecisionV2",
        "LeaseExitClearanceV2",
        "LeaseExitCloseV2",
    ):
        required = set(schemas[command].get("required") or [])
        if command == "LeaseApprovalCommandV2":
            required = set(schemas[command]["allOf"][1]["required"])
            assert "approval_id" in required
        else:
            assert "expected_version" in required, command
    assert "idempotency_key" in schemas["LeaseChangeApplyV2"]["required"]
    assert "idempotency_key" in schemas["LeaseExitCloseV2"]["required"]
    charge = schemas["LeaseChargeLineV2"]["properties"]
    assert set(charge["calculation_method"]["enum"]) == {"FIXED", "PER_AREA"}
    assert set(charge["billing_cycle"]["enum"]) == {
        "MONTHLY",
        "QUARTERLY",
        "SEMI_ANNUAL",
        "ANNUAL",
        "ONE_TIME",
    }


def test_lease_compatibility_contract_cannot_bypass_v2_governance() -> None:
    """The controlled contract must expose the same fail-closed legacy semantics as runtime."""
    from app.main import create_app

    document = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    paths = document["paths"]
    runtime_paths = create_app().openapi()["paths"]
    versioned_aliases = {
        "/leases/{lease_id}/submit": "LeaseVersionCommandV2",
        "/leases/{lease_id}/reject": "LeaseApprovalCommandV2",
        "/leases/{lease_id}/cancel": "LeaseVersionCommandV2",
        "/leases/{lease_id}/activate": "LeaseVersionCommandV2",
    }
    for path, schema_name in versioned_aliases.items():
        operation = paths[path]["post"]
        schema = operation["requestBody"]["content"]["application/json"]["schema"]
        assert schema["$ref"] == f"#/components/schemas/{schema_name}"
        runtime_path = "/api/v1" + path.replace("{lease_id}", "{contract_id}")
        runtime_operation = runtime_paths[runtime_path]["post"]
        assert runtime_operation["requestBody"]["required"] is True

    for path in ("/leases/{lease_id}/terminate", "/leases/{lease_id}/breach"):
        responses = paths[path]["post"]["responses"]
        assert "409" in responses
        assert "200" not in responses

    list_parameters = {
        item["name"] for item in paths["/leases"]["get"]["parameters"] if "name" in item
    }
    assert {"approval_status", "change_status", "exit_status"} <= list_parameters

    schemas = document["components"]["schemas"]
    create_properties = schemas["LeaseCreate"]["properties"]
    update_schema = schemas["LeaseUpdate"]
    assert "charges" in create_properties
    assert "increase_date" not in create_properties
    assert "increase_rate" not in create_properties
    assert "expected_version" in update_schema["required"]
    assert "charges" in update_schema["properties"]


def test_organization_governance_openapi_matches_every_runtime_method() -> None:
    """Controlled YAML and mounted FastAPI routes must expose the same vertical slice."""

    from app.main import create_app

    document = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    paths = document["paths"]
    runtime_paths = create_app().openapi()["paths"]
    expected_methods = {
        "/system/organization-governance/hierarchy": {"get"},
        "/system/organization-governance/groups": {"post"},
        "/system/organization-governance/groups/{group_id}": {"patch"},
        "/system/organization-governance/regions": {"post"},
        "/system/organization-governance/regions/{region_id}": {"patch"},
        "/system/organization-governance/park-assignments": {"post"},
        "/system/organization-governance/parks/{park_id}/assignment-history": {"get"},
        "/system/organization-governance/positions": {"get", "post"},
        "/system/organization-governance/positions/{position_id}": {"patch"},
        "/system/organization-governance/user-assignments": {"get", "post"},
        "/system/organization-governance/user-assignments/{assignment_id}/end": {"post"},
        "/system/organization-governance/protected-fields": {"get"},
        "/system/organization-governance/field-policies": {"get", "put"},
    }
    for path, methods in expected_methods.items():
        assert path in paths, f"organization-governance path absent from YAML: {path}"
        assert methods <= {key.lower() for key in paths[path]}, path
        runtime_path = "/api/v1" + path
        assert runtime_path in runtime_paths, f"runtime route absent: {runtime_path}"
        assert methods <= {key.lower() for key in runtime_paths[runtime_path]}, path

    schemas = document["components"]["schemas"]
    assert set(schemas["FieldAccessPolicyUpsert"]["properties"]["access_mode"]["enum"]) == {
        "VISIBLE",
        "MASKED",
        "HIDDEN",
    }
    assert schemas["FieldAccessPolicyUpsert"]["properties"]["resource_type"]["enum"] == ["USER"]
    assert schemas["FieldAccessPolicyUpsert"]["properties"]["field_name"]["enum"] == ["phone"]
    assert {"region_id", "park_id"} <= set(schemas["RegionParkAssignmentCommand"]["required"])
    assert {"user_id", "position_id"} <= set(schemas["UserPositionAssignmentCreate"]["required"])


def test_workbench_automation_openapi_matches_every_runtime_method() -> None:
    """The controlled contract exposes the complete workbench automation surface."""

    from app.main import create_app

    document = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    paths = document["paths"]
    runtime_paths = create_app().openapi()["paths"]
    expected_methods = {
        "/business-events": {"get", "post"},
        "/business-events/dispatch": {"post"},
        "/event-consumers/{consumer_id}/replay": {"post"},
        "/automation-rules": {"get", "post"},
        "/automation-rules/{rule_id}/draft": {"put", "post"},
        "/automation-rules/{rule_id}/publish": {"post"},
        "/automation-rules/{rule_id}/retire": {"post"},
        "/automation-executions": {"get"},
        "/notifications": {"get"},
        "/notifications/bulk-read": {"post"},
        "/notifications/{notification_id}/read": {"post"},
        "/notifications/{notification_id}/archive": {"post"},
        "/scheduler/definitions": {"get", "post"},
        "/scheduler/definitions/{schedule_id}": {"put"},
        "/scheduler/definitions/{schedule_id}/run": {"post"},
        "/scheduler/poll": {"post"},
        "/scheduler/recover": {"post"},
        "/scheduler/runs": {"get"},
        "/workbench/layout": {"get", "put", "delete"},
        "/workbench/layout/roles": {"get"},
        "/workbench/layout/roles/{role_id}": {"get", "put"},
        "/work-items/{work_item_id}/reassign": {"post"},
    }
    for path, methods in expected_methods.items():
        assert path in paths, path
        assert methods == {
            method.lower()
            for method in paths[path]
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }, path
        runtime_path = "/api/v1" + path
        assert runtime_path in runtime_paths, runtime_path
        assert methods == {
            method.lower()
            for method in runtime_paths[runtime_path]
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }, runtime_path

    schemas = document["components"]["schemas"]
    for command in (
        "BusinessEventEmit",
        "ReplayRequest",
        "RuleCreate",
        "RuleDraftUpdate",
        "WorkbenchVersionCommand",
        "NotificationBulkRead",
        "ScheduleCreate",
        "ScheduleUpdate",
        "ScheduleRunRequest",
        "LayoutWidget",
        "LayoutSave",
        "RoleLayoutSave",
        "WorkItemTransition",
        "WorkItemReassign",
    ):
        assert command in schemas, command
    assert "expected_version" in schemas["WorkbenchVersionCommand"]["required"]
    assert "expected_version" in schemas["WorkItemTransition"]["required"]
    assert schemas["NotificationBulkRead"]["properties"]["ids"]["maxItems"] == 100


def test_tenant_service_openapi_matches_every_runtime_method() -> None:
    """Controlled YAML and mounted FastAPI expose the same complete service lifecycle."""

    from app.main import create_app

    document = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    paths = document["paths"]
    runtime_paths = create_app().openapi()["paths"]
    expected_methods = {
        "/work-order-assignment-rules": {"get", "post"},
        "/work-order-assignment-rules/{rule_id}/publish": {"post"},
        "/work-order-assignment-rules/{rule_id}/retire": {"post"},
        "/work-orders/sla/sweep": {"post"},
        "/work-orders": {"get", "post"},
        "/work-orders/{work_order_id}": {"get"},
        "/work-orders/{work_order_id}/dispatch": {"post"},
        "/work-orders/{work_order_id}/start": {"post"},
        "/work-orders/{work_order_id}/quotes": {"post"},
        "/work-orders/{work_order_id}/quotes/{quote_id}/submit": {"post"},
        "/work-orders/{work_order_id}/cost-entries": {"post"},
        "/work-orders/{work_order_id}/cost-entries/{cost_id}/reverse": {"post"},
        "/work-orders/{work_order_id}/complete": {"post"},
        "/work-orders/{work_order_id}/cancel": {"post"},
        "/tenant-service/principals": {"get", "post"},
        "/tenant-service/principals/{principal_id}/disable": {"post"},
        "/tenant-service/requests": {"get", "post"},
        "/tenant-service/requests/{work_order_id}": {"get"},
        "/tenant-service/requests/{work_order_id}/quotes/{quote_id}/decision": {"post"},
        "/tenant-service/requests/{work_order_id}/acceptance": {"post"},
        "/tenant-service/requests/{work_order_id}/rating": {"post"},
    }
    assert sum(len(methods) for methods in expected_methods.values()) == 25
    for path, methods in expected_methods.items():
        assert path in paths, path
        assert methods == {
            method.lower()
            for method in paths[path]
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }, path
        runtime_path = "/api/v1" + path
        assert runtime_path in runtime_paths, runtime_path
        assert methods == {
            method.lower()
            for method in runtime_paths[runtime_path]
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }, runtime_path

    schemas = document["components"]["schemas"]
    for command in (
        "WorkOrderCreate",
        "TenantServiceRequestCreate",
        "TenantServicePrincipalGrant",
        "WorkOrderAssignmentRuleCreate",
        "WorkOrderAssignmentRuleRetire",
        "WorkOrderExpectedVersion",
        "WorkOrderDispatch",
        "WorkOrderCancel",
        "WorkOrderQuoteCreate",
        "WorkOrderQuoteDecision",
        "WorkOrderCostCreate",
        "WorkOrderCostReverse",
        "WorkOrderCompletion",
        "WorkOrderAcceptance",
        "WorkOrderRating",
        "WorkOrderSlaSweep",
    ):
        assert schemas[command]["additionalProperties"] is False, command
    assert schemas["WorkOrderAssignmentRuleRetire"]["required"] == ["reason"]


def test_records_signature_seal_openapi_matches_every_runtime_method() -> None:
    from app.main import create_app

    document = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    paths = document["paths"]
    runtime_paths = create_app().openapi()["paths"]
    expected_methods = {
        "/record-categories": {"get", "post"},
        "/record-categories/{category_id}": {"patch"},
        "/record-categories/{category_id}/retire": {"post"},
        "/records": {"get", "post"},
        "/records/{record_id}": {"get"},
        "/records/{record_id}/revisions": {"post"},
        "/records/{record_id}/file": {"post"},
        "/records/{record_id}/verify": {"post"},
        "/records/{record_id}/holds": {"post"},
        "/records/{record_id}/holds/{hold_id}/release": {"post"},
        "/records/{record_id}/access-requests": {"post"},
        "/record-access-requests": {"get"},
        "/record-access-requests/{request_id}/refresh-approval": {"post"},
        "/record-access-requests/{request_id}/checkout": {"post"},
        "/record-access-requests/{request_id}/return": {"post"},
        "/records/{record_id}/dispositions": {"post"},
        "/record-dispositions": {"get"},
        "/record-dispositions/{disposition_id}/refresh-approval": {"post"},
        "/record-dispositions/{disposition_id}/confirm": {"post"},
        "/seals": {"get", "post"},
        "/seals/{seal_id}": {"get"},
        "/seals/{seal_id}/transfer": {"post"},
        "/seals/{seal_id}/accept-transfer": {"post"},
        "/seals/{seal_id}/mark-lost": {"post"},
        "/seals/{seal_id}/recover": {"post"},
        "/seals/{seal_id}/retire": {"post"},
        "/seal-use-applications": {"get", "post"},
        "/seal-use-applications/{application_id}/refresh-approval": {"post"},
        "/seal-use-applications/{application_id}/execute": {"post"},
        "/signature-providers": {"get", "post"},
        "/signature-envelopes": {"get", "post"},
        "/signature-envelopes/{envelope_id}": {"get"},
        "/signature-envelopes/{envelope_id}/dispatch": {"post"},
    }
    for path, methods in expected_methods.items():
        assert path in paths, f"records/seal path absent from controlled YAML: {path}"
        assert methods <= {key.lower() for key in paths[path]}, path
        runtime_path = "/api/v1" + path
        assert runtime_path in runtime_paths, f"records/seal path absent at runtime: {runtime_path}"
        assert methods <= {key.lower() for key in runtime_paths[runtime_path]}, path

    schemas = document["components"]["schemas"]
    for command in (
        "RecordsExpectedReason",
        "RecordCategoryUpdate",
        "RecordRevisionCreate",
        "RecordDispositionCreate",
        "SealTransfer",
        "SealUseExecute",
    ):
        assert "expected_version" in schemas[command]["required"], command
    for path in (
        "/records/{record_id}/verify",
        "/records/{record_id}/access-requests",
        "/records/{record_id}/dispositions",
        "/seal-use-applications",
        "/seal-use-applications/{application_id}/execute",
    ):
        parameters = paths[path]["post"]["parameters"]
        assert any(
            parameter["in"] == "header"
            and parameter["name"] == "Idempotency-Key"
            and parameter["required"] is True
            for parameter in parameters
        ), path


def test_facility_management_openapi_matches_every_runtime_method() -> None:
    """Facility devices, inspections and IoT alarms stay method-exact and strict."""

    from app.main import create_app

    document = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    paths = document["paths"]
    runtime_paths = create_app().openapi()["paths"]
    expected_methods = {
        "/facility-devices": {"get", "post"},
        "/facility-devices/{device_id}": {"get", "put"},
        "/facility-devices/{device_id}/retire": {"post"},
        "/inspection-templates": {"get", "post"},
        "/inspection-templates/{template_id}/versions": {"post"},
        "/inspection-template-versions/{version_id}/publish": {"post"},
        "/inspection-schedules": {"get", "post"},
        "/inspection-schedules/{schedule_id}/retire": {"post"},
        "/inspection-schedules/{schedule_id}/pause": {"post"},
        "/inspection-schedules/{schedule_id}/resume": {"post"},
        "/inspection-tasks/generate": {"post"},
        "/inspection-tasks/sweep-missed": {"post"},
        "/inspection-tasks": {"get"},
        "/inspection-tasks/{task_id}": {"get"},
        "/inspection-tasks/{task_id}/start": {"post"},
        "/inspection-tasks/{task_id}/reassign": {"post"},
        "/inspection-tasks/{task_id}/submit": {"post"},
        "/inspection-exceptions/{exception_id}/promote": {"post"},
        "/iot-providers": {"get", "post"},
        "/iot-device-bindings": {"get", "post"},
        "/iot-device-bindings/{binding_id}/retire": {"post"},
        "/iot-alarm-events/ingest": {"post"},
        "/iot-alarms/sweep-escalations": {"post"},
        "/iot-alarms": {"get"},
        "/iot-alarms/{alarm_id}": {"get"},
        "/iot-alarms/{alarm_id}/{target}": {"post"},
    }
    assert sum(len(methods) for methods in expected_methods.values()) == 32
    for path, methods in expected_methods.items():
        assert path in paths, path
        assert methods == {
            method.lower()
            for method in paths[path]
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }, path
        runtime_path = "/api/v1" + path
        assert runtime_path in runtime_paths, runtime_path
        assert methods == {
            method.lower()
            for method in runtime_paths[runtime_path]
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }, runtime_path

    schemas = document["components"]["schemas"]
    for command in (
        "FacilityDeviceCreate",
        "FacilityDeviceUpdate",
        "FacilityExpectedVersion",
        "FacilityExpectedReason",
        "FacilityReason",
        "InspectionTemplateItemV2",
        "InspectionTemplateCreateV2",
        "InspectionTemplateVersionCreateV2",
        "InspectionScheduleCreate",
        "FacilitySweepRequest",
        "InspectionReassign",
        "InspectionResultInput",
        "InspectionSubmit",
        "IoTProviderCreateV2",
        "IoTBindingCreate",
        "IoTAlarmIngestV2",
        "IoTAlarmTransition",
    ):
        assert schemas[command]["additionalProperties"] is False, command
    assert schemas["IoTProviderCreateV2"]["properties"]["adapter_kind"]["enum"] == [
        "LOCAL",
        "SANDBOX",
        "HTTP",
    ]

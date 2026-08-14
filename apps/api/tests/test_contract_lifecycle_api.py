"""Lease V2 governed submit/document/activation API matrix."""

from __future__ import annotations

import base64
import hashlib
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.infrastructure.database.models.billing import Bill
from app.infrastructure.database.models.lease import (
    LeaseContract,
    LeaseContractVersion,
    LeaseExitSettlement,
)
from app.infrastructure.database.models.park_property import Unit


def _headers(
    *,
    permissions: list[str],
    uid: int = 1,
    tenant_id: int = 1,
    park_scope_mode: str = "ALL",
    park_ids: list[int] | None = None,
) -> dict[str, str]:
    token = create_access_token(
        subject=f"lease-v2-{uid}",
        claims={
            "uid": uid,
            "tenant_id": tenant_id,
            "permissions": permissions,
            "park_ids": park_ids or [],
            "park_scope_mode": park_scope_mode,
        },
    )
    return {"Authorization": f"Bearer {token}"}


def _seed_contract(
    client,
    headers: dict[str, str],
    *,
    start_date: str = "2026-01-01",
    end_date: str = "2026-03-31",
) -> tuple[int, int, int]:
    park = client.post(
        "/api/v1/parks",
        headers=headers,
        json={"name": "合同V2园区", "address": "本地测试"},
    ).json()["data"]
    unit = client.post(
        "/api/v1/units",
        headers=headers,
        json={
            "park_id": park["id"],
            "name": "V2-101",
            "code": "V2101",
            "rentable_area": 200,
            "status": "VACANT",
        },
    ).json()["data"]
    party = client.post(
        "/api/v1/parties",
        headers=headers,
        json={"name": "合同V2承租企业", "party_type": "ORGANIZATION"},
    ).json()["data"]
    contract = client.post(
        "/api/v1/leases",
        headers=headers,
        json={
            "park_id": park["id"],
            "party_id": party["id"],
            "start_date": start_date,
            "end_date": end_date,
            "deposit_amount": "1000",
            "units": [{"unit_id": unit["id"], "occupied_area": "80", "unit_rent_price": "5"}],
        },
    ).json()["data"]
    return int(contract["id"]), int(unit["id"]), int(park["id"])


def _activate_minimal_v2(
    client,
    admin: dict[str, str],
    *,
    start_date: str = "2026-01-01",
    end_date: str = "2026-03-31",
) -> tuple[int, int, int, dict]:
    contract_id, unit_id, park_id = _seed_contract(
        client, admin, start_date=start_date, end_date=end_date
    )
    client.put(
        f"/api/v1/leases/{contract_id}/charges",
        headers=admin,
        json={
            "expected_version": 1,
            "charges": [
                {
                    "charge_code": "RENT",
                    "charge_type": "RENT",
                    "calculation_method": "FIXED",
                    "billing_cycle": "MONTHLY",
                    "start_date": start_date,
                    "end_date": end_date,
                    "amount": "1000",
                }
            ],
        },
    )
    submitted = client.post(
        f"/api/v1/leases/{contract_id}/lifecycle/submit",
        headers=admin,
        json={"expected_version": 2},
    ).json()["data"]
    client.post(
        f"/api/v1/leases/{contract_id}/lifecycle/approve",
        headers=admin,
        json={
            "approval_id": submitted["pending_approval"]["id"],
            "expected_version": 3,
            "override_reason": "本地单管理员合成验收",
        },
    )
    content = b"minimal v2 contract"
    attachment = client.post(
        "/api/v1/attachments",
        headers=admin,
        json={
            "biz_type": "LEASE_CONTRACT",
            "biz_id": str(contract_id),
            "filename": "minimal.txt",
            "content_base64": base64.b64encode(content).decode("ascii"),
            "park_id": park_id,
        },
    ).json()["data"]
    document = client.post(
        f"/api/v1/leases/{contract_id}/documents",
        headers=admin,
        json={
            "expected_version": 4,
            "attachment_id": attachment["id"],
            "document_type": "MAIN_CONTRACT",
            "checksum": hashlib.sha256(content).hexdigest(),
            "is_main": True,
        },
    ).json()["data"]
    client.post(
        f"/api/v1/leases/{contract_id}/documents/{document['documents'][-1]['id']}/approve",
        headers=admin,
        json={"expected_version": 5},
    )
    active = client.post(
        f"/api/v1/leases/{contract_id}/lifecycle/activate",
        headers=admin,
        json={"expected_version": 6},
    )
    assert active.status_code == 200, active.text
    return contract_id, unit_id, park_id, active.json()["data"]


def test_atomic_draft_create_includes_charges_and_rolls_back_invalid_schedule(
    client, db_session: Session
) -> None:
    admin = _headers(permissions=["*"])
    seed_id, unit_id, park_id = _seed_contract(client, admin)
    seed = client.get(f"/api/v1/leases/{seed_id}", headers=admin).json()["data"]
    before = db_session.scalar(select(func.count()).select_from(LeaseContract))
    payload = {
        "park_id": park_id,
        "party_id": seed["party_id"],
        "start_date": "2026-04-01",
        "end_date": "2026-06-30",
        "deposit_amount": "500",
        "units": [{"unit_id": unit_id, "occupied_area": "20", "unit_rent_price": "5"}],
        "charges": [
            {
                "charge_code": "RENT",
                "charge_type": "RENT",
                "calculation_method": "FIXED",
                "billing_cycle": "MONTHLY",
                "start_date": "2026-04-01",
                "end_date": "2026-06-30",
                "amount": "500",
            }
        ],
    }
    created = client.post("/api/v1/leases", headers=admin, json=payload)
    assert created.status_code == 200, created.text
    assert created.json()["data"]["schedule_preview"]["row_count"] == 3
    assert created.json()["data"]["lock_version"] == 2

    invalid = deepcopy(payload)
    invalid["contract_no"] = "ATOMIC-ROLLBACK-INVALID"
    invalid["charges"][0]["rules"] = [
        {"rule_type": "RENT_FREE", "effective_date": "2026-04-15", "end_date": "2026-04-30"}
    ]
    failed = client.post("/api/v1/leases", headers=admin, json=invalid)
    assert failed.status_code == 400, failed.text
    assert failed.json()["code"] == "LEASE_PRORATION_UNSUPPORTED"
    db_session.expire_all()
    after = db_session.scalar(select(func.count()).select_from(LeaseContract))
    assert after == before + 1
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(LeaseContract)
            .where(LeaseContract.contract_no == "ATOMIC-ROLLBACK-INVALID")
        )
        == 0
    )


def test_document_review_and_signature_work_items_follow_document_versions(client) -> None:
    admin = _headers(permissions=["*"])
    contract_id, _, park_id = _seed_contract(client, admin)
    content = b"document work item lifecycle"
    attachment = client.post(
        "/api/v1/attachments",
        headers=admin,
        json={
            "biz_type": "LEASE_CONTRACT",
            "biz_id": str(contract_id),
            "filename": "work-item.txt",
            "content_base64": base64.b64encode(content).decode("ascii"),
            "park_id": park_id,
        },
    )
    assert attachment.status_code == 200, attachment.text

    uploaded = client.post(
        f"/api/v1/leases/{contract_id}/documents",
        headers=admin,
        json={
            "expected_version": 1,
            "attachment_id": attachment.json()["data"]["id"],
            "document_type": "MAIN_CONTRACT",
            "checksum": hashlib.sha256(content).hexdigest(),
            "is_main": True,
        },
    )
    assert uploaded.status_code == 200, uploaded.text
    draft_document = uploaded.json()["data"]["documents"][-1]

    review_items = client.get(
        "/api/v1/work-items",
        headers=admin,
        params={"item_type": "LEASE_DOCUMENT_REVIEW", "page_size": 100},
    ).json()["data"]["items"]
    review = next(
        item
        for item in review_items
        if item["source_type"] == "LEASE_DOCUMENT"
        and item["source_id"] == str(draft_document["id"])
    )
    assert review["status"] == "OPEN"

    approved = client.post(
        f"/api/v1/leases/{contract_id}/documents/{draft_document['id']}/approve",
        headers=admin,
        json={"expected_version": 2},
    )
    assert approved.status_code == 200, approved.text
    approved_document = approved.json()["data"]["documents"][-1]

    review_items = client.get(
        "/api/v1/work-items",
        headers=admin,
        params={"item_type": "LEASE_DOCUMENT_REVIEW", "page_size": 100},
    ).json()["data"]["items"]
    assert next(item for item in review_items if item["id"] == review["id"])["status"] == "DONE"
    signature_items = client.get(
        "/api/v1/work-items",
        headers=admin,
        params={"item_type": "LEASE_SIGNATURE_WAIT", "page_size": 100},
    ).json()["data"]["items"]
    signature = next(
        item
        for item in signature_items
        if item["source_type"] == "LEASE_DOCUMENT"
        and item["source_id"] == str(approved_document["id"])
    )
    assert signature["status"] == "OPEN"

    signed = client.post(
        f"/api/v1/leases/{contract_id}/documents/{approved_document['id']}/sign",
        headers=admin,
        json={"expected_version": 3},
    )
    assert signed.status_code == 200, signed.text
    sandbox_document = max(
        signed.json()["data"]["documents"], key=lambda row: row["document_version"]
    )
    assert sandbox_document["status"] == "SANDBOX_COMPLETED"
    assert sandbox_document["signature_provider"] == "local_sandbox"
    assert sandbox_document["live_verified"] is False
    signature_items = client.get(
        "/api/v1/work-items",
        headers=admin,
        params={"item_type": "LEASE_SIGNATURE_WAIT", "page_size": 100},
    ).json()["data"]["items"]
    assert (
        next(item for item in signature_items if item["id"] == signature["id"])["status"] == "OPEN"
    )


def test_legacy_mutation_paths_cannot_bypass_v2_governance(client) -> None:
    admin = _headers(permissions=["*"])
    contract_id, _, _ = _seed_contract(client, admin)
    charges = client.put(
        f"/api/v1/leases/{contract_id}/charges",
        headers=admin,
        json={
            "expected_version": 1,
            "charges": [
                {
                    "charge_code": "RENT",
                    "charge_type": "RENT",
                    "calculation_method": "FIXED",
                    "billing_cycle": "MONTHLY",
                    "start_date": "2026-01-01",
                    "end_date": "2026-03-31",
                    "amount": "1000",
                }
            ],
        },
    )
    assert charges.status_code == 200, charges.text
    assert client.post(f"/api/v1/leases/{contract_id}/submit", headers=admin).status_code == 422
    submitted = client.post(
        f"/api/v1/leases/{contract_id}/submit",
        headers=admin,
        json={"expected_version": 2},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["data"]["contract"]["status"] == "PENDING_APPROVAL"
    activate = client.post(
        f"/api/v1/leases/{contract_id}/activate",
        headers=admin,
        json={"expected_version": 3},
    )
    assert activate.status_code == 409
    assert activate.json()["code"] == "LEASE_APPROVAL_REQUIRED"
    for action in ("terminate", "breach"):
        denied = client.post(f"/api/v1/leases/{contract_id}/{action}", headers=admin)
        assert denied.status_code == 409
        assert denied.json()["code"] == "LEASE_EXIT_SETTLEMENT_REQUIRED"


def test_governed_contract_activation_creates_version_not_bill(client, db_session: Session) -> None:
    admin = _headers(permissions=["*"])
    applicant = _headers(
        permissions=[
            "lease:read",
            "lease:write",
            "lease:approve",
            "approval:read",
            "approval:write",
            "approval:decide",
        ]
    )
    contract_id, unit_id, park_id = _seed_contract(client, admin)

    charges = client.put(
        f"/api/v1/leases/{contract_id}/charges",
        headers=admin,
        json={
            "expected_version": 1,
            "charges": [
                {
                    "charge_code": "RENT",
                    "charge_type": "RENT",
                    "calculation_method": "PER_AREA",
                    "billing_cycle": "MONTHLY",
                    "start_date": "2026-01-01",
                    "end_date": "2026-03-31",
                    "unit_price": "5.005",
                    "tax_rate": "0.06",
                    "due_day": 5,
                    "rules": [
                        {
                            "rule_type": "RENT_FREE",
                            "effective_date": "2026-02-01",
                            "end_date": "2026-02-28",
                            "rule_ref": "FREE-FEB",
                        }
                    ],
                }
            ],
        },
    )
    assert charges.status_code == 200, charges.text
    charge_data = charges.json()["data"]
    assert charge_data["row_count"] == 3
    assert charge_data["rows"][0]["gross_amount"] == "424.42"
    assert charge_data["rows"][1]["gross_amount"] == "0.00"

    submitted = client.post(
        f"/api/v1/leases/{contract_id}/lifecycle/submit",
        headers=applicant,
        json={"expected_version": 2, "remark": "申请审批"},
    )
    assert submitted.status_code == 200, submitted.text
    submitted_data = submitted.json()["data"]
    approval_id = submitted_data["pending_approval"]["id"]
    assert submitted_data["contract"]["status"] == "PENDING_APPROVAL"
    assert submitted_data["contract"]["lock_version"] == 3

    generic = client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        headers=admin,
        json={"remark": "不应从通用入口决定"},
    )
    assert generic.status_code == 409
    assert generic.json()["code"] == "APPROVAL_DOMAIN_COMMAND_REQUIRED"

    self_approval = client.post(
        f"/api/v1/leases/{contract_id}/lifecycle/approve",
        headers=applicant,
        json={"approval_id": approval_id, "expected_version": 3, "remark": "自批"},
    )
    assert self_approval.status_code == 403
    assert self_approval.json()["code"] == "LEASE_SELF_APPROVAL_FORBIDDEN"

    approved = client.post(
        f"/api/v1/leases/{contract_id}/lifecycle/approve",
        headers=admin,
        json={
            "approval_id": approval_id,
            "expected_version": 3,
            "remark": "同意",
            "override_reason": "本地验收管理员单人场景",
        },
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["contract"]["status"] == "PENDING_ACTIVE"

    no_document = client.post(
        f"/api/v1/leases/{contract_id}/lifecycle/activate",
        headers=admin,
        json={"expected_version": 4},
    )
    assert no_document.status_code == 409
    assert no_document.json()["code"] == "LEASE_DOCUMENT_REQUIRED"

    content = b"synthetic contract v2 document"
    checksum = hashlib.sha256(content).hexdigest()
    uploaded = client.post(
        "/api/v1/attachments",
        headers=admin,
        json={
            "biz_type": "LEASE_CONTRACT",
            "biz_id": str(contract_id),
            "filename": "contract-v2.txt",
            "content_base64": base64.b64encode(content).decode("ascii"),
            "content_type": "text/plain",
            "park_id": park_id,
        },
    )
    assert uploaded.status_code == 200, uploaded.text
    attachment_id = uploaded.json()["data"]["id"]

    document = client.post(
        f"/api/v1/leases/{contract_id}/documents",
        headers=admin,
        json={
            "expected_version": 4,
            "attachment_id": attachment_id,
            "document_type": "MAIN_CONTRACT",
            "checksum": checksum,
            "is_main": True,
        },
    )
    assert document.status_code == 200, document.text
    document_id = document.json()["data"]["documents"][-1]["id"]

    document_approved = client.post(
        f"/api/v1/leases/{contract_id}/documents/{document_id}/approve",
        headers=admin,
        json={"expected_version": 5},
    )
    assert document_approved.status_code == 200, document_approved.text
    documents = document_approved.json()["data"]["documents"]
    assert [row["status"] for row in documents] == ["DRAFT", "APPROVED"]

    activated = client.post(
        f"/api/v1/leases/{contract_id}/lifecycle/activate",
        headers=admin,
        json={"expected_version": 6},
    )
    assert activated.status_code == 200, activated.text
    result = activated.json()["data"]
    assert result["contract"]["status"] == "ACTIVE"
    assert result["contract"]["current_version_no"] == 1
    assert result["contract"]["lock_version"] == 7
    assert len(result["versions"]) == 1
    assert len(result["versions"][0]["checksum"]) == 64
    assert len(result["schedules"]) == 3
    assert result["billing_effect"] == "NONE"
    assert result["approval_ids"] == [approval_id]
    assert result["approval_timeline"][0]["status"] == "APPROVED"
    assert [event["action"] for event in result["approval_timeline"][0]["events"]] == [
        "SUBMIT",
        "APPROVE",
    ]

    unit = db_session.scalar(select(Unit).where(Unit.id == unit_id))
    db_session.refresh(unit)
    assert Decimal(str(unit.used_area)) == Decimal("80")
    assert db_session.scalar(select(func.count()).select_from(Bill)) == 0
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(LeaseContractVersion)
            .where(LeaseContractVersion.contract_id == contract_id)
        )
        == 1
    )


def test_v2_stale_and_foreign_attachment_fail_closed(client) -> None:
    admin = _headers(permissions=["*"])
    contract_id, _, park_id = _seed_contract(client, admin)
    stale = client.post(
        f"/api/v1/leases/{contract_id}/schedule-preview",
        headers=admin,
        json={"expected_version": 99},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "LEASE_VERSION_CONFLICT"

    content = b"foreign attachment"
    attachment = client.post(
        "/api/v1/attachments",
        headers=admin,
        json={
            "biz_type": "OTHER",
            "biz_id": "7",
            "filename": "other.txt",
            "content_base64": base64.b64encode(content).decode("ascii"),
            "park_id": park_id,
        },
    ).json()["data"]
    denied = client.post(
        f"/api/v1/leases/{contract_id}/documents",
        headers=admin,
        json={
            "expected_version": 1,
            "attachment_id": attachment["id"],
            "document_type": "MAIN_CONTRACT",
            "checksum": hashlib.sha256(content).hexdigest(),
            "is_main": True,
        },
    )
    assert denied.status_code == 404
    assert denied.json()["code"] == "ATTACHMENT_NOT_FOUND"


def test_approved_renewal_applies_one_version_and_replays_idempotently(
    client, db_session: Session
) -> None:
    admin = _headers(permissions=["*"])
    contract_id, _, park_id = _seed_contract(client, admin)
    charge_response = client.put(
        f"/api/v1/leases/{contract_id}/charges",
        headers=admin,
        json={
            "expected_version": 1,
            "charges": [
                {
                    "charge_code": "RENT",
                    "charge_type": "RENT",
                    "calculation_method": "FIXED",
                    "billing_cycle": "MONTHLY",
                    "start_date": "2026-01-01",
                    "end_date": "2026-03-31",
                    "amount": "1000",
                    "tax_rate": "0",
                }
            ],
        },
    )
    assert charge_response.status_code == 200
    submitted = client.post(
        f"/api/v1/leases/{contract_id}/lifecycle/submit",
        headers=admin,
        json={"expected_version": 2},
    ).json()["data"]
    approval_id = submitted["pending_approval"]["id"]
    approved = client.post(
        f"/api/v1/leases/{contract_id}/lifecycle/approve",
        headers=admin,
        json={
            "approval_id": approval_id,
            "expected_version": 3,
            "override_reason": "本地单管理员合成验收",
        },
    )
    assert approved.status_code == 200
    content = b"renewal baseline contract"
    attachment = client.post(
        "/api/v1/attachments",
        headers=admin,
        json={
            "biz_type": "LEASE_CONTRACT",
            "biz_id": str(contract_id),
            "filename": "renewal-base.txt",
            "content_base64": base64.b64encode(content).decode("ascii"),
            "park_id": park_id,
        },
    ).json()["data"]
    document = client.post(
        f"/api/v1/leases/{contract_id}/documents",
        headers=admin,
        json={
            "expected_version": 4,
            "attachment_id": attachment["id"],
            "document_type": "MAIN_CONTRACT",
            "checksum": hashlib.sha256(content).hexdigest(),
            "is_main": True,
        },
    ).json()["data"]
    document_id = document["documents"][-1]["id"]
    client.post(
        f"/api/v1/leases/{contract_id}/documents/{document_id}/approve",
        headers=admin,
        json={"expected_version": 5},
    )
    active = client.post(
        f"/api/v1/leases/{contract_id}/lifecycle/activate",
        headers=admin,
        json={"expected_version": 6},
    )
    assert active.status_code == 200, active.text
    state = active.json()["data"]
    proposed = deepcopy(state["current_snapshot"])
    proposed["contract"]["end_date"] = "2027-03-31"
    proposed["charges"][0]["end_date"] = "2027-03-31"
    change_created = client.post(
        f"/api/v1/leases/{contract_id}/changes",
        headers=admin,
        json={
            "expected_version": 7,
            "change_type": "RENEWAL",
            "effective_date": "2026-04-01",
            "reason": "续租一年",
            "proposed_snapshot": proposed,
        },
    )
    assert change_created.status_code == 200, change_created.text
    change_id = change_created.json()["data"]["changes"][0]["id"]
    change_submitted = client.post(
        f"/api/v1/lease-changes/{change_id}/submit",
        headers=admin,
        json={"expected_version": 8, "remark": "续租审批"},
    )
    assert change_submitted.status_code == 200, change_submitted.text
    change_approved = client.post(
        f"/api/v1/lease-changes/{change_id}/approve",
        headers=admin,
        json={
            "expected_version": 9,
            "override_reason": "本地单管理员合成验收",
        },
    )
    assert change_approved.status_code == 200, change_approved.text
    applied = client.post(
        f"/api/v1/lease-changes/{change_id}/apply",
        headers=admin,
        json={
            "expected_version": 10,
            "idempotency_key": "renewal-apply-1",
            "as_of": "2026-04-01",
        },
    )
    assert applied.status_code == 200, applied.text
    applied_state = applied.json()["data"]
    assert applied_state["contract"]["current_version_no"] == 2
    assert applied_state["contract"]["end_date"] == "2027-03-31"
    assert applied_state["changes"][0]["status"] == "APPLIED"
    assert applied_state["changes"][0]["applied_version_no"] == 2
    assert len(applied_state["versions"]) == 2
    assert len(applied_state["schedules"]) == 18

    replay = client.post(
        f"/api/v1/lease-changes/{change_id}/apply",
        headers=admin,
        json={
            "expected_version": 10,
            "idempotency_key": "renewal-apply-1",
            "as_of": "2026-04-01",
        },
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["contract"]["current_version_no"] == 2
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(LeaseContractVersion)
            .where(LeaseContractVersion.contract_id == contract_id)
        )
        == 2
    )


def test_exit_retains_occupancy_until_cleared_close_and_replays(
    client, db_session: Session
) -> None:
    admin = _headers(permissions=["*"])
    contract_id, unit_id, park_id, _ = _activate_minimal_v2(client, admin)
    created = client.post(
        f"/api/v1/leases/{contract_id}/exit-settlements",
        headers=admin,
        json={
            "expected_version": 7,
            "handover_date": "2026-03-31",
            "inspection_summary": "合成交接",
        },
    )
    assert created.status_code == 200, created.text
    settlement = created.json()["data"]["exit_settlement"]
    settlement_id = settlement["id"]
    assert settlement["status"] == "DRAFT"
    assert settlement["outstanding_source"] == "BILLING_SCOPED_READ"

    edited = client.put(
        f"/api/v1/lease-exit-settlements/{settlement_id}",
        headers=admin,
        json={
            "expected_version": 1,
            "inspection_summary": "验房完成",
            "meter_readings": [
                {"meter_code": "POWER", "previous_reading": "10", "current_reading": "12"}
            ],
            "items": [{"item_type": "DEDUCTION", "amount": "200", "description": "维修扣减"}],
        },
    )
    assert edited.status_code == 200, edited.text
    settlement = edited.json()["data"]["exit_settlement"]
    assert settlement["net_due_to_party"] == "800.00"
    assert settlement["net_due_from_party"] == "0.00"

    submitted = client.post(
        f"/api/v1/lease-exit-settlements/{settlement_id}/submit",
        headers=admin,
        json={"expected_version": 2, "contract_expected_version": 8},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["data"]["contract"]["status"] == "EXIT_PENDING"
    unit = db_session.scalar(select(Unit).where(Unit.id == unit_id))
    db_session.refresh(unit)
    assert Decimal(str(unit.used_area)) == Decimal("80")

    approved = client.post(
        f"/api/v1/lease-exit-settlements/{settlement_id}/approve",
        headers=admin,
        json={"expected_version": 3, "override_reason": "本地单管理员合成验收"},
    )
    assert approved.status_code == 200, approved.text
    blocked = client.post(
        f"/api/v1/lease-exit-settlements/{settlement_id}/close",
        headers=admin,
        json={
            "expected_version": 4,
            "contract_expected_version": 9,
            "idempotency_key": "exit-close-1",
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "LEASE_FINANCIAL_CLEARANCE_REQUIRED"

    evidence = b"synthetic offline settlement evidence"
    evidence_checksum = hashlib.sha256(evidence).hexdigest()
    attachment = client.post(
        "/api/v1/attachments",
        headers=admin,
        json={
            "biz_type": "LEASE_EXIT_SETTLEMENT",
            "biz_id": str(settlement_id),
            "filename": "exit-evidence.txt",
            "content_base64": base64.b64encode(evidence).decode("ascii"),
            "park_id": park_id,
        },
    ).json()["data"]
    clearance = client.post(
        f"/api/v1/lease-exit-settlements/{settlement_id}/clearance",
        headers=admin,
        json={
            "expected_version": 4,
            "evidence_attachment_id": attachment["id"],
            "reference": "OFFLINE-CLEARANCE-001",
            "reason": "本地合成线下清算凭证复核",
        },
    )
    assert clearance.status_code == 200, clearance.text
    assert clearance.json()["data"]["exit_settlement"]["financial_clearance_status"] == (
        "CONFIRMED"
    )

    exit_document = client.post(
        f"/api/v1/leases/{contract_id}/documents",
        headers=admin,
        json={
            "expected_version": 9,
            "attachment_id": attachment["id"],
            "document_type": "EXIT_HANDOVER",
            "checksum": evidence_checksum,
            "is_main": False,
            "exit_settlement_id": settlement_id,
        },
    )
    assert exit_document.status_code == 200, exit_document.text
    exit_document_id = next(
        row["id"]
        for row in exit_document.json()["data"]["documents"]
        if row["document_type"] == "EXIT_HANDOVER" and row["status"] == "DRAFT"
    )
    exit_document_approved = client.post(
        f"/api/v1/leases/{contract_id}/documents/{exit_document_id}/approve",
        headers=admin,
        json={"expected_version": 10},
    )
    assert exit_document_approved.status_code == 200, exit_document_approved.text

    closed = client.post(
        f"/api/v1/lease-exit-settlements/{settlement_id}/close",
        headers=admin,
        json={
            "expected_version": 5,
            "contract_expected_version": 11,
            "idempotency_key": "exit-close-1",
        },
    )
    assert closed.status_code == 200, closed.text
    result = closed.json()["data"]
    assert result["contract"]["status"] == "TERMINATED"
    assert result["contract"]["current_version_no"] == 2
    assert result["exit_settlement"]["status"] == "CLOSED"
    assert result["exit_settlement"]["financial_effect"] == "NONE"
    db_session.refresh(unit)
    assert Decimal(str(unit.used_area)) == Decimal("0")

    replay = client.post(
        f"/api/v1/lease-exit-settlements/{settlement_id}/close",
        headers=admin,
        json={
            "expected_version": 5,
            "contract_expected_version": 11,
            "idempotency_key": "exit-close-1",
        },
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["contract"]["current_version_no"] == 2
    assert db_session.scalar(select(func.count()).select_from(Bill)) == 0


def test_rejected_exit_restores_active_contract_and_keeps_occupancy(
    client, db_session: Session
) -> None:
    admin = _headers(permissions=["*"])
    contract_id, unit_id, _, _ = _activate_minimal_v2(client, admin)
    created = client.post(
        f"/api/v1/leases/{contract_id}/exit-settlements",
        headers=admin,
        json={"expected_version": 7, "handover_date": "2026-03-31"},
    )
    assert created.status_code == 200, created.text
    settlement_id = created.json()["data"]["exit_settlement"]["id"]

    submitted = client.post(
        f"/api/v1/lease-exit-settlements/{settlement_id}/submit",
        headers=admin,
        json={"expected_version": 1, "contract_expected_version": 8},
    )
    assert submitted.status_code == 200, submitted.text
    rejected = client.post(
        f"/api/v1/lease-exit-settlements/{settlement_id}/reject",
        headers=admin,
        json={"expected_version": 2, "override_reason": "合成验收：退租审批驳回"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["data"]["contract"]["status"] == "ACTIVE"
    assert rejected.json()["data"]["exit_settlement"]["status"] == "REJECTED"
    unit = db_session.scalar(select(Unit).where(Unit.id == unit_id))
    db_session.refresh(unit)
    assert Decimal(str(unit.used_area)) == Decimal("80")


def test_exit_applicant_can_withdraw_and_restore_active_contract(client) -> None:
    admin = _headers(permissions=["*"])
    contract_id, _, _, _ = _activate_minimal_v2(client, admin)
    created = client.post(
        f"/api/v1/leases/{contract_id}/exit-settlements",
        headers=admin,
        json={"expected_version": 7, "handover_date": "2026-03-31"},
    )
    assert created.status_code == 200, created.text
    settlement_id = created.json()["data"]["exit_settlement"]["id"]
    submitted = client.post(
        f"/api/v1/lease-exit-settlements/{settlement_id}/submit",
        headers=admin,
        json={"expected_version": 1, "contract_expected_version": 8},
    )
    assert submitted.status_code == 200, submitted.text
    withdrawn = client.post(
        f"/api/v1/lease-exit-settlements/{settlement_id}/withdraw",
        headers=admin,
        json={
            "expected_version": 2,
            "contract_expected_version": 9,
            "remark": "承租方撤回退租申请",
        },
    )
    assert withdrawn.status_code == 200, withdrawn.text
    assert withdrawn.json()["data"]["contract"]["status"] == "ACTIVE"
    assert withdrawn.json()["data"]["exit_settlement"]["status"] == "WITHDRAWN"


def test_change_edit_cancel_and_withdraw_commands(client) -> None:
    admin = _headers(permissions=["*"])
    contract_id, _, _, state = _activate_minimal_v2(client, admin)
    proposed = deepcopy(state["current_snapshot"])
    proposed["contract"]["end_date"] = "2027-03-31"
    proposed["charges"][0]["end_date"] = "2027-03-31"
    created = client.post(
        f"/api/v1/leases/{contract_id}/changes",
        headers=admin,
        json={
            "expected_version": 7,
            "change_type": "RENEWAL",
            "effective_date": "2026-04-01",
            "reason": "续租草稿",
            "proposed_snapshot": proposed,
        },
    )
    assert created.status_code == 200, created.text
    change_id = created.json()["data"]["changes"][0]["id"]
    edited_proposal = deepcopy(proposed)
    edited_proposal["contract"]["end_date"] = "2028-03-31"
    edited_proposal["charges"][0]["end_date"] = "2028-03-31"
    edited = client.put(
        f"/api/v1/lease-changes/{change_id}",
        headers=admin,
        json={
            "expected_version": 8,
            "change_type": "RENEWAL",
            "effective_date": "2026-04-01",
            "reason": "续租草稿已修订",
            "proposed_snapshot": edited_proposal,
        },
    )
    assert edited.status_code == 200, edited.text
    edited_change = next(row for row in edited.json()["data"]["changes"] if row["id"] == change_id)
    assert edited_change["reason"] == "续租草稿已修订"
    cancelled = client.post(
        f"/api/v1/lease-changes/{change_id}/cancel",
        headers=admin,
        json={"expected_version": 9, "remark": "改用新方案"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert (
        next(row for row in cancelled.json()["data"]["changes"] if row["id"] == change_id)["status"]
        == "CANCELLED"
    )

    proposed["contract"]["end_date"] = "2029-03-31"
    proposed["charges"][0]["end_date"] = "2029-03-31"
    second = client.post(
        f"/api/v1/leases/{contract_id}/changes",
        headers=admin,
        json={
            "expected_version": 10,
            "change_type": "RENEWAL",
            "effective_date": "2026-04-01",
            "reason": "待撤回续租",
            "proposed_snapshot": proposed,
        },
    )
    assert second.status_code == 200, second.text
    second_id = second.json()["data"]["changes"][0]["id"]
    submitted = client.post(
        f"/api/v1/lease-changes/{second_id}/submit",
        headers=admin,
        json={"expected_version": 11},
    )
    assert submitted.status_code == 200, submitted.text
    withdrawn = client.post(
        f"/api/v1/lease-changes/{second_id}/withdraw",
        headers=admin,
        json={"expected_version": 12, "remark": "双方暂停续租"},
    )
    assert withdrawn.status_code == 200, withdrawn.text
    assert (
        next(row for row in withdrawn.json()["data"]["changes"] if row["id"] == second_id)["status"]
        == "WITHDRAWN"
    )


def test_apply_due_early_termination_links_exit_without_releasing_occupancy(
    client, db_session: Session
) -> None:
    admin = _headers(permissions=["*"])
    contract_id, unit_id, _, state = _activate_minimal_v2(
        client,
        admin,
        start_date="2099-01-01",
        end_date="2099-12-31",
    )
    proposed = deepcopy(state["current_snapshot"])
    created = client.post(
        f"/api/v1/leases/{contract_id}/changes",
        headers=admin,
        json={
            "expected_version": 7,
            "change_type": "EARLY_TERMINATION",
            "effective_date": "2099-06-01",
            "reason": "双方协商提前退租",
            "proposed_snapshot": proposed,
        },
    )
    assert created.status_code == 200, created.text
    change_id = created.json()["data"]["changes"][0]["id"]
    submitted = client.post(
        f"/api/v1/lease-changes/{change_id}/submit",
        headers=admin,
        json={"expected_version": 8},
    )
    assert submitted.status_code == 200, submitted.text
    approved = client.post(
        f"/api/v1/lease-changes/{change_id}/approve",
        headers=admin,
        json={"expected_version": 9, "override_reason": "本地合成管理员审批"},
    )
    assert approved.status_code == 200, approved.text
    batch = client.post(
        "/api/v1/lease-changes/apply-due",
        headers=admin,
        json={"as_of": "2099-06-01", "limit": 10},
    )
    assert batch.status_code == 200, batch.text
    assert batch.json()["data"]["processed"] == 1
    assert batch.json()["data"]["failed"] == []

    detail = client.get(f"/api/v1/leases/{contract_id}/lifecycle", headers=admin)
    assert detail.status_code == 200, detail.text
    result = detail.json()["data"]
    assert result["contract"]["status"] == "EXIT_PENDING"
    assert result["contract"]["current_version_no"] == 2
    assert result["exit_settlement"]["status"] == "DRAFT"
    assert result["exit_settlement"]["change_order_id"] == change_id
    settlement = db_session.scalar(
        select(LeaseExitSettlement).where(LeaseExitSettlement.contract_id == contract_id)
    )
    assert settlement is not None and settlement.change_order_id == change_id
    unit = db_session.scalar(select(Unit).where(Unit.id == unit_id))
    db_session.refresh(unit)
    assert Decimal(str(unit.used_area)) == Decimal("80")
    assert db_session.scalar(select(func.count()).select_from(Bill)) == 0


def test_signature_provider_fails_closed_outside_local_env(client, monkeypatch) -> None:
    admin = _headers(permissions=["*"])
    contract_id, _, _, state = _activate_minimal_v2(client, admin)
    approved_document = next(row for row in state["documents"] if row["status"] == "APPROVED")
    monkeypatch.setattr(
        "app.modules.lease.application.contract_lifecycle_service.get_settings",
        lambda: SimpleNamespace(app_env="production"),
    )
    failed = client.post(
        f"/api/v1/leases/{contract_id}/documents/{approved_document['id']}/sign",
        headers=admin,
        json={"expected_version": 7},
    )
    assert failed.status_code == 503, failed.text
    assert failed.json()["code"] == "SIGNATURE_PROVIDER_NOT_CONFIGURED"
    detail = client.get(f"/api/v1/leases/{contract_id}/lifecycle", headers=admin)
    assert len(detail.json()["data"]["documents"]) == 2


def test_contract_workspace_summary_selectors_and_party_profile(client) -> None:
    admin = _headers(permissions=["*"])
    contract_id, unit_id, park_id, state = _activate_minimal_v2(client, admin)
    reader = _headers(permissions=["lease:read"])
    summary = client.get(
        "/api/v1/leases/summary",
        headers=reader,
        params={"park_id": park_id, "as_of": "2026-02-01"},
    )
    assert summary.status_code == 200, summary.text
    metrics = summary.json()["data"]["metrics"]
    assert metrics["current_contracts"] == 1
    assert metrics["current_deposit_amount"] == "1000.00"
    assert metrics["unresolved_clearance"] == 0

    selectors = client.get("/api/v1/leases/selectors", headers=reader, params={"park_id": park_id})
    assert selectors.status_code == 200, selectors.text
    selector_data = selectors.json()["data"]
    assert any(row["id"] == park_id for row in selector_data["parks"])
    assert any(row["id"] == unit_id for row in selector_data["units"])
    assert any(row["id"] == state["contract"]["party_id"] for row in selector_data["parties"])

    profile = client.get(
        f"/api/v1/parties/{state['contract']['party_id']}/lease-profile", headers=reader
    )
    assert profile.status_code == 200, profile.text
    profile_data = profile.json()["data"]
    assert [row["id"] for row in profile_data["current_contracts"]] == [contract_id]
    assert profile_data["billing_summary"]["financial_effect"] == "NONE"

    filtered = client.get(
        "/api/v1/leases",
        headers=reader,
        params={"keyword": state["contract"]["contract_no"], "contract_type": "LEASE"},
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["data"]["items"][0]["lock_version"] == 7


def test_contract_list_pagination_privacy_and_scope_are_fail_closed(client) -> None:
    admin = _headers(permissions=["*"])
    first_id, unit_id, park_id = _seed_contract(client, admin)
    first = client.get(f"/api/v1/leases/{first_id}", headers=admin).json()["data"]
    visible_ids = [first_id]
    for index in (2, 3):
        created = client.post(
            "/api/v1/leases",
            headers=admin,
            json={
                "park_id": park_id,
                "party_id": first["party_id"],
                "contract_no": f"SCOPE-PAGE-{uuid4().hex[:12]}-{index}",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "units": [{"unit_id": unit_id, "occupied_area": "10", "unit_rent_price": "5"}],
            },
        )
        assert created.status_code == 200, created.text
        visible_ids.append(int(created.json()["data"]["id"]))
    foreign_id, _, foreign_park_id = _seed_contract(client, admin)
    assert foreign_park_id != park_id

    scoped = _headers(permissions=["lease:read"], park_scope_mode="LIST", park_ids=[park_id])
    first_page = client.get("/api/v1/leases", headers=scoped, params={"page": 1, "page_size": 1})
    second_page = client.get("/api/v1/leases", headers=scoped, params={"page": 2, "page_size": 1})
    assert first_page.status_code == 200 and second_page.status_code == 200
    assert first_page.json()["data"]["total"] == 3
    assert first_page.json()["data"]["page"] == 1
    assert first_page.json()["data"]["page_size"] == 1
    assert [
        first_page.json()["data"]["items"][0]["id"],
        second_page.json()["data"]["items"][0]["id"],
    ] == sorted(visible_ids, reverse=True)[:2]
    assert all(row["park_id"] == park_id for row in first_page.json()["data"]["items"])

    cross_park = client.get(f"/api/v1/leases/{foreign_id}", headers=scoped)
    assert cross_park.status_code == 404
    assert cross_park.json()["code"] == "LEASE_NOT_FOUND"
    cross_tenant = _headers(permissions=["lease:read"], tenant_id=999999)
    cross_tenant_list = client.get("/api/v1/leases", headers=cross_tenant)
    assert cross_tenant_list.status_code == 401
    assert cross_tenant_list.json()["code"] == "AUTH_SESSION_REVOKED"
    hidden = client.get(f"/api/v1/leases/{first_id}", headers=cross_tenant)
    assert hidden.status_code == 401
    assert hidden.json()["code"] == "AUTH_SESSION_REVOKED"

    empty = client.get(
        "/api/v1/leases",
        headers=scoped,
        params={"keyword": f"NO-MATCH-{uuid4().hex}"},
    )
    assert empty.status_code == 200
    assert empty.json()["data"]["total"] == 0
    assert empty.json()["data"]["items"] == []
    invalid_page = client.get("/api/v1/leases", headers=scoped, params={"page_size": 201})
    assert invalid_page.status_code == 422
    assert invalid_page.json()["code"] == "VALIDATION_ERROR"

    lifecycle = client.get(f"/api/v1/leases/{first_id}/lifecycle", headers=scoped)
    assert lifecycle.status_code == 200, lifecycle.text

    def all_keys(value) -> set[str]:
        if isinstance(value, dict):
            return set(value) | set().union(*(all_keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(all_keys(item) for item in value)) if value else set()
        return set()

    exposed_keys = all_keys(first_page.json()) | all_keys(lifecycle.json())
    forbidden = {
        "password",
        "password_hash",
        "access_token",
        "refresh_token",
        "object_key",
        "signature_ref",
        "contact_phone",
        "id_card_no",
        "bank_account",
    }
    assert exposed_keys.isdisjoint(forbidden)

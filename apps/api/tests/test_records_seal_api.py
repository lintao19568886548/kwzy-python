"""End-to-end API tests for governed records, approvals, seals and signature truth."""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.infrastructure.database.models.records_seal import RecordFile


def _headers(
    uid: int = 1,
    *,
    permissions: list[str] | None = None,
    park_ids: list[int] | None = None,
    mode: str = "ALL",
) -> dict[str, str]:
    token = create_access_token(
        subject=f"records-user-{uid}",
        claims={
            "uid": uid,
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


def _publish_definition(
    client,
    headers: dict[str, str],
    *,
    code: str,
    biz_type: str,
    assignee_user_id: int,
) -> None:
    created = client.post(
        "/api/v1/approval-definitions",
        headers=headers,
        json={
            "code": code,
            "name": f"{code} 审批",
            "biz_type": biz_type,
            "steps": [
                {
                    "step_order": 1,
                    "name": "治理复核",
                    "approval_mode": "ANY",
                    "min_approvals": 1,
                    "sla_hours": 24,
                    "assignees": [{"user_id": assignee_user_id}],
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    definition = created.json()["data"]
    draft = next(item for item in definition["versions"] if item["status"] == "DRAFT")
    published = client.post(
        f"/api/v1/approval-definitions/{definition['id']}/publish",
        headers=headers,
        json={"version_id": draft["id"], "expected_lock_version": 0},
    )
    assert published.status_code == 200, published.text


def _approve(client, headers: dict[str, str], approval_id: int, *, suffix: str) -> None:
    detail = client.get(f"/api/v1/approvals/{approval_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    task = next(item for item in detail.json()["data"]["tasks"] if item["status"] == "PENDING")
    decision = client.post(
        f"/api/v1/approval-tasks/{task['id']}/decide",
        headers=headers,
        json={
            "action": "APPROVE",
            "expected_version": detail.json()["data"]["lock_version"],
            "idempotency_key": f"decision-{suffix}",
            "override_reason": "独立验收单用户审批门禁测试"
            if task["assignee_user_id"] == 1
            else None,
        },
    )
    assert decision.status_code == 200, decision.text


def _create_filed_record(client, headers: dict[str, str]) -> tuple[dict, dict, dict]:
    park_response = client.post(
        "/api/v1/parks",
        headers=headers,
        json={"name": f"档案园-{uuid4().hex[:8]}", "address": "档案验收地址"},
    )
    assert park_response.status_code == 200, park_response.text
    park = park_response.json()["data"]
    category_response = client.post(
        "/api/v1/record-categories",
        headers=headers,
        json={
            "code": f"LEASE_{uuid4().hex[:8].upper()}",
            "name": "合同档案",
            "retention_mode": "YEARS",
            "retention_years": 1,
            "confidentiality_max": "RESTRICTED",
        },
    )
    assert category_response.status_code == 200, category_response.text
    category = category_response.json()["data"]
    content = f"governed-record-{uuid4().hex}".encode()
    attachment_response = client.post(
        "/api/v1/attachments",
        headers=headers,
        json={
            "biz_type": "RECORD_SOURCE",
            "biz_id": uuid4().hex,
            "filename": "contract-evidence.txt",
            "content_type": "text/plain",
            "content_base64": base64.b64encode(content).decode("ascii"),
            "park_id": park["id"],
        },
    )
    assert attachment_response.status_code == 200, attachment_response.text
    attachment = attachment_response.json()["data"]
    record_response = client.post(
        "/api/v1/records",
        headers=headers,
        json={
            "park_id": park["id"],
            "category_id": category["id"],
            "title": "主合同归档件",
            "description": "独立验收合成档案",
            "confidentiality": "CONFIDENTIAL",
            "source_type": "LEASE_CONTRACT",
            "source_id": uuid4().hex,
        },
    )
    assert record_response.status_code == 200, record_response.text
    record = record_response.json()["data"]
    revised = client.post(
        f"/api/v1/records/{record['id']}/revisions",
        headers=headers,
        json={"expected_version": record["lock_version"], "attachment_id": attachment["id"]},
    )
    assert revised.status_code == 200, revised.text
    record = revised.json()["data"]
    revision = record["revisions"][0]
    assert revision["checksum_sha256"] == hashlib.sha256(content).hexdigest()
    pinned = client.delete(f"/api/v1/attachments/{attachment['id']}", headers=headers)
    assert pinned.status_code == 409, pinned.text
    assert pinned.json()["code"] == "ATTACHMENT_GOVERNED_RECORD_PINNED"
    filed = client.post(
        f"/api/v1/records/{record['id']}/file",
        headers=headers,
        json={"expected_version": record["lock_version"], "reason": "验收归档"},
    )
    assert filed.status_code == 200, filed.text
    return park, filed.json()["data"], revision


def test_category_can_switch_from_years_to_permanent_without_stale_years(client) -> None:
    admin = _headers()
    created = client.post(
        "/api/v1/record-categories",
        headers=admin,
        json={
            "code": f"PERM_{uuid4().hex[:8].upper()}",
            "name": "长期档案",
            "retention_mode": "YEARS",
            "retention_years": 10,
            "confidentiality_max": "CONFIDENTIAL",
        },
    )
    assert created.status_code == 200, created.text
    category = created.json()["data"]

    updated = client.patch(
        f"/api/v1/record-categories/{category['id']}",
        headers=admin,
        json={
            "expected_version": category["lock_version"],
            "reason": "依法调整为永久保管",
            "retention_mode": "PERMANENT",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["retention_mode"] == "PERMANENT"
    assert updated.json()["data"]["retention_years"] is None


def test_record_integrity_hold_scope_seal_and_sandbox_signature(client) -> None:
    admin = _headers()
    park, record, revision = _create_filed_record(client, admin)
    verified = client.post(
        f"/api/v1/records/{record['id']}/verify",
        headers=_key(admin, "verify-record-1"),
        json={"revision_id": revision["id"]},
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["data"]["result"] == "MATCH"
    replay = client.post(
        f"/api/v1/records/{record['id']}/verify",
        headers=_key(admin, "verify-record-1"),
        json={"revision_id": revision["id"]},
    )
    assert replay.json()["data"]["id"] == verified.json()["data"]["id"]

    held = client.post(
        f"/api/v1/records/{record['id']}/holds",
        headers=admin,
        json={"expected_version": record["lock_version"], "reason": "诉讼证据保全"},
    )
    assert held.status_code == 200, held.text
    held_record = held.json()["data"]
    assert held_record["status"] == "ON_HOLD"
    released = client.post(
        f"/api/v1/records/{record['id']}/holds/{held_record['holds'][0]['id']}/release",
        headers=admin,
        json={"expected_version": held_record["lock_version"], "reason": "案件结案"},
    )
    assert released.status_code == 200, released.text

    other_park = client.post(
        "/api/v1/parks",
        headers=admin,
        json={"name": f"隔离园-{uuid4().hex[:8]}", "address": "隔离范围"},
    ).json()["data"]
    scoped = _headers(permissions=["record:read"], park_ids=[other_park["id"]], mode="LIST")
    denied = client.get(f"/api/v1/records/{record['id']}", headers=scoped)
    assert denied.status_code == 404

    seal_response = client.post(
        "/api/v1/seals",
        headers=admin,
        json={
            "park_id": park["id"],
            "seal_code": f"CONTRACT-{uuid4().hex[:6]}",
            "name": "合同专用章",
            "kind": "CONTRACT",
            "custodian_user_id": 1,
            "description": "独立验收台账",
        },
    )
    assert seal_response.status_code == 200, seal_response.text
    assert seal_response.json()["data"]["custody_events"][0]["event_type"] == "CREATED"

    provider_response = client.post(
        "/api/v1/signature-providers",
        headers=admin,
        json={
            "code": f"SANDBOX_{uuid4().hex[:6].upper()}",
            "name": "本地非法律效力沙箱",
            "adapter_kind": "LOCAL_SANDBOX",
        },
    )
    assert provider_response.status_code == 200, provider_response.text
    provider = provider_response.json()["data"]
    assert provider["status"] == "SANDBOX"
    assert provider["live_verified"] is False
    envelope_response = client.post(
        "/api/v1/signature-envelopes",
        headers=admin,
        json={
            "provider_id": provider["id"],
            "record_id": record["id"],
            "revision_id": revision["id"],
            "source_type": "LEASE_CONTRACT",
            "source_id": uuid4().hex,
            "purpose": "沙箱流程验证",
            "participants": [
                {"role": "SIGNER", "display_name": "测试签署人", "contact_masked": "138****8000"}
            ],
        },
    )
    assert envelope_response.status_code == 200, envelope_response.text
    envelope = envelope_response.json()["data"]
    dispatched = client.post(
        f"/api/v1/signature-envelopes/{envelope['id']}/dispatch",
        headers=admin,
        json={"expected_version": envelope["lock_version"], "reason": "仅沙箱验证"},
    )
    assert dispatched.status_code == 200, dispatched.text
    signed = dispatched.json()["data"]
    assert signed["status"] == "SANDBOX_COMPLETED"
    assert signed["live_verified"] is False
    assert signed["events"][0]["detail"]["legal_effect"] is False


def test_native_approval_access_seal_use_and_two_person_disposition(
    client, db_session: Session
) -> None:
    admin = _headers()
    park, record, revision = _create_filed_record(client, admin)
    suffix = uuid4().hex[:8]
    role_response = client.post(
        "/api/v1/system/roles",
        headers=admin,
        json={
            "code": f"RECORD_GOV_{suffix.upper()}",
            "name": "档案治理复核",
            "all_parks": True,
            "permission_codes": [
                "record:dispose_confirm",
                "seal:execute",
                "approval.task.read",
                "approval.task.decide",
            ],
            "park_ids": [],
        },
    )
    assert role_response.status_code == 200, role_response.text
    role_id = role_response.json()["data"]["id"]
    user_ids: list[int] = []
    for index in (1, 2):
        response = client.post(
            "/api/v1/system/users",
            headers=admin,
            json={
                "username": f"record_gov_{suffix}_{index}",
                "password": "Records-Test-123!",
                "real_name": f"档案复核人{index}",
                "role_ids": [role_id],
                "park_ids": [],
                "all_parks": True,
            },
        )
        assert response.status_code == 200, response.text
        user_ids.append(response.json()["data"]["id"])
    reviewer = _headers(
        user_ids[0],
        permissions=["record:dispose_confirm", "approval.task.read", "approval.task.decide"],
    )
    confirmer = _headers(user_ids[1], permissions=["record:dispose_confirm", "seal:execute"])

    _publish_definition(
        client,
        admin,
        code=f"ACCESS_{suffix.upper()}",
        biz_type="RECORD_ACCESS",
        assignee_user_id=1,
    )
    access_response = client.post(
        f"/api/v1/records/{record['id']}/access-requests",
        headers=_key(admin, f"access-{suffix}"),
        json={
            "mode": "VIEW",
            "purpose": "合规查阅",
            "requested_until": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "definition_code": f"ACCESS_{suffix.upper()}",
        },
    )
    assert access_response.status_code == 200, access_response.text
    access = access_response.json()["data"]
    _approve(client, admin, access["approval_id"], suffix=f"access-{suffix}")
    refreshed_access = client.post(
        f"/api/v1/record-access-requests/{access['id']}/refresh-approval", headers=admin
    )
    assert refreshed_access.json()["data"]["status"] == "APPROVED"

    seal = client.post(
        "/api/v1/seals",
        headers=admin,
        json={
            "park_id": park["id"],
            "seal_code": f"USE-{suffix}",
            "name": "验收用印章",
            "kind": "OFFICIAL",
            "custodian_user_id": user_ids[1],
        },
    ).json()["data"]
    _publish_definition(
        client,
        admin,
        code=f"SEAL_{suffix.upper()}",
        biz_type="SEAL_USE",
        assignee_user_id=user_ids[0],
    )
    seal_use_response = client.post(
        "/api/v1/seal-use-applications",
        headers=_key(admin, f"seal-use-{suffix}"),
        json={
            "seal_id": seal["id"],
            "record_id": record["id"],
            "revision_id": revision["id"],
            "purpose": "合同盖章",
            "copy_count": 2,
            "requested_for": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "definition_code": f"SEAL_{suffix.upper()}",
        },
    )
    assert seal_use_response.status_code == 200, seal_use_response.text
    seal_use = seal_use_response.json()["data"]
    _approve(client, reviewer, seal_use["approval_id"], suffix=f"seal-{suffix}")
    seal_use = client.post(
        f"/api/v1/seal-use-applications/{seal_use['id']}/refresh-approval", headers=admin
    ).json()["data"]
    executed = client.post(
        f"/api/v1/seal-use-applications/{seal_use['id']}/execute",
        headers=_key(confirmer, f"seal-execute-{suffix}"),
        json={"expected_version": seal_use["lock_version"]},
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["data"]["status"] == "EXECUTED"
    replayed = client.post(
        f"/api/v1/seal-use-applications/{seal_use['id']}/execute",
        headers=_key(confirmer, f"seal-execute-{suffix}"),
        json={"expected_version": seal_use["lock_version"]},
    )
    assert replayed.status_code == 200, replayed.text
    assert replayed.json()["data"]["receipt"]["id"] == executed.json()["data"]["receipt"]["id"]
    changed_replay = client.post(
        f"/api/v1/seal-use-applications/{seal_use['id']}/execute",
        headers=_key(confirmer, f"seal-execute-{suffix}"),
        json={
            "expected_version": seal_use["lock_version"],
            "evidence_attachment_id": 999999,
        },
    )
    assert changed_replay.status_code == 409, changed_replay.text
    assert changed_replay.json()["code"] == "IDEMPOTENCY_CONFLICT"

    conflicting_seal = client.post(
        "/api/v1/seals",
        headers=admin,
        json={
            "park_id": park["id"],
            "seal_code": f"SOD-{suffix}",
            "name": "职责分离验证章",
            "kind": "CONTRACT",
            "custodian_user_id": 1,
        },
    ).json()["data"]
    conflicting_use = client.post(
        "/api/v1/seal-use-applications",
        headers=_key(admin, f"seal-use-sod-{suffix}"),
        json={
            "seal_id": conflicting_seal["id"],
            "record_id": record["id"],
            "revision_id": revision["id"],
            "purpose": "验证申请人不得执行合同章",
            "copy_count": 1,
            "requested_for": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "definition_code": f"SEAL_{suffix.upper()}",
        },
    ).json()["data"]
    _approve(client, reviewer, conflicting_use["approval_id"], suffix=f"seal-sod-{suffix}")
    conflicting_use = client.post(
        f"/api/v1/seal-use-applications/{conflicting_use['id']}/refresh-approval",
        headers=admin,
    ).json()["data"]
    separation_denied = client.post(
        f"/api/v1/seal-use-applications/{conflicting_use['id']}/execute",
        headers=_key(admin, f"seal-execute-sod-{suffix}"),
        json={"expected_version": conflicting_use["lock_version"]},
    )
    assert separation_denied.status_code == 403, separation_denied.text
    assert separation_denied.json()["code"] == "SEAL_USE_SEPARATION_OF_DUTIES"
    emergency = client.post(
        f"/api/v1/seal-use-applications/{conflicting_use['id']}/execute",
        headers=_key(admin, f"seal-execute-sod-{suffix}"),
        json={
            "expected_version": conflicting_use["lock_version"],
            "emergency_override_reason": "突发法定期限且无其他保管人在岗，已登记事后复核",
        },
    )
    assert emergency.status_code == 200, emergency.text
    assert emergency.json()["data"]["status"] == "EXECUTED"

    stored = db_session.scalar(select(RecordFile).where(RecordFile.id == record["id"]))
    assert stored is not None
    stored.retention_until = datetime.now(timezone.utc).date() - timedelta(days=1)
    db_session.commit()
    _publish_definition(
        client,
        admin,
        code=f"DISPOSE_{suffix.upper()}",
        biz_type="RECORD_DISPOSITION",
        assignee_user_id=user_ids[0],
    )
    current = client.get(f"/api/v1/records/{record['id']}", headers=admin).json()["data"]
    disposition_response = client.post(
        f"/api/v1/records/{record['id']}/dispositions",
        headers=_key(admin, f"dispose-{suffix}"),
        json={
            "expected_version": current["lock_version"],
            "reason": "保管期届满",
            "definition_code": f"DISPOSE_{suffix.upper()}",
        },
    )
    assert disposition_response.status_code == 200, disposition_response.text
    disposition = disposition_response.json()["data"]
    _approve(client, reviewer, disposition["approval_id"], suffix=f"dispose-{suffix}")
    disposition = client.post(
        f"/api/v1/record-dispositions/{disposition['id']}/refresh-approval", headers=admin
    ).json()["data"]
    assert disposition["status"] == "CONFIRMING"
    self_denied = client.post(
        f"/api/v1/record-dispositions/{disposition['id']}/confirm",
        headers=admin,
        json={"expected_version": disposition["lock_version"], "reason": "申请人自确认"},
    )
    assert self_denied.status_code == 403
    first = client.post(
        f"/api/v1/record-dispositions/{disposition['id']}/confirm",
        headers=reviewer,
        json={"expected_version": disposition["lock_version"], "reason": "现场复核一"},
    )
    assert first.status_code == 200, first.text
    second = client.post(
        f"/api/v1/record-dispositions/{disposition['id']}/confirm",
        headers=confirmer,
        json={
            "expected_version": first.json()["data"]["lock_version"],
            "reason": "现场复核二",
        },
    )
    assert second.status_code == 200, second.text
    disposed = second.json()["data"]
    assert disposed["status"] == "DISPOSED"
    assert disposed["storage_deletion_status"] == "RETAINED_LOGICAL_ONLY"
    assert len(disposed["confirmations"]) == 2

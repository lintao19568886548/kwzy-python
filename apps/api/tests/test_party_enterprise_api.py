"""End-to-end HTTP tests for the governed enterprise Party aggregate."""

from __future__ import annotations

import base64

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.infrastructure.database.models.attachment import Attachment
from app.infrastructure.database.models.audit import AuditLog
from app.infrastructure.database.models.identity import Tenant
from app.infrastructure.database.models.party import Party
from app.infrastructure.database.models.party_enterprise import PartyEnterpriseCredential


def _headers(
    *, user_id: int = 1, permissions: list[str] | None = None
) -> dict[str, str]:
    token = create_access_token(
        subject="enterprise-auditor",
        claims={
            "uid": user_id,
            "tenant_id": 1,
            "permissions": permissions or ["*"],
            "park_ids": [],
            "park_scope_mode": "ALL",
        },
    )
    return {"Authorization": f"Bearer {token}"}


def _party(client, headers: dict[str, str], name: str, **extra) -> int:
    response = client.post(
        "/api/v1/parties",
        headers=headers,
        json={"name": name, "party_type": "ORGANIZATION", **extra},
    )
    assert response.status_code == 200, response.text
    return int(response.json()["data"]["id"])


def _attachment(client, headers: dict[str, str], party_id: int) -> int:
    response = client.post(
        "/api/v1/attachments",
        headers=headers,
        json={
            "biz_type": "PARTY_ENTERPRISE",
            "biz_id": str(party_id),
            "filename": "business-license.txt",
            "content_type": "text/plain",
            "content_base64": base64.b64encode(b"synthetic business license evidence").decode(),
        },
    )
    assert response.status_code == 200, response.text
    return int(response.json()["data"]["id"])


def test_enterprise_profile_evidence_and_directory_journey(client, db_session: Session) -> None:
    headers = _headers()
    raw_identifier = "91310000MA1FL1Y37B"
    party_id = _party(client, headers, "完整画像企业", credit_code=raw_identifier)

    initial = client.get(
        f"/api/v1/parties/{party_id}/enterprise-profile", headers=headers
    )
    assert initial.status_code == 200, initial.text
    assert initial.json()["data"]["completeness_score"] == 15
    assert initial.json()["data"]["provider_status"] == "NOT_CONNECTED"

    saved = client.put(
        f"/api/v1/parties/{party_id}/enterprise-profile",
        headers=headers,
        json={
            "expected_lock_version": 0,
            "short_name": "完整企业",
            "legal_representative": "张负责人",
            "established_on": "2020-01-02",
            "registered_capital": "1000000.00",
            "capital_currency": "CNY",
            "registration_status": "ACTIVE",
            "registration_authority": "上海市市场监督管理局",
            "industry_code": "I65",
            "industry_name": "软件和信息技术服务业",
            "employee_size_band": "SMALL",
            "website": "https://example.cn/company",
            "business_scope": "软件开发与园区数字化服务",
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["lock_version"] == 1
    assert saved.json()["data"]["completeness_score"] == 70

    stale = client.put(
        f"/api/v1/parties/{party_id}/enterprise-profile",
        headers=headers,
        json={"expected_lock_version": 0, "short_name": "过期更新"},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "ENTERPRISE_PROFILE_CONFLICT"

    address = client.post(
        f"/api/v1/parties/{party_id}/addresses",
        headers=headers,
        json={
            "address_type": "REGISTERED",
            "country_code": "CN",
            "province": "上海市",
            "city": "上海市",
            "district": "浦东新区",
            "detail": "示例路 1 号",
            "is_primary": True,
        },
    )
    assert address.status_code == 200, address.text
    contact = client.post(
        f"/api/v1/parties/{party_id}/contacts",
        headers=headers,
        json={"name": "李经理", "phone": "13800138000", "is_primary": True},
    )
    assert contact.status_code == 200, contact.text

    attachment_id = _attachment(client, headers, party_id)
    credential = client.post(
        f"/api/v1/parties/{party_id}/enterprise-credentials",
        headers=headers,
        json={
            "attachment_id": attachment_id,
            "credential_type": "BUSINESS_LICENSE",
            "identifier": raw_identifier,
            "issuer": "上海市市场监督管理局",
            "issued_on": "2020-01-02",
        },
    )
    assert credential.status_code == 200, credential.text
    credential_data = credential.json()["data"]
    serialized = credential.text
    assert raw_identifier not in serialized
    assert "identifier_fingerprint" not in serialized
    assert credential_data["identifier_masked"].endswith("Y37B")
    persisted_credential = db_session.scalar(
        select(PartyEnterpriseCredential).where(
            PartyEnterpriseCredential.id == credential_data["id"]
        )
    )
    assert persisted_credential is not None
    assert raw_identifier not in persisted_credential.identifier_fingerprint
    assert len(persisted_credential.identifier_fingerprint) == 64

    unsupported_review = client.post(
        f"/api/v1/parties/{party_id}/enterprise-credentials/{credential_data['id']}/review",
        headers=headers,
        json={
            "expected_lock_version": credential_data["lock_version"],
            "verification_status": "EXTERNALLY_VERIFIED",
            "reason": "没有外部提供商证据",
        },
    )
    assert unsupported_review.status_code == 409
    assert unsupported_review.json()["code"] == "EXTERNAL_VERIFICATION_FORBIDDEN"

    reviewed = client.post(
        f"/api/v1/parties/{party_id}/enterprise-credentials/{credential_data['id']}/review",
        headers=headers,
        json={
            "expected_lock_version": credential_data["lock_version"],
            "verification_status": "LOCALLY_REVIEWED",
            "reason": "人工核验附件原件",
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["data"]["verification_status"] == "LOCALLY_REVIEWED"

    complete = client.get(
        f"/api/v1/parties/{party_id}/enterprise-profile", headers=headers
    )
    assert complete.status_code == 200
    assert complete.json()["data"]["completeness_score"] == 100
    assert complete.json()["data"]["missing_dimensions"] == []

    directory = client.get(
        "/api/v1/enterprise-parties",
        headers=headers,
        params={
            "keyword": "完整画像",
            "registration_status": "ACTIVE",
            "industry": "软件",
            "min_completeness": 100,
            "max_completeness": 100,
            "sort_by": "completeness",
        },
    )
    assert directory.status_code == 200, directory.text
    assert directory.json()["data"]["total"] == 1
    assert directory.json()["data"]["items"][0]["party_id"] == party_id

    audits = db_session.scalars(
        select(AuditLog).where(AuditLog.resource_type == "PARTY_ENTERPRISE_CREDENTIAL")
    ).all()
    assert audits
    assert raw_identifier not in " ".join(str(row.detail_json) for row in audits)


def test_enterprise_relationship_tag_and_risk_invariants(client, db_session: Session) -> None:
    headers = _headers()
    parent_id = _party(client, headers, "企业集团 A")
    child_id = _party(client, headers, "成员企业 B")

    relationship = client.post(
        f"/api/v1/parties/{parent_id}/enterprise-relationships",
        headers=headers,
        json={
            "target_party_id": child_id,
            "relationship_type": "PARENT_OF",
            "ownership_percent": "75.5",
        },
    )
    assert relationship.status_code == 200, relationship.text
    assert relationship.json()["data"]["ownership_percent"] == "75.50"

    cycle = client.post(
        f"/api/v1/parties/{child_id}/enterprise-relationships",
        headers=headers,
        json={"target_party_id": parent_id, "relationship_type": "PARENT_OF"},
    )
    assert cycle.status_code == 409
    assert cycle.json()["code"] == "ENTERPRISE_RELATIONSHIP_CYCLE"

    first_symmetric = client.post(
        f"/api/v1/parties/{parent_id}/enterprise-relationships",
        headers=headers,
        json={"target_party_id": child_id, "relationship_type": "BUSINESS_PARTNER"},
    )
    reverse_symmetric = client.post(
        f"/api/v1/parties/{child_id}/enterprise-relationships",
        headers=headers,
        json={"target_party_id": parent_id, "relationship_type": "BUSINESS_PARTNER"},
    )
    assert first_symmetric.status_code == reverse_symmetric.status_code == 200
    assert first_symmetric.json()["data"]["id"] == reverse_symmetric.json()["data"]["id"]

    tag = client.post(
        f"/api/v1/parties/{parent_id}/enterprise-tags",
        headers=headers,
        json={"name": " 专精特新 ", "tag_type": "QUALIFICATION"},
    )
    duplicate_tag = client.post(
        f"/api/v1/parties/{parent_id}/enterprise-tags",
        headers=headers,
        json={"name": "专精特新", "tag_type": "QUALIFICATION"},
    )
    assert tag.status_code == duplicate_tag.status_code == 200
    assert tag.json()["data"]["id"] == duplicate_tag.json()["data"]["id"]

    stale_tag = client.post(
        f"/api/v1/parties/{parent_id}/enterprise-tags/{tag.json()['data']['id']}/deactivate",
        headers=headers,
        json={"expected_lock_version": 99, "reason": "错误版本"},
    )
    assert stale_tag.status_code == 409

    signal = client.post(
        f"/api/v1/parties/{parent_id}/enterprise-risk-signals",
        headers=headers,
        json={
            "category": "COMPLIANCE",
            "severity": "CRITICAL",
            "summary": "人工发现的合规待核查事项",
            "source_reference": "manual-case-001",
        },
    )
    assert signal.status_code == 200, signal.text
    signal_id = signal.json()["data"]["id"]
    repeated = client.post(
        f"/api/v1/parties/{parent_id}/enterprise-risk-signals",
        headers=headers,
        json={
            "category": "COMPLIANCE",
            "severity": "CRITICAL",
            "summary": "重复提交不应新增",
            "source_reference": "manual-case-001",
        },
    )
    assert repeated.status_code == 200
    assert repeated.json()["data"]["id"] == signal_id

    risks = client.get(
        f"/api/v1/parties/{parent_id}/enterprise-risk-signals", headers=headers
    )
    assert risks.status_code == 200
    assert risks.json()["data"]["summary"]["overall_level"] == "CRITICAL"
    party = db_session.get(Party, parent_id)
    assert party is not None and party.risk_status == "NORMAL"

    resolved = client.post(
        f"/api/v1/parties/{parent_id}/enterprise-risk-signals/{signal_id}/resolve",
        headers=headers,
        json={"resolution_type": "MITIGATED", "reason": "已补齐合规材料"},
    )
    assert resolved.status_code == 200, resolved.text
    after = client.get(
        f"/api/v1/parties/{parent_id}/enterprise-risk-signals", headers=headers
    ).json()["data"]
    assert after["summary"]["overall_level"] == "NONE"
    assert after["summary"]["unresolved_count"] == 0


def test_enterprise_boundary_rejects_person_pollution_and_unproven_provider(client) -> None:
    headers = _headers()
    person = client.post(
        "/api/v1/parties",
        headers=headers,
        json={"name": "自然人主体", "party_type": "PERSON"},
    )
    assert person.status_code == 200
    person_id = person.json()["data"]["id"]
    profile = client.get(
        f"/api/v1/parties/{person_id}/enterprise-profile", headers=headers
    )
    assert profile.status_code == 400
    assert profile.json()["code"] == "ENTERPRISE_PROFILE_ORGANIZATION_REQUIRED"

    org_id = _party(client, headers, "边界测试企业")
    polluted = client.put(
        f"/api/v1/parties/{org_id}/enterprise-profile",
        headers=headers,
        json={"expected_lock_version": 0, "tenant_id": 999, "id_number": "310000000000000000"},
    )
    assert polluted.status_code == 422

    other_id = _party(client, headers, "外部关系目标")
    external = client.post(
        f"/api/v1/parties/{org_id}/enterprise-relationships",
        headers=headers,
        json={
            "target_party_id": other_id,
            "relationship_type": "PARENT_OF",
            "source_type": "EXTERNAL",
        },
    )
    assert external.status_code == 503
    assert external.json()["code"] == "PROVIDER_NOT_CONNECTED"

    bad_range = client.get(
        "/api/v1/enterprise-parties",
        headers=headers,
        params={"min_completeness": 80, "max_completeness": 20},
    )
    assert bad_range.status_code == 400
    assert bad_range.json()["code"] == "VALIDATION_ERROR"


def test_sensitive_enterprise_permissions_are_database_derived(client) -> None:
    """A forged JWT claim cannot grant credential or risk access absent a DB role grant."""

    admin_headers = _headers()
    party_id = _party(client, admin_headers, "敏感权限边界企业")
    user = client.post(
        "/api/v1/system/users",
        headers=admin_headers,
        json={"username": "party-sensitive-denied", "password": "Strong#12345"},
    )
    assert user.status_code == 200, user.text
    forged_headers = _headers(
        user_id=int(user.json()["data"]["id"]),
        permissions=["*", "party:credential_read", "party:risk_read"],
    )

    credentials = client.get(
        f"/api/v1/parties/{party_id}/enterprise-credentials", headers=forged_headers
    )
    risks = client.get(
        f"/api/v1/parties/{party_id}/enterprise-risk-signals", headers=forged_headers
    )
    for response in (credentials, risks):
        assert response.status_code == 403, response.text
        assert response.json()["code"] == "PERMISSION_DENIED"


def test_enterprise_evidence_rejects_cross_tenant_and_wrong_park_attachments(
    client, db_session: Session
) -> None:
    headers = _headers()
    park_a = client.post(
        "/api/v1/parks", headers=headers, json={"name": "企业证据园区甲"}
    ).json()["data"]
    park_b = client.post(
        "/api/v1/parks", headers=headers, json={"name": "企业证据园区乙"}
    ).json()["data"]
    party_id = _party(
        client,
        headers,
        "园区证据边界企业",
        initial_park_relation={"park_id": park_a["id"], "role_code": "LESSEE"},
    )
    wrong_park_attachment = client.post(
        "/api/v1/attachments",
        headers=headers,
        json={
            "biz_type": "PARTY_ENTERPRISE",
            "biz_id": str(party_id),
            "filename": "wrong-park.txt",
            "content_type": "text/plain",
            "content_base64": base64.b64encode(b"synthetic wrong park").decode(),
            "park_id": park_b["id"],
        },
    )
    assert wrong_park_attachment.status_code == 200, wrong_park_attachment.text
    wrong_park = client.post(
        f"/api/v1/parties/{party_id}/enterprise-credentials",
        headers=headers,
        json={
            "attachment_id": wrong_park_attachment.json()["data"]["id"],
            "credential_type": "BUSINESS_LICENSE",
        },
    )
    assert wrong_park.status_code == 403, wrong_park.text
    assert wrong_park.json()["code"] == "PARK_SCOPE_DENIED"

    foreign_tenant = Tenant(code="party-evidence-foreign", name="企业证据外租户")
    db_session.add(foreign_tenant)
    db_session.flush()
    foreign_party = Party(
        tenant_id=int(foreign_tenant.id),
        name="不可见的外租户企业",
        party_type="ORGANIZATION",
        status="ACTIVE",
        risk_status="NORMAL",
    )
    db_session.add(foreign_party)
    db_session.flush()
    foreign_attachment = Attachment(
        tenant_id=int(foreign_tenant.id),
        biz_type="PARTY_ENTERPRISE",
        biz_id=str(party_id),
        filename="foreign-tenant.txt",
        content_type="text/plain",
        size_bytes=9,
        object_key="party-enterprise/foreign-tenant-evidence",
        etag="synthetic",
        status="ACTIVE",
    )
    db_session.add(foreign_attachment)
    db_session.commit()
    cross_tenant_relationship = client.post(
        f"/api/v1/parties/{party_id}/enterprise-relationships",
        headers=headers,
        json={
            "target_party_id": int(foreign_party.id),
            "relationship_type": "BUSINESS_PARTNER",
        },
    )
    assert cross_tenant_relationship.status_code == 404, cross_tenant_relationship.text
    assert cross_tenant_relationship.json()["code"] == "PARTY_NOT_FOUND"
    cross_tenant = client.post(
        f"/api/v1/parties/{party_id}/enterprise-credentials",
        headers=headers,
        json={
            "attachment_id": int(foreign_attachment.id),
            "credential_type": "BUSINESS_LICENSE",
        },
    )
    assert cross_tenant.status_code == 404, cross_tenant.text
    assert cross_tenant.json()["code"] == "ATTACHMENT_NOT_FOUND"


def test_enterprise_child_ids_are_bound_to_the_party_path(client) -> None:
    headers = _headers()
    owner_id = _party(client, headers, "子资源归属企业甲")
    related_id = _party(client, headers, "子资源归属企业乙")
    unrelated_id = _party(client, headers, "子资源归属企业丙")

    relationship = client.post(
        f"/api/v1/parties/{owner_id}/enterprise-relationships",
        headers=headers,
        json={"target_party_id": related_id, "relationship_type": "BUSINESS_PARTNER"},
    ).json()["data"]
    tag = client.post(
        f"/api/v1/parties/{owner_id}/enterprise-tags",
        headers=headers,
        json={"name": "路径归属标签", "tag_type": "CUSTOM"},
    ).json()["data"]
    risk = client.post(
        f"/api/v1/parties/{owner_id}/enterprise-risk-signals",
        headers=headers,
        json={
            "category": "COMPLIANCE",
            "severity": "LOW",
            "summary": "路径归属风险",
            "source_reference": "path-owner-risk",
        },
    ).json()["data"]
    attachment_id = _attachment(client, headers, owner_id)
    credential = client.post(
        f"/api/v1/parties/{owner_id}/enterprise-credentials",
        headers=headers,
        json={"attachment_id": attachment_id, "credential_type": "BUSINESS_LICENSE"},
    ).json()["data"]

    attempts = (
        client.post(
            f"/api/v1/parties/{unrelated_id}/enterprise-relationships/{relationship['id']}/end",
            headers=headers,
            json={"expected_lock_version": relationship["lock_version"], "reason": "越权路径"},
        ),
        client.post(
            f"/api/v1/parties/{unrelated_id}/enterprise-tags/{tag['id']}/deactivate",
            headers=headers,
            json={"expected_lock_version": tag["lock_version"], "reason": "越权路径"},
        ),
        client.post(
            f"/api/v1/parties/{unrelated_id}/enterprise-risk-signals/{risk['id']}/resolve",
            headers=headers,
            json={"resolution_type": "MITIGATED", "reason": "越权路径"},
        ),
        client.post(
            f"/api/v1/parties/{unrelated_id}/enterprise-credentials/{credential['id']}/review",
            headers=headers,
            json={
                "expected_lock_version": credential["lock_version"],
                "verification_status": "LOCALLY_REVIEWED",
                "reason": "越权路径",
            },
        ),
    )
    expected_codes = (
        "ENTERPRISE_RELATIONSHIP_NOT_FOUND",
        "ENTERPRISE_TAG_NOT_FOUND",
        "ENTERPRISE_RISK_NOT_FOUND",
        "ENTERPRISE_CREDENTIAL_NOT_FOUND",
    )
    for response, code in zip(attempts, expected_codes, strict=True):
        assert response.status_code == 404, response.text
        assert response.json()["code"] == code

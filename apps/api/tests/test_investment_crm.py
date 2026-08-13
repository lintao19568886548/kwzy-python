"""Investment CRM V2 API behavior on isolated SQLite."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.errors import AppError
from app.core.security import create_access_token
from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.investment import Lead, LeadUnitLock
from app.infrastructure.database.models.identity import Tenant, User
from app.infrastructure.database.models.lease import LeaseContract
from app.infrastructure.database.models.park_property import Park, Unit
from app.infrastructure.database.models.party import Party
from app.modules.investment.application.lead_service import LeadService
from app.shared.tenant_context import ParkScopeMode, TenantContext


def _h(*, uid: int = 1, username: str = "admin", permissions: list[str] | None = None) -> dict:
    token = create_access_token(
        subject=username,
        claims={
            "uid": uid,
            "tenant_id": 1,
            "permissions": permissions or ["*"],
            "park_ids": [],
            "park_scope_mode": "ALL",
        },
    )
    return {"Authorization": f"Bearer {token}"}


def _park(client, headers: dict, name: str = "CRM园") -> int:
    response = client.post(
        "/api/v1/parks",
        headers=headers,
        json={"name": name, "address": "test"},
    )
    assert response.status_code == 200, response.text
    return int(response.json()["data"]["id"])


def _lead(client, headers: dict, park_id: int, *, name: str, phone: str, **extra) -> dict:
    response = client.post(
        "/api/v1/leads",
        headers=headers,
        json={"park_id": park_id, "name": name, "contact_phone": phone, **extra},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _unit(client, headers: dict, park_id: int, *, code: str, **extra) -> dict:
    response = client.post(
        "/api/v1/units",
        headers=headers,
        json={
            "park_id": park_id,
            "name": code,
            "code": code,
            "rentable_area": "100",
            "usage_type": "FACTORY",
            "base_rent_price": "20",
            "status": "VACANT",
            **extra,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_duplicate_override_activity_and_version_conflict(client) -> None:
    headers = _h()
    park_id = _park(client, headers)
    lead = _lead(client, headers, park_id, name="重复 企业", phone="138-0013-8000")

    duplicate = client.post(
        "/api/v1/leads",
        headers=headers,
        json={"park_id": park_id, "name": "重复   企业", "contact_phone": "13800138000"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "LEAD_DUPLICATE"
    assert duplicate.json()["data"]["candidates"][0]["id"] == lead["id"]

    overridden = client.post(
        "/api/v1/leads",
        headers=headers,
        json={
            "park_id": park_id,
            "name": "重复 企业",
            "contact_phone": "13800138000",
            "duplicate_override_reason": "同电话下的独立项目",
        },
    )
    assert overridden.status_code == 200, overridden.text

    activity = client.post(
        f"/api/v1/leads/{lead['id']}/activities",
        headers=headers,
        json={
            "expected_version": lead["lock_version"],
            "activity_type": "CALL",
            "content": "确认首次需求",
            "stage_to": "FOLLOWING",
            "next_follow_up_at": "2026-08-20T09:00:00",
        },
    )
    assert activity.status_code == 200, activity.text
    detail = activity.json()["data"]
    assert detail["status"] == "CONTACTING"
    assert detail["activities"][0]["activity_type"] == "CALL"
    assert detail["lock_version"] == lead["lock_version"] + 1

    stale = client.patch(
        f"/api/v1/leads/{lead['id']}",
        headers=headers,
        json={"expected_version": lead["lock_version"], "remark": "stale"},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "LEAD_VERSION_CONFLICT"

    invalid_jump = client.post(
        f"/api/v1/leads/{lead['id']}/activities",
        headers=headers,
        json={
            "expected_version": detail["lock_version"],
            "activity_type": "NEGOTIATION",
            "content": "非法跳阶",
            "stage_to": "NEGOTIATING",
        },
    )
    assert invalid_jump.status_code == 400
    assert invalid_jump.json()["code"] == "LEAD_STAGE_INVALID"


def test_public_claim_owner_scope_and_masking(client, db_session) -> None:
    admin = _h()
    park_id = _park(client, admin, "公海园")
    db_session.add(
        User(
            tenant_id=1,
            username="seller2",
            password_hash="not-used",
            real_name="销售二",
            status="ACTIVE",
        )
    )
    db_session.commit()
    seller_id = int(db_session.query(User).filter(User.username == "seller2").one().id)
    seller = _h(
        uid=seller_id,
        username="seller2",
        permissions=["lead:read", "lead:write", "lead:claim"],
    )

    private = _lead(client, admin, park_id, name="管理员私有", phone="13900139000")
    public = _lead(
        client,
        admin,
        park_id,
        name="公海客户",
        phone="13700137000",
        pool_status="PUBLIC",
    )

    listing = client.get("/api/v1/leads", headers=seller)
    assert listing.status_code == 200
    items = listing.json()["data"]["items"]
    assert all(item["id"] != private["id"] for item in items)
    public_row = next(item for item in items if item["id"] == public["id"])
    assert public_row["public_summary"] is True
    assert "****" in public_row["contact_phone"]

    claimed = client.post(
        f"/api/v1/leads/{public['id']}/claim",
        headers=seller,
        json={"expected_version": public["lock_version"]},
    )
    assert claimed.status_code == 200, claimed.text
    claimed_lead = claimed.json()["data"]
    assert claimed_lead["owner_user_id"] == seller_id
    assert claimed_lead["pool_status"] == "PRIVATE"
    assert claimed_lead["public_summary"] is False

    again = client.post(
        f"/api/v1/leads/{public['id']}/claim",
        headers=seller,
        json={"expected_version": claimed_lead["lock_version"]},
    )
    assert again.status_code == 409
    assert again.json()["code"] == "LEAD_ALREADY_CLAIMED"


def test_manager_assignment_and_merge_lineage(client, db_session) -> None:
    headers = _h()
    park_id = _park(client, headers, "合并园")
    db_session.add(
        User(
            tenant_id=1,
            username="seller3",
            password_hash="not-used",
            real_name="销售三",
            status="ACTIVE",
        )
    )
    db_session.commit()
    seller_id = int(db_session.query(User).filter(User.username == "seller3").one().id)

    source = _lead(client, headers, park_id, name="来源线索", phone="13600136000")
    target = _lead(client, headers, park_id, name="保留线索", phone="13500135000")
    assigned = client.post(
        f"/api/v1/leads/{target['id']}/assign",
        headers=headers,
        json={
            "expected_version": target["lock_version"],
            "owner_user_id": seller_id,
            "reason": "区域分配",
        },
    )
    assert assigned.status_code == 200, assigned.text
    target = assigned.json()["data"]

    merged = client.post(
        f"/api/v1/leads/{source['id']}/merge",
        headers=headers,
        json={
            "expected_version": source["lock_version"],
            "target_lead_id": target["id"],
            "target_expected_version": target["lock_version"],
            "reason": "确认同一机会",
        },
    )
    assert merged.status_code == 200, merged.text
    body = merged.json()["data"]
    assert body["source"]["status"] == "MERGED"
    assert body["source"]["merged_into_lead_id"] == target["id"]
    assert source["id"] in body["target"]["merged_sources"]
    assert body["target"]["assignment_events"][0]["to_owner_user_id"] == seller_id

    current = client.get("/api/v1/leads", headers=headers).json()["data"]["items"]
    assert all(item["id"] != source["id"] for item in current)


def test_tenant_and_park_scope_isolate_detail_list_summary_and_duplicates(client, db_session) -> None:
    admin = _h()
    allowed_park = _park(client, admin, "范围内园区")
    denied_park = _park(client, admin, "范围外园区")
    allowed = _lead(
        client,
        admin,
        allowed_park,
        name="范围内客户",
        phone="13800001001",
        pool_status="PUBLIC",
    )
    denied = _lead(
        client,
        admin,
        denied_park,
        name="范围外客户",
        phone="13800001002",
        pool_status="PUBLIC",
    )
    seller = User(
        tenant_id=1,
        username="scoped-seller",
        password_hash="not-used",
        real_name="范围销售",
        status="ACTIVE",
    )
    other_tenant = Tenant(code="crm-isolation", name="CRM隔离租户", status="ACTIVE")
    db_session.add_all([seller, other_tenant])
    db_session.flush()
    other_user = User(
        tenant_id=other_tenant.id,
        username="other-crm-admin",
        password_hash="not-used",
        real_name="其他租户管理员",
        status="ACTIVE",
    )
    other_park = Park(
        tenant_id=other_tenant.id,
        name="其他租户园区",
        address="isolated",
        status="ACTIVE",
    )
    db_session.add_all([other_user, other_park])
    db_session.commit()

    scoped = LeadService(
        db_session,
        TenantContext(
            tenant_id=1,
            user_id=int(seller.id),
            username=seller.username,
            permissions=["lead:read", "lead:write"],
            park_ids=[allowed_park],
            park_scope_mode=ParkScopeMode.LIST,
        ),
    )
    listing = scoped.list_leads()
    assert [row["id"] for row in listing["items"]] == [allowed["id"]]
    assert scoped.crm_summary()["counts"]["total"] == 1
    assert scoped.duplicate_candidates(
        {
            "park_id": allowed_park,
            "name": denied["name"],
            "contact_phone": denied["contact_phone"],
            "source_type": "MANUAL",
        }
    ) == []
    with pytest.raises(AppError, match="线索不存在"):
        scoped.get_lead(denied["id"])

    other_service = LeadService(
        db_session,
        TenantContext(
            tenant_id=int(other_tenant.id),
            user_id=int(other_user.id),
            username=other_user.username,
            permissions=["*"],
            park_scope_mode=ParkScopeMode.ALL,
        ),
    )
    foreign = other_service.create_lead(
        {
            "park_id": int(other_park.id),
            "name": "范围内客户",
            "contact_phone": "13800001001",
        }
    )
    tenant_one = LeadService(
        db_session,
        TenantContext(
            tenant_id=1,
            user_id=1,
            username="admin",
            permissions=["*"],
            park_scope_mode=ParkScopeMode.ALL,
        ),
    )
    assert foreign["id"] not in {row["id"] for row in tenant_one.list_leads()["items"]}
    assert all(
        row["id"] != foreign["id"]
        for row in tenant_one.duplicate_candidates(
            {
                "park_id": allowed_park,
                "name": foreign["name"],
                "contact_phone": foreign["contact_phone"],
                "source_type": "MANUAL",
            }
        )
    )
    with pytest.raises(AppError, match="线索不存在"):
        tenant_one.get_lead(foreign["id"])


def test_explainable_matching_lock_renew_release_and_expiry(client, db_session) -> None:
    headers = _h()
    park_id = _park(client, headers, "锁定园")
    other_park = _park(client, headers, "其他园")
    best = _unit(client, headers, park_id, code="BEST")
    expensive = _unit(
        client,
        headers,
        park_id,
        code="EXPENSIVE",
        rentable_area="140",
        usage_type="OFFICE",
        base_rent_price="50",
    )
    _unit(client, headers, other_park, code="FOREIGN")
    occupied = _unit(client, headers, park_id, code="OCCUPIED")
    occupied_model = db_session.get(Unit, occupied["id"])
    occupied_model.status = "OCCUPIED"
    occupied_model.used_area = 10
    db_session.commit()

    lead = _lead(
        client,
        headers,
        park_id,
        name="匹配客户",
        phone="13100131000",
        intent_area="100",
        desired_usage="FACTORY",
        budget_unit_price="20",
    )
    matches = client.get(f"/api/v1/leads/{lead['id']}/unit-matches", headers=headers)
    assert matches.status_code == 200, matches.text
    rows = matches.json()["data"]["items"]
    assert [row["unit_id"] for row in rows] == [best["id"], expensive["id"]]
    assert rows[0]["score"] == 100
    assert rows[0]["score_breakdown"]["area"]["score"] == 50

    acquired = client.post(
        f"/api/v1/leads/{lead['id']}/unit-locks",
        headers=headers,
        json={"expected_version": lead["lock_version"], "unit_id": best["id"]},
    )
    assert acquired.status_code == 200, acquired.text
    lock = acquired.json()["data"]
    db_session.expire_all()
    assert db_session.get(Unit, best["id"]).status == "RESERVED"

    other = _lead(client, headers, park_id, name="竞争客户", phone="13200132000")
    conflict = client.post(
        f"/api/v1/leads/{other['id']}/unit-locks",
        headers=headers,
        json={"expected_version": other["lock_version"], "unit_id": best["id"]},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "UNIT_ALREADY_LOCKED"

    renewed = client.post(
        f"/api/v1/leads/{lead['id']}/unit-locks/{lock['id']}/renew",
        headers=headers,
        json={"expected_version": lock["lock_version"], "duration_hours": 72},
    )
    assert renewed.status_code == 200, renewed.text
    lock = renewed.json()["data"]
    assert lock["lock_version"] == 2

    released = client.post(
        f"/api/v1/leads/{lead['id']}/unit-locks/{lock['id']}/release",
        headers=headers,
        json={"expected_version": lock["lock_version"]},
    )
    assert released.status_code == 200, released.text
    assert released.json()["data"]["status"] == "RELEASED"
    db_session.expire_all()
    assert db_session.get(Unit, best["id"]).status == "VACANT"

    reacquired = client.post(
        f"/api/v1/leads/{lead['id']}/unit-locks",
        headers=headers,
        json={
            "expected_version": acquired.json()["data"]["lead_lock_version"],
            "unit_id": best["id"],
        },
    )
    assert reacquired.status_code == 200, reacquired.text
    active = db_session.get(LeadUnitLock, reacquired.json()["data"]["id"])
    active.expires_at = utc_now() - timedelta(seconds=1)
    db_session.commit()
    swept = client.post(
        "/api/v1/crm/unit-locks/sweep",
        headers=headers,
        params={"park_id": park_id},
    )
    assert swept.status_code == 200, swept.text
    assert swept.json()["data"]["expired_count"] == 1
    db_session.expire_all()
    assert db_session.get(Unit, best["id"]).status == "VACANT"


def test_foreign_lock_blocks_independent_lease_activation(client, db_session) -> None:
    headers = _h()
    park_id = _park(client, headers, "激活锁园")
    unit = _unit(client, headers, park_id, code="LOCKED")
    lead = _lead(client, headers, park_id, name="锁定客户", phone="13300133000")
    lock = client.post(
        f"/api/v1/leads/{lead['id']}/unit-locks",
        headers=headers,
        json={"expected_version": lead["lock_version"], "unit_id": unit["id"]},
    )
    assert lock.status_code == 200, lock.text

    party = client.post(
        "/api/v1/parties",
        headers=headers,
        json={"name": "其他承租人", "party_type": "ORGANIZATION"},
    ).json()["data"]
    lease = client.post(
        "/api/v1/leases",
        headers=headers,
        json={
            "park_id": park_id,
            "party_id": party["id"],
            "start_date": "2026-09-01",
            "end_date": "2027-08-31",
            "units": [
                {"unit_id": unit["id"], "occupied_area": "80", "unit_rent_price": "20"}
            ],
        },
    ).json()["data"]
    assert client.post(f"/api/v1/leases/{lease['id']}/submit", headers=headers).status_code == 200
    activation = client.post(f"/api/v1/leases/{lease['id']}/activate", headers=headers)
    assert activation.status_code == 409
    assert activation.json()["code"] == "UNIT_ALREADY_LOCKED"
    lease_after = client.get(f"/api/v1/leases/{lease['id']}", headers=headers).json()["data"]
    assert lease_after["status"] == "PENDING_ACTIVE"
    db_session.expire_all()
    assert db_session.get(Unit, unit["id"]).status == "RESERVED"
    assert db_session.get(LeadUnitLock, lock.json()["data"]["id"]).status == "ACTIVE"


def test_funnel_reconciles_with_list_and_empty_range(client) -> None:
    headers = _h()
    park_id = _park(client, headers, "漏斗园")
    first = _lead(
        client,
        headers,
        park_id,
        name="漏斗新线索",
        phone="13400134000",
        source_type="MANUAL",
    )
    second = _lead(
        client,
        headers,
        park_id,
        name="漏斗跟进线索",
        phone="13500135001",
        source_type="IMPORT",
    )
    followed = client.post(
        f"/api/v1/leads/{second['id']}/activities",
        headers=headers,
        json={
            "expected_version": second["lock_version"],
            "activity_type": "CALL",
            "content": "首跟进",
            "stage_to": "CONTACTING",
        },
    )
    assert followed.status_code == 200, followed.text

    params = {"park_id": park_id}
    listing = client.get("/api/v1/leads", headers=headers, params=params).json()["data"]
    summary = client.get("/api/v1/crm/summary", headers=headers, params=params)
    assert summary.status_code == 200, summary.text
    metrics = summary.json()["data"]
    assert metrics["counts"]["total"] == listing["total"] == 2
    assert sum(metrics["stage_counts"].values()) == listing["total"]
    assert metrics["stage_counts"]["NEW"] == 1
    assert metrics["stage_counts"]["CONTACTING"] == 1
    assert metrics["average_first_follow_seconds"] is not None
    assert [row["source_type"] for row in metrics["source_breakdown"]] == ["IMPORT", "MANUAL"]

    board = client.get("/api/v1/crm/board", headers=headers, params=params).json()["data"]
    assert board["total"] == listing["total"]
    assert sum(column["count"] for column in board["columns"]) == listing["total"]

    empty = client.get(
        "/api/v1/crm/summary",
        headers=headers,
        params={"park_id": park_id, "created_from": "2099-01-01T00:00:00Z"},
    ).json()["data"]
    assert empty["counts"]["total"] == 0
    assert empty["conversion_rate"] == 0
    assert empty["average_first_follow_seconds"] is None


def test_conversion_failure_rolls_back_and_retry_succeeds(client, db_session) -> None:
    headers = _h()
    park_id = _park(client, headers, "转化回滚园")
    unit = _unit(client, headers, park_id, code="ROLLBACK")
    lead = _lead(client, headers, park_id, name="回滚客户", phone="13600136001")
    locked = client.post(
        f"/api/v1/leads/{lead['id']}/unit-locks",
        headers=headers,
        json={"expected_version": lead["lock_version"], "unit_id": unit["id"]},
    ).json()["data"]
    before_parties = db_session.query(Party).count()
    before_leases = db_session.query(LeaseContract).count()
    ctx = TenantContext(
        tenant_id=1,
        user_id=1,
        username="admin",
        permissions=["*"],
        park_scope_mode=ParkScopeMode.ALL,
    )
    service = LeadService(db_session, ctx)
    payload = {
        "expected_version": locked["lead_lock_version"],
        "unit_ids": [unit["id"]],
        "start_date": "2026-10-01",
        "end_date": "2027-09-30",
        "occupied_area": "80",
        "unit_rent_price": "20",
        "_test_fail_after_lease": True,
    }
    with pytest.raises(RuntimeError, match="injected conversion failure after lease"):
        service.convert_lead(lead["id"], payload)

    db_session.expire_all()
    assert db_session.query(Party).count() == before_parties
    assert db_session.query(LeaseContract).count() == before_leases
    stored_lead = db_session.get(Lead, lead["id"])
    assert stored_lead.status == "NEW"
    assert stored_lead.party_id is None
    assert stored_lead.lease_id is None
    stored_lock = db_session.get(LeadUnitLock, locked["id"])
    assert stored_lock.status == "ACTIVE"
    assert stored_lock.lease_id is None
    assert db_session.get(Unit, unit["id"]).status == "RESERVED"

    payload.pop("_test_fail_after_lease")
    retry = client.post(
        f"/api/v1/leads/{lead['id']}/convert",
        headers=headers,
        json=payload,
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["data"]["lead"]["status"] == "WON"
    idempotent_retry = client.post(
        f"/api/v1/leads/{lead['id']}/convert",
        headers=headers,
        json=payload,
    )
    assert idempotent_retry.status_code == 200, idempotent_retry.text
    assert (
        idempotent_retry.json()["data"]["lease"]["id"]
        == retry.json()["data"]["lease"]["id"]
    )
    assert db_session.query(Party).count() == before_parties + 1
    assert db_session.query(LeaseContract).count() == before_leases + 1


def test_overdue_recycle_is_idempotent(client, db_session) -> None:
    headers = _h()
    park_id = _park(client, headers, "回收园")
    lead = _lead(client, headers, park_id, name="应回收客户", phone="13700137001")
    stored = db_session.get(Lead, lead["id"])
    stored.recycle_due_at = utc_now() - timedelta(days=1)
    db_session.commit()

    first = client.post(
        f"/api/v1/leads/{lead['id']}/recycle",
        headers=headers,
        json={"expected_version": lead["lock_version"]},
    )
    assert first.status_code == 200, first.text
    recycled = first.json()["data"]
    assert recycled["pool_status"] == "PUBLIC"
    assert recycled["owner_user_id"] is None

    second = client.post(
        f"/api/v1/leads/{lead['id']}/recycle",
        headers=headers,
        json={"expected_version": recycled["lock_version"]},
    )
    assert second.status_code == 200, second.text
    detail = client.get(f"/api/v1/leads/{lead['id']}", headers=headers).json()["data"]
    recycle_events = [
        row for row in detail["assignment_events"] if row["event_type"] == "RECYCLE"
    ]
    assert len(recycle_events) == 1


def test_manager_stage_override_and_explicit_reopen(client) -> None:
    headers = _h()
    park_id = _park(client, headers, "阶段治理园")
    lead = _lead(client, headers, park_id, name="阶段客户", phone="13800138002")
    for stage, activity_type in [
        ("CONTACTING", "CALL"),
        ("VISITING", "VISIT"),
    ]:
        advanced = client.post(
            f"/api/v1/leads/{lead['id']}/activities",
            headers=headers,
            json={
                "expected_version": lead["lock_version"],
                "activity_type": activity_type,
                "content": f"推进到 {stage}",
                "stage_to": stage,
            },
        )
        assert advanced.status_code == 200, advanced.text
        lead = advanced.json()["data"]

    missing_reason = client.patch(
        f"/api/v1/leads/{lead['id']}",
        headers=headers,
        json={"expected_version": lead["lock_version"], "status": "CONTACTING"},
    )
    assert missing_reason.status_code == 400
    assert missing_reason.json()["code"] == "LEAD_STAGE_OVERRIDE_REQUIRED"

    rolled_back = client.patch(
        f"/api/v1/leads/{lead['id']}",
        headers=headers,
        json={
            "expected_version": lead["lock_version"],
            "status": "CONTACTING",
            "stage_reason": "客户调整了选址计划",
        },
    )
    assert rolled_back.status_code == 200, rolled_back.text
    lead = rolled_back.json()["data"]
    assert lead["status"] == "CONTACTING"

    lost = client.post(
        f"/api/v1/leads/{lead['id']}/lose",
        headers=headers,
        json={"expected_version": lead["lock_version"], "reason": "预算暂停"},
    )
    assert lost.status_code == 200, lost.text
    lead = lost.json()["data"]
    direct_patch = client.patch(
        f"/api/v1/leads/{lead['id']}",
        headers=headers,
        json={
            "expected_version": lead["lock_version"],
            "status": "CONTACTING",
            "stage_reason": "错误入口",
        },
    )
    assert direct_patch.status_code == 400
    reopened = client.post(
        f"/api/v1/leads/{lead['id']}/reopen",
        headers=headers,
        json={
            "expected_version": lead["lock_version"],
            "reason": "客户预算恢复",
            "target_status": "CONTACTING",
        },
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["data"]["status"] == "CONTACTING"
    assert reopened.json()["data"]["lost_reason"] is None

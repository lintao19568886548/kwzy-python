"""Application-level engagement journeys over the isolated SQLite test database."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.engagement import (
    EngagementActivity,
    EngagementActivityVersion,
    EngagementAnnouncement,
    EngagementAnnouncementVersion,
    EngagementPolicy,
    EngagementPolicyVersion,
    EngagementServiceCatalog,
    EngagementServiceVersion,
)
from app.infrastructure.database.models.facility_ops import (
    TenantServicePrincipal,
    TenantServicePrincipalPark,
)
from app.infrastructure.database.models.identity import User
from app.infrastructure.database.models.park_property import Park
from app.infrastructure.database.models.party import Party, PartyParkRelation, PartyRole
from app.infrastructure.database.models.party_enterprise import (
    PartyEnterpriseProfile,
    PartyEnterpriseTag,
)
from app.infrastructure.database.models.workflow import ApprovalRequest
from app.modules.engagement.application.service import EngagementService
from app.modules.identity.application.bootstrap import ensure_default_tenant
from app.shared.tenant_context import ParkScopeMode, TenantContext


def _ctx(tenant_id: int, user_id: int) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        username=f"engagement-{user_id}",
        permissions=["*"],
        park_scope_mode=ParkScopeMode.ALL,
    )


def _seed_principal(session: Session, *, suffix: str, create_park: bool = True) -> dict[str, int]:
    tenant = ensure_default_tenant(session)
    user = session.scalar(select(User).where(User.tenant_id == tenant.id, User.username == "admin"))
    assert user is not None
    if suffix != "primary":
        user = User(
            tenant_id=tenant.id,
            username=f"eng_{suffix}",
            password_hash="synthetic-not-login",
            real_name=f"参与用户{suffix}",
            status="ACTIVE",
            all_parks=True,
        )
        session.add(user)
        session.flush()
    park = session.scalar(select(Park).where(Park.tenant_id == tenant.id))
    if park is None or create_park:
        park = Park(tenant_id=tenant.id, name=f"参与园区{suffix}", status="ACTIVE")
        session.add(park)
        session.flush()
    party = Party(
        tenant_id=tenant.id,
        party_type="ORGANIZATION",
        name=f"参与企业{suffix}",
        credit_code=f"91310{uuid4().hex[:13].upper()}",
        status="ACTIVE",
        risk_status="NORMAL",
    )
    session.add(party)
    session.flush()
    role = PartyRole(
        tenant_id=tenant.id,
        party_id=party.id,
        role_code="TENANT",
        status="ACTIVE",
    )
    session.add(role)
    session.flush()
    session.add(
        PartyParkRelation(
            tenant_id=tenant.id,
            party_id=party.id,
            park_id=park.id,
            party_role_id=role.id,
            status="ACTIVE",
        )
    )
    principal = TenantServicePrincipal(
        tenant_id=tenant.id,
        user_id=user.id,
        party_id=party.id,
        status="ACTIVE",
        created_by=user.id,
    )
    session.add(principal)
    session.flush()
    session.add(
        TenantServicePrincipalPark(
            tenant_id=tenant.id,
            principal_id=principal.id,
            park_id=park.id,
        )
    )
    session.commit()
    return {
        "tenant_id": int(tenant.id),
        "user_id": int(user.id),
        "park_id": int(park.id),
        "party_id": int(party.id),
        "principal_id": int(principal.id),
    }


def _approve_exact(
    session: Session,
    *,
    biz_type: str,
    aggregate,
    version,
    user_id: int,
) -> None:  # type: ignore[no-untyped-def]
    approval = ApprovalRequest(
        tenant_id=aggregate.tenant_id,
        park_id=getattr(aggregate, "park_id", None),
        biz_type=biz_type,
        biz_id=EngagementService._approval_biz_id(aggregate.id, version),
        title=f"测试审批 {biz_type}",
        status="APPROVED",
        priority="MEDIUM",
        applicant_user_id=user_id,
        approver_user_id=user_id,
        submitted_at=utc_now(),
        completed_at=utc_now(),
        lock_version=1,
        compatibility_mode="NATIVE",
    )
    session.add(approval)
    session.flush()
    aggregate.status = "PENDING_APPROVAL"
    aggregate.approval_id = approval.id
    version.status = "SUBMITTED"
    version.approval_id = approval.id
    session.commit()


def test_policy_publication_matching_follow_and_consultation(db_session: Session) -> None:
    seed = _seed_principal(db_session, suffix="primary")
    db_session.add(
        PartyEnterpriseProfile(
            tenant_id=seed["tenant_id"],
            party_id=seed["party_id"],
            industry_code="IOT",
            employee_size_band="SMALL",
            registration_status="ACTIVE",
            provider_status="LOCAL_ONLY",
            lock_version=1,
        )
    )
    db_session.add(
        PartyEnterpriseTag(
            tenant_id=seed["tenant_id"],
            party_id=seed["party_id"],
            name="高新技术",
            normalized_name="HIGH_TECH",
            tag_type="QUALIFICATION",
            source_type="MANUAL",
            confidence=1,
            verification_status="LOCALLY_REVIEWED",
            status="ACTIVE",
            lock_version=1,
            created_by=seed["user_id"],
        )
    )
    db_session.commit()
    service = EngagementService(db_session, _ctx(seed["tenant_id"], seed["user_id"]))
    created = service.create_policy(
        {
            "park_id": seed["park_id"],
            "code": "POL_IOT",
            "title": "物联网企业扶持指引",
            "summary": "本地相关性提示，不替代政府资格认定。",
            "content_text": "园区本地政策正文。",
            "category": "INDUSTRY",
            "region_code": "CN-SH",
            "source_type": "LOCAL",
            "source_system": "KWZY",
            "source_identifier": "SYNTHETIC-POLICY-1",
            "source_publisher": "园区政策服务中心",
            "source_url": "https://policy.example.com/iot",
            "allowed_hosts": ["policy.example.com"],
            "source_published_at": utc_now(),
            "effective_on": utc_now().date(),
            "expires_on": (utc_now() + timedelta(days=90)).date(),
            "attachment_ids": [],
            "applicability": [
                {"field": "industry_code", "operator": "EQ", "values": ["IOT"]},
                {"field": "tag_code", "operator": "CONTAINS_ANY", "values": ["HIGH_TECH"]},
            ],
        }
    )
    policy = db_session.get(EngagementPolicy, created["id"])
    version = db_session.scalar(
        select(EngagementPolicyVersion).where(
            EngagementPolicyVersion.policy_id == created["id"],
            EngagementPolicyVersion.version == 1,
        )
    )
    assert policy is not None and version is not None
    _approve_exact(
        db_session,
        biz_type="ENGAGEMENT_POLICY",
        aggregate=policy,
        version=version,
        user_id=seed["user_id"],
    )
    published = service.publish_policy(created["id"], {"expected_version": 1})
    assert published["status"] == "PUBLISHED"
    matched = service.match_policy(created["id"], key="match-primary")
    matched_replay = service.match_policy(created["id"], key="match-primary")
    assert matched["local_relevance"] is True
    assert matched_replay == matched
    assert matched["official_eligibility"] == "NOT_DETERMINED"
    assert service.follow_policy(created["id"], active=True)["status"] == "ACTIVE"
    consultation = service.create_consultation(
        created["id"],
        {"park_id": seed["park_id"], "subject": "申报范围", "question": "是否适用？"},
        key="consult-primary",
    )
    replay = service.create_consultation(
        created["id"],
        {"park_id": seed["park_id"], "subject": "申报范围", "question": "是否适用？"},
        key="consult-primary",
    )
    assert consultation["id"] == replay["id"]
    other = _seed_principal(db_session, suffix="policy-other", create_park=False)
    other_service = EngagementService(
        db_session, _ctx(other["tenant_id"], other["user_id"])
    )
    with pytest.raises(AppError) as cross_party:
        other_service.create_consultation(
            created["id"],
            {"park_id": seed["park_id"], "subject": "申报范围", "question": "是否适用？"},
            key="consult-primary",
        )
    assert cross_party.value.code == "IDEMPOTENCY_CONFLICT"
    withdrawn = service.withdraw_policy(
        created["id"],
        {"expected_version": published["lock_version"], "reason": "合成本地撤回验收"},
        key="policy-withdraw-primary",
    )
    assert withdrawn["status"] == "WITHDRAWN"
    assert (
        service.withdraw_policy(
            created["id"],
            {"expected_version": published["lock_version"], "reason": "合成本地撤回验收"},
            key="policy-withdraw-primary",
        )["status"]
        == "WITHDRAWN"
    )


def test_service_case_lifecycle_uses_persisted_principal_and_feedback(db_session: Session) -> None:
    seed = _seed_principal(db_session, suffix="primary")
    service = EngagementService(db_session, _ctx(seed["tenant_id"], seed["user_id"]))
    catalog_data = service.create_service(
        {
            "park_id": seed["park_id"],
            "code": "SVC_ADVISORY",
            "title": "企业政策咨询",
            "description": "园区内部咨询服务。",
            "category": "ADVISORY",
            "provider_type": "INTERNAL",
            "provider_name": "园区企业服务中心",
            "provider_state": "LOCAL",
            "sla_hours": 24,
            "appointment_required": False,
            "eligibility": [],
            "evidence_rules": [],
            "price_amount": None,
            "currency": "CNY",
        }
    )
    catalog = db_session.get(EngagementServiceCatalog, catalog_data["id"])
    version = db_session.scalar(
        select(EngagementServiceVersion).where(
            EngagementServiceVersion.catalog_id == catalog_data["id"],
            EngagementServiceVersion.version == 1,
        )
    )
    assert catalog is not None and version is not None
    _approve_exact(
        db_session,
        biz_type="ENGAGEMENT_SERVICE",
        aggregate=catalog,
        version=version,
        user_id=seed["user_id"],
    )
    assert service.publish_service(catalog.id, {"expected_version": 1})["status"] == "PUBLISHED"
    case = service.create_case(
        {
            "catalog_id": catalog.id,
            "priority": "MEDIUM",
            "subject": "政策适用咨询",
            "description": "需要园区工作人员说明本地服务边界。",
            "contact_last4": "1234",
        },
        key="case-primary",
    )
    with pytest.raises(AppError) as foreign_party:
        service.create_case(
            {
                "catalog_id": catalog.id,
                "party_id": 99999999,
                "priority": "MEDIUM",
                "subject": "越权代办",
                "description": "不得为外部 Party 创建。",
                "contact_last4": None,
            },
            key="staff-on-behalf-foreign",
            staff_on_behalf=True,
        )
    assert foreign_party.value.status_code == 404
    sla = service.escalate_service_sla(
        due_at=utc_now() + timedelta(days=2), limit=10
    )
    assert sla["escalated"] == 1
    transitions = [
        ("ACCEPTED", {}),
        ("ASSIGNED", {"assigned_to": seed["user_id"]}),
        ("IN_PROGRESS", {}),
        ("RESULT_READY", {"result_summary": "本地咨询结果已形成"}),
    ]
    for expected, (target, extra) in enumerate(transitions, start=1):
        case = service.transition_case(
            case["id"],
            {"expected_version": expected, "target_status": target, **extra},
            key=f"case-{target.lower()}",
        )
    case = service.transition_case(
        case["id"],
        {"expected_version": 5, "target_status": "CONFIRMED"},
        key="case-confirmed",
        tenant_view=True,
    )
    assert case["status"] == "CONFIRMED"
    feedback = service.feedback_case(case["id"], {"score": 5, "comment": "处理清晰"})
    assert feedback["score"] == 5


def test_activity_capacity_waitlist_cancel_and_single_promotion(db_session: Session) -> None:
    first = _seed_principal(db_session, suffix="primary")
    second = _seed_principal(db_session, suffix="second", create_park=False)
    assert first["park_id"] == second["park_id"]
    first_service = EngagementService(db_session, _ctx(first["tenant_id"], first["user_id"]))
    now = utc_now()
    activity_data = first_service.create_activity(
        {
            "park_id": first["park_id"],
            "code": "ACT_DEMO",
            "title": "企业交流活动",
            "description": "容量与候补验收活动。",
            "location": "一号会议室",
            "starts_at": now + timedelta(hours=2),
            "ends_at": now + timedelta(hours=4),
            "registration_opens_at": now - timedelta(hours=1),
            "registration_closes_at": now + timedelta(hours=1),
            "capacity": 1,
            "attendee_rules": [],
            "audience": [],
            "attachment_ids": [],
            "cancellation_terms": "开始前可取消。",
        }
    )
    activity = db_session.get(EngagementActivity, activity_data["id"])
    version = db_session.scalar(
        select(EngagementActivityVersion).where(
            EngagementActivityVersion.activity_id == activity_data["id"],
            EngagementActivityVersion.version == 1,
        )
    )
    assert activity is not None and version is not None
    _approve_exact(
        db_session,
        biz_type="ENGAGEMENT_ACTIVITY",
        aggregate=activity,
        version=version,
        user_id=first["user_id"],
    )
    first_service.publish_activity(activity.id, {"expected_version": 1})
    first_registration = first_service.register_activity(
        activity.id, {"attendee_count": 1}, key="registration-first"
    )
    with pytest.raises(AppError) as cross_party:
        second_service = EngagementService(
            db_session, _ctx(second["tenant_id"], second["user_id"])
        )
        second_service.register_activity(
            activity.id, {"attendee_count": 1}, key="registration-first"
        )
    assert cross_party.value.code == "IDEMPOTENCY_CONFLICT"
    second_service = EngagementService(
        db_session, _ctx(second["tenant_id"], second["user_id"])
    )
    second_registration = second_service.register_activity(
        activity.id, {"attendee_count": 1}, key="registration-second"
    )
    assert first_registration["status"] == "CONFIRMED"
    assert second_registration["status"] == "WAITLISTED"
    cancelled = first_service.cancel_registration(
        first_registration["id"],
        {"expected_version": 1, "reason": "行程变化"},
        key="cancel-first",
    )
    assert cancelled["promoted_registration_id"] == second_registration["id"]
    promoted = second_service.list_registrations(tenant_view=True)[0]
    assert promoted["status"] == "CONFIRMED"
    checked_in = first_service.check_in(
        promoted["id"],
        {"expected_version": promoted["lock_version"], "evidence_note": "现场二维码核验"},
        key="checkin-promoted",
    )
    assert checked_in["status"] == "CHECKED_IN"
    assert second_service.feedback_activity(
        promoted["id"], {"score": 5, "comment": "活动有效"}
    )["score"] == 5
    activity_state = first_service.transition_activity(
        activity.id,
        {
            "expected_version": 2,
            "target_status": "REGISTRATION_CLOSED",
            "reason": "报名窗口已关闭",
        },
        key="activity-close-registration",
    )
    activity_state = first_service.transition_activity(
        activity.id,
        {
            "expected_version": activity_state["lock_version"],
            "target_status": "IN_PROGRESS",
            "reason": "活动开始",
        },
        key="activity-start",
    )
    activity_state = first_service.transition_activity(
        activity.id,
        {
            "expected_version": activity_state["lock_version"],
            "target_status": "COMPLETED",
            "reason": "活动完成",
        },
        key="activity-complete",
    )
    assert activity_state["status"] == "COMPLETED"


def test_announcement_frozen_audience_fanout_inbox_and_read(db_session: Session) -> None:
    first = _seed_principal(db_session, suffix="primary")
    second = _seed_principal(db_session, suffix="second", create_park=False)
    service = EngagementService(db_session, _ctx(first["tenant_id"], first["user_id"]))
    created = service.create_announcement(
        {
            "park_id": first["park_id"],
            "code": "ANN_WELCOME",
            "title": "园区企业服务公告",
            "content_text": "这是站内公告，不代表短信、邮件或微信已送达。",
            "priority": "IMPORTANT",
            "pin_from": None,
            "pin_to": None,
            "publish_at": utc_now(),
            "expires_at": utc_now() + timedelta(days=7),
            "attachment_ids": [],
            "audience": [{"type": "TENANT_PRINCIPAL", "ids": [], "codes": []}],
        }
    )
    announcement = db_session.get(EngagementAnnouncement, created["id"])
    version = db_session.scalar(
        select(EngagementAnnouncementVersion).where(
            EngagementAnnouncementVersion.announcement_id == created["id"],
            EngagementAnnouncementVersion.version == 1,
        )
    )
    assert announcement is not None and version is not None
    _approve_exact(
        db_session,
        biz_type="ENGAGEMENT_ANNOUNCEMENT",
        aggregate=announcement,
        version=version,
        user_id=first["user_id"],
    )
    published = service.publish_announcement(announcement.id, {"expected_version": 1})
    assert published["frozen_recipient_count"] == 2
    first_batch = service.fanout_announcements(limit=1)
    second_batch = service.fanout_announcements(limit=10)
    replay_batch = service.fanout_announcements(limit=10)
    assert first_batch == {
        "delivered": 1,
        "failed": 0,
        "channel": "IN_APP",
        "external_delivery": "NOT_CONNECTED",
        "production_contacted": False,
    }
    assert second_batch["delivered"] == 1
    assert replay_batch["delivered"] == replay_batch["failed"] == 0
    second_service = EngagementService(db_session, _ctx(second["tenant_id"], second["user_id"]))
    inbox = second_service.inbox()
    assert len(inbox) == 1
    assert inbox[0]["status"] == "DELIVERED"
    assert second_service.read_delivery(inbox[0]["delivery_id"])["status"] == "READ"
    withdrawn = service.withdraw_announcement(
        announcement.id,
        {"expected_version": published["lock_version"], "reason": "公告撤回验收"},
        key="announcement-withdraw",
    )
    assert withdrawn["status"] == "WITHDRAWN"


def test_policy_expiry_and_scheduled_announcement_are_idempotent(
    db_session: Session,
) -> None:
    seed = _seed_principal(db_session, suffix="primary")
    service = EngagementService(db_session, _ctx(seed["tenant_id"], seed["user_id"]))
    now = utc_now()
    policy_data = service.create_policy(
        {
            "park_id": seed["park_id"],
            "code": "POL_EXPIRED",
            "title": "已过有效期政策",
            "summary": None,
            "content_text": "仅用于本地到期事件验收。",
            "category": "GENERAL",
            "region_code": None,
            "source_type": "LOCAL",
            "source_system": "KWZY",
            "source_identifier": "SYNTHETIC-EXPIRED",
            "source_publisher": "园区",
            "source_url": None,
            "allowed_hosts": [],
            "source_published_at": now - timedelta(days=3),
            "effective_on": (now - timedelta(days=3)).date(),
            "expires_on": (now - timedelta(days=1)).date(),
            "attachment_ids": [],
            "applicability": [],
        }
    )
    policy = db_session.get(EngagementPolicy, policy_data["id"])
    policy_version = db_session.scalar(
        select(EngagementPolicyVersion).where(
            EngagementPolicyVersion.policy_id == policy_data["id"],
            EngagementPolicyVersion.version == 1,
        )
    )
    assert policy is not None and policy_version is not None
    _approve_exact(
        db_session,
        biz_type="ENGAGEMENT_POLICY",
        aggregate=policy,
        version=policy_version,
        user_id=seed["user_id"],
    )
    service.publish_policy(policy.id, {"expected_version": 1})
    expiry = service.expire_policies(due_on=now.date(), limit=10)
    assert expiry["expired"] == 1
    assert service.expire_policies(due_on=now.date(), limit=10)["expired"] == 0

    scheduled_data = service.create_announcement(
        {
            "park_id": seed["park_id"],
            "code": "ANN_SCHEDULED",
            "title": "定时公告",
            "content_text": "到点后才冻结受众并生成站内投递。",
            "priority": "NORMAL",
            "pin_from": None,
            "pin_to": None,
            "publish_at": now + timedelta(hours=1),
            "expires_at": now + timedelta(hours=2),
            "attachment_ids": [],
            "audience": [{"type": "TENANT_PRINCIPAL", "ids": [], "codes": []}],
        }
    )
    announcement = db_session.get(EngagementAnnouncement, scheduled_data["id"])
    announcement_version = db_session.scalar(
        select(EngagementAnnouncementVersion).where(
            EngagementAnnouncementVersion.announcement_id == scheduled_data["id"],
            EngagementAnnouncementVersion.version == 1,
        )
    )
    assert announcement is not None and announcement_version is not None
    _approve_exact(
        db_session,
        biz_type="ENGAGEMENT_ANNOUNCEMENT",
        aggregate=announcement,
        version=announcement_version,
        user_id=seed["user_id"],
    )
    scheduled = service.publish_announcement(announcement.id, {"expected_version": 1})
    assert scheduled["status"] == "SCHEDULED"
    assert scheduled["frozen_recipient_count"] == 0
    due = service.process_due_announcements(due_at=now + timedelta(minutes=90), limit=10)
    assert due["published"] == 1
    assert service.process_due_announcements(
        due_at=now + timedelta(minutes=90), limit=10
    )["published"] == 0
    expired = service.process_due_announcements(due_at=now + timedelta(hours=3), limit=10)
    assert expired["expired"] == 1

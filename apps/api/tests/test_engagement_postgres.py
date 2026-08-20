"""PostgreSQL 16 schema, isolation, and immutable-evidence tests for engagement."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.infrastructure.database.models.engagement import (
    EngagementActivity,
    EngagementActivityRegistration,
    EngagementActivityVersion,
    EngagementPolicy,
    EngagementPolicyEvent,
    EngagementPolicyVersion,
    EngagementServiceCase,
    EngagementServiceCatalog,
    EngagementServiceVersion,
)
from app.infrastructure.database.models.facility_ops import (
    TenantServicePrincipal,
    TenantServicePrincipalPark,
)
from app.infrastructure.database.models.identity import Tenant, User
from app.infrastructure.database.models.park_property import Park
from app.infrastructure.database.models.party import Party, PartyParkRelation, PartyRole
from app.modules.engagement.application.service import EngagementService
from app.shared.tenant_context import ParkScopeMode, TenantContext

pytestmark = pytest.mark.pg


def _url() -> str:
    value = os.environ.get("TEST_DATABASE_URL") or os.environ.get("POSTGRES_TEST_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL / POSTGRES_TEST_URL not set")
    parsed = make_url(value)
    if (
        parsed.get_backend_name() != "postgresql"
        or parsed.host not in {"127.0.0.1", "localhost"}
        or (parsed.database or "").lower() != "kwzy_party_test"
    ):
        pytest.fail("engagement acceptance requires disposable loopback PostgreSQL kwzy_party_test")
    return value


def _factory():
    engine = create_engine(_url(), pool_pre_ping=True)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _seed_two_tenants():
    _, Session = _factory()
    suffix = uuid4().hex[:10]
    with Session() as session:
        first = Tenant(code=f"eng-a-{suffix}", name="参与治理租户A", status="ACTIVE")
        second = Tenant(code=f"eng-b-{suffix}", name="参与治理租户B", status="ACTIVE")
        session.add_all([first, second])
        session.flush()
        first_park = Park(tenant_id=first.id, name=f"参与园区A-{suffix}", status="ACTIVE")
        second_park = Park(tenant_id=second.id, name=f"参与园区B-{suffix}", status="ACTIVE")
        session.add_all([first_park, second_park])
        session.commit()
        return int(first.id), int(first_park.id), int(second.id), int(second_park.id)


def _seed_concurrency_scope() -> dict[str, object]:
    _, Session = _factory()
    suffix = uuid4().hex[:10]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with Session() as session:
        tenant = Tenant(code=f"eng-race-{suffix}", name="参与并发租户", status="ACTIVE")
        session.add(tenant)
        session.flush()
        park = Park(tenant_id=tenant.id, name=f"参与并发园区-{suffix}", status="ACTIVE")
        session.add(park)
        session.flush()
        user_ids: list[int] = []
        party_ids: list[int] = []
        for index in range(2):
            user = User(
                tenant_id=tenant.id,
                username=f"eng-race-{index}-{suffix}",
                password_hash="synthetic-not-login",
                real_name=f"并发参与人{index}",
                status="ACTIVE",
                all_parks=True,
            )
            session.add(user)
            session.flush()
            party = Party(
                tenant_id=tenant.id,
                party_type="ORGANIZATION",
                name=f"并发企业{index}",
                credit_code=f"91310{uuid4().hex[:13].upper()}",
                status="ACTIVE",
                risk_status="NORMAL",
            )
            session.add(party)
            session.flush()
            party_role = PartyRole(
                tenant_id=tenant.id,
                party_id=party.id,
                role_code="TENANT",
                status="ACTIVE",
            )
            session.add(party_role)
            session.flush()
            session.add(
                PartyParkRelation(
                    tenant_id=tenant.id,
                    party_id=party.id,
                    park_id=park.id,
                    party_role_id=party_role.id,
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
            user_ids.append(int(user.id))
            party_ids.append(int(party.id))

        activity = EngagementActivity(
            tenant_id=tenant.id,
            park_id=park.id,
            code=f"ACT_{suffix.upper()}",
            status="PUBLISHED",
            current_version=1,
            published_version=1,
            lock_version=1,
            created_by=user_ids[0],
        )
        session.add(activity)
        session.flush()
        activity_version = EngagementActivityVersion(
            tenant_id=tenant.id,
            activity_id=activity.id,
            version=1,
            status="PUBLISHED",
            title="最后席位并发活动",
            description="PostgreSQL 16 行锁验收",
            location="并发会议室",
            starts_at=now + timedelta(hours=3),
            ends_at=now + timedelta(hours=4),
            registration_opens_at=now - timedelta(hours=1),
            registration_closes_at=now + timedelta(hours=1),
            capacity=1,
            confirmed_count=0,
            waitlist_count=0,
            attendee_rules_json=[],
            audience_json=[],
            attachments_json=[],
            cancellation_terms="开始前可取消",
            checksum="b" * 64,
            created_by=user_ids[0],
            published_at=now,
        )
        session.add(activity_version)

        catalog = EngagementServiceCatalog(
            tenant_id=tenant.id,
            park_id=park.id,
            code=f"SVC_{suffix.upper()}",
            status="PUBLISHED",
            current_version=1,
            published_version=1,
            lock_version=1,
            created_by=user_ids[0],
        )
        session.add(catalog)
        session.flush()
        service_version = EngagementServiceVersion(
            tenant_id=tenant.id,
            catalog_id=catalog.id,
            version=1,
            status="PUBLISHED",
            title="并发预约服务",
            description="本地预约并发验收",
            category="ADVISORY",
            provider_type="INTERNAL",
            provider_name="园区服务中心",
            provider_state="LOCAL",
            sla_hours=24,
            appointment_required=True,
            eligibility_json=[],
            evidence_rules_json=[],
            price_amount=None,
            currency="CNY",
            checksum="c" * 64,
            created_by=user_ids[0],
            published_at=now,
        )
        session.add(service_version)
        session.flush()
        case = EngagementServiceCase(
            tenant_id=tenant.id,
            park_id=park.id,
            catalog_id=catalog.id,
            service_version_id=service_version.id,
            party_id=party_ids[0],
            principal_id=None,
            case_no=f"SC-RACE-{suffix.upper()}",
            status="ASSIGNED",
            priority="MEDIUM",
            subject="并发预约",
            description="两个操作者竞争同一案件版本",
            assigned_to=user_ids[0],
            sla_due_at=now + timedelta(days=1),
            idempotency_key=f"case-race-{suffix}",
            payload_hash="d" * 64,
            lock_version=1,
            created_by=user_ids[0],
        )
        session.add(case)
        session.commit()
        return {
            "tenant_id": int(tenant.id),
            "park_id": int(park.id),
            "user_ids": user_ids,
            "activity_id": int(activity.id),
            "activity_version_id": int(activity_version.id),
            "case_id": int(case.id),
        }


def _ctx(scope: dict[str, object], user_id: int) -> TenantContext:
    return TenantContext(
        tenant_id=int(scope["tenant_id"]),
        user_id=user_id,
        username=f"engagement-pg-{user_id}",
        permissions=["*"],
        park_scope_mode=ParkScopeMode.ALL,
    )


def test_engagement_schema_has_unique_head_constraints_indexes_and_guards() -> None:
    engine, _ = _factory()
    inspector = inspect(engine)
    engagement_tables = {
        name for name in inspector.get_table_names() if name.startswith("engagement_")
    }
    assert len(engagement_tables) == 20
    assert {
        "engagement_policies",
        "engagement_policy_versions",
        "engagement_service_cases",
        "engagement_activity_registrations",
        "engagement_announcement_deliveries",
        "engagement_migration_runs",
    } <= engagement_tables
    assert {item["name"] for item in inspector.get_unique_constraints("business_events")} >= {
        "uk_business_event_tenant_id"
    }
    assert {item["name"] for item in inspector.get_unique_constraints("in_app_notifications")} >= {
        "uk_in_app_notification_tenant_id"
    }
    assert {
        item["name"] for item in inspector.get_check_constraints("engagement_activity_versions")
    } >= {
        "ck_eng_activity_capacity",
        "ck_eng_activity_confirmed",
        "ck_eng_activity_schedule",
    }
    assert {item["name"] for item in inspector.get_indexes("engagement_service_cases")} >= {
        "ix_eng_service_case_scope"
    }
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "e7b24f0a1c09"
        )
        trigger_count = connection.execute(
            text(
                """
                SELECT count(*)
                FROM pg_trigger
                WHERE NOT tgisinternal
                  AND tgname LIKE 'trg_engagement_%'
                """
            )
        ).scalar_one()
        assert trigger_count == 7
    engine.dispose()


def test_composite_tenant_park_reference_rejects_cross_boundary_insert() -> None:
    first_tenant, _, _, second_park = _seed_two_tenants()
    _, Session = _factory()
    with Session() as session:
        session.add(
            EngagementPolicy(
                tenant_id=first_tenant,
                park_id=second_park,
                code=f"POL_{uuid4().hex[:12].upper()}",
                status="DRAFT",
                current_version=1,
                lock_version=1,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_submitted_versions_and_events_are_database_immutable() -> None:
    tenant_id, park_id, _, _ = _seed_two_tenants()
    _, Session = _factory()
    suffix = uuid4().hex[:12].upper()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today = now.date()
    with Session() as session:
        policy = EngagementPolicy(
            tenant_id=tenant_id,
            park_id=park_id,
            code=f"POL_{suffix}",
            status="PENDING_APPROVAL",
            current_version=1,
            lock_version=1,
        )
        session.add(policy)
        session.flush()
        version = EngagementPolicyVersion(
            tenant_id=tenant_id,
            policy_id=policy.id,
            version=1,
            status="SUBMITTED",
            title="不可变政策版本",
            summary="测试摘要",
            content_text="提交后的正文不得被覆盖。",
            category="INDUSTRY",
            region_code="CN-SH",
            source_type="LOCAL",
            source_system="SYNTHETIC_TEST",
            source_identifier=suffix,
            source_publisher="测试发布方",
            source_url=None,
            source_published_at=now,
            effective_on=today,
            expires_on=today + timedelta(days=30),
            attachments_json=[],
            applicability_json=[],
            checksum="a" * 64,
        )
        event = EngagementPolicyEvent(
            tenant_id=tenant_id,
            policy_id=policy.id,
            version=1,
            event_type="SUBMITTED",
            reason="提交审批",
            detail_json={"checksum": "a" * 64},
            idempotency_key=f"event-{suffix}",
            occurred_at=now,
        )
        session.add_all([version, event])
        session.commit()
        version_id = int(version.id)
        event_id = int(event.id)

    with Session() as session:
        version = session.get(EngagementPolicyVersion, version_id)
        assert version is not None
        version.title = "试图覆盖已提交版本"
        with pytest.raises(DBAPIError, match="immutable"):
            session.commit()

    with Session() as session:
        event = session.get(EngagementPolicyEvent, event_id)
        assert event is not None
        event.reason = "试图修改历史事件"
        with pytest.raises(DBAPIError, match="append-only"):
            session.commit()


def test_last_seat_registration_is_serialized_without_overbooking() -> None:
    scope = _seed_concurrency_scope()
    _, Session = _factory()
    barrier = Barrier(2)

    def register(index: int) -> str:
        with Session() as session:
            service = EngagementService(
                session, _ctx(scope, int(scope["user_ids"][index]))  # type: ignore[index]
            )
            barrier.wait(timeout=10)
            result = service.register_activity(
                int(scope["activity_id"]),
                {"attendee_count": 1},
                key=f"pg-last-seat-{uuid4().hex}",
            )
            return str(result["status"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = sorted(executor.map(register, range(2)))
    assert statuses == ["CONFIRMED", "WAITLISTED"]
    with Session() as session:
        version = session.get(
            EngagementActivityVersion, int(scope["activity_version_id"])
        )
        assert version is not None
        assert int(version.confirmed_count) == 1
        registrations = list(
            session.query(EngagementActivityRegistration)
            .filter(
                EngagementActivityRegistration.tenant_id == int(scope["tenant_id"]),
                EngagementActivityRegistration.activity_id == int(scope["activity_id"]),
            )
            .all()
        )
        assert sum(
            int(item.attendee_count) for item in registrations if item.status == "CONFIRMED"
        ) == 1


def test_concurrent_case_appointment_accepts_one_expected_version() -> None:
    scope = _seed_concurrency_scope()
    _, Session = _factory()
    barrier = Barrier(2)
    slots = [
        datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1),
        datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=2),
    ]

    def appoint(index: int) -> str:
        with Session() as session:
            service = EngagementService(
                session, _ctx(scope, int(scope["user_ids"][index]))  # type: ignore[index]
            )
            barrier.wait(timeout=10)
            try:
                service.transition_case(
                    int(scope["case_id"]),
                    {
                        "expected_version": 1,
                        "target_status": "APPOINTED",
                        "appointment_at": slots[index],
                    },
                    key=f"pg-appointment-{index}-{uuid4().hex}",
                )
            except AppError as exc:
                return exc.code
            return "SUCCEEDED"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = sorted(executor.map(appoint, range(2)))
    assert results == ["SUCCEEDED", "VERSION_CONFLICT"]
    with Session() as session:
        row = session.get(EngagementServiceCase, int(scope["case_id"]))
        assert row is not None
        assert row.status == "APPOINTED"
        assert int(row.lock_version) == 2
        assert row.appointment_at in slots

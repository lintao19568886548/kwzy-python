"""PostgreSQL concurrency acceptance for Investment CRM V2."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.investment import (
    Lead,
    LeadActivity,
    LeadAssignmentRuleVersion,
    LeadChannelInboxEvent,
    LeadIntentApplication,
    LeadIntentUnit,
    LeadIntentVersion,
    LeadUnitLock,
    LeadViewing,
)
from app.infrastructure.database.models.lease import LeaseContract
from app.infrastructure.database.models.park_property import Unit
from app.infrastructure.database.models.workflow import ApprovalRequest
from app.modules.identity.application.bootstrap import ensure_default_tenant
from app.modules.investment.application.assignment_service import AssignmentRuleService
from app.modules.investment.application.channel_service import ChannelService, PublicChannelIntake
from app.modules.investment.application.lead_service import LeadService
from app.modules.investment.application.viewing_service import ViewingService
from app.modules.lease.application.lease_service import LeaseService
from app.modules.park_property.application.park_service import ParkService
from app.modules.park_property.application.spatial_service import SpatialService
from app.modules.park_property.application.unit_service import UnitService
from app.modules.party.application.party_service import PartyService
from app.shared.tenant_context import ParkScopeMode, TenantContext

pytestmark = pytest.mark.pg


def _require_pg_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("POSTGRES_TEST_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL / POSTGRES_TEST_URL not set")
    if not url.startswith("postgresql") or (
        "127.0.0.1" not in url and "localhost" not in url
    ):
        pytest.fail("CRM concurrency tests require localhost PostgreSQL")
    if "kwzy_party_test" not in url:
        pytest.fail("database name must include kwzy_party_test")
    return url


def _factory(url: str):
    engine = create_engine(url, pool_pre_ping=True, pool_size=8, max_overflow=4)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _ctx(tenant_id: int, *, user_id: int = 1) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        username=f"crm-pg-{user_id}",
        permissions=["*"],
        park_scope_mode=ParkScopeMode.ALL,
    )


def _approved_intent(
    session, *, tenant_id: int, park_id: int, lead_id: int, unit_id: int
) -> int:
    unit = session.get(Unit, unit_id)
    assert unit is not None
    application = LeadIntentApplication(
        tenant_id=tenant_id,
        park_id=park_id,
        lead_id=lead_id,
        status="APPROVED",
        current_version=1,
        lock_version=1,
        submitted_at=utc_now(),
        created_by=1,
        updated_by=1,
    )
    session.add(application)
    session.flush()
    today = utc_now().date()
    version = LeadIntentVersion(
        tenant_id=tenant_id,
        application_id=int(application.id),
        version=1,
        starts_on=today,
        ends_on=today + timedelta(days=365),
        valid_until=utc_now() + timedelta(days=30),
        proposed_unit_price=Decimal("1.00"),
        currency="CNY",
        checksum=f"pg-approved-{application.id}-{uuid4().hex}",
        created_by=1,
    )
    session.add(version)
    session.flush()
    session.add(
        LeadIntentUnit(
            tenant_id=tenant_id,
            intent_version_id=int(version.id),
            unit_id=unit_id,
            unit_version=int(unit.version_no),
            requested_area=Decimal(str(unit.rentable_area)),
        )
    )
    approval = ApprovalRequest(
        tenant_id=tenant_id,
        park_id=park_id,
        biz_type="LEAD_INTENT",
        biz_id=str(application.id),
        title="PostgreSQL 并发测试批准意向",
        status="APPROVED",
        priority="HIGH",
        applicant_user_id=1,
        approver_user_id=1,
        submitted_at=utc_now(),
        completed_at=utc_now(),
        lock_version=1,
        compatibility_mode="NATIVE",
    )
    session.add(approval)
    session.flush()
    application.approval_request_id = int(approval.id)
    session.commit()
    return int(application.id)


def _seed(Session) -> dict[str, int]:
    suffix = uuid4().hex[:10].upper()
    with Session() as session:
        tenant_id = int(ensure_default_tenant(session).id)
        session.commit()
        ctx = _ctx(tenant_id)
        park = ParkService(session, ctx).create_park({"name": f"CRM并发园-{suffix}"})
        building = SpatialService(session, ctx).create(
            {
                "park_id": park["id"],
                "code": f"B-{suffix}",
                "name": f"CRM并发楼-{suffix}",
                "node_type": "BUILDING",
            }
        )
        unit = UnitService(session, ctx).create_unit(
            {
                "park_id": park["id"],
                "building_id": building["id"],
                "code": f"U-{suffix}",
                "name": f"CRM并发单元-{suffix}",
                "rentable_area": "100",
            }
        )
        first = LeadService(session, ctx).create_lead(
            {
                "park_id": park["id"],
                "name": f"并发线索甲-{suffix}",
                "contact_phone": f"138{suffix[:8]}",
            }
        )
        second = LeadService(session, ctx).create_lead(
            {
                "park_id": park["id"],
                "name": f"并发线索乙-{suffix}",
                "contact_phone": f"139{suffix[:8]}",
            }
        )
        public = LeadService(session, ctx).create_lead(
            {
                "park_id": park["id"],
                "name": f"并发公海-{suffix}",
                "contact_phone": f"137{suffix[:8]}",
                "pool_status": "PUBLIC",
            }
        )
        first_intent_id = _approved_intent(
            session,
            tenant_id=tenant_id,
            park_id=int(park["id"]),
            lead_id=int(first["id"]),
            unit_id=int(unit["id"]),
        )
        second_intent_id = _approved_intent(
            session,
            tenant_id=tenant_id,
            park_id=int(park["id"]),
            lead_id=int(second["id"]),
            unit_id=int(unit["id"]),
        )
        return {
            "tenant_id": tenant_id,
            "park_id": int(park["id"]),
            "unit_id": int(unit["id"]),
            "first_id": int(first["id"]),
            "first_version": int(first["lock_version"]),
            "first_intent_id": first_intent_id,
            "second_id": int(second["id"]),
            "second_version": int(second["lock_version"]),
            "second_intent_id": second_intent_id,
            "public_id": int(public["id"]),
            "public_version": int(public["lock_version"]),
        }


def test_pg_concurrent_unit_lock_has_one_winner() -> None:
    engine, Session = _factory(_require_pg_url())
    seed = _seed(Session)
    barrier = threading.Barrier(2)

    def acquire(lead_id: int, version: int) -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                LeadService(session, _ctx(seed["tenant_id"])).acquire_unit_lock(
                    lead_id,
                    unit_id=seed["unit_id"],
                    expected_version=version,
                    intent_id=(
                        seed["first_intent_id"]
                        if lead_id == seed["first_id"]
                        else seed["second_intent_id"]
                    ),
                )
                return ("ok", None)
            except AppError as exc:
                session.rollback()
                return ("err", exc.code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda args: acquire(*args),
                [
                    (seed["first_id"], seed["first_version"]),
                    (seed["second_id"], seed["second_version"]),
                ],
            )
        )
    assert sorted(state for state, _ in results) == ["err", "ok"], results
    assert [code for state, code in results if state == "err"] == ["UNIT_ALREADY_LOCKED"]
    with Session() as session:
        active = session.scalar(
            select(func.count()).select_from(LeadUnitLock).where(
                LeadUnitLock.tenant_id == seed["tenant_id"],
                LeadUnitLock.unit_id == seed["unit_id"],
                LeadUnitLock.status == "ACTIVE",
            )
        )
        unit = session.get(Unit, seed["unit_id"])
        assert int(active or 0) == 1
        assert unit.status == "RESERVED"
        assert Decimal(str(unit.used_area or 0)) == Decimal("0")
    engine.dispose()


def test_pg_concurrent_public_claim_has_one_winner() -> None:
    engine, Session = _factory(_require_pg_url())
    seed = _seed(Session)
    barrier = threading.Barrier(2)

    def claim(user_id: int) -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                LeadService(session, _ctx(seed["tenant_id"], user_id=user_id)).claim_lead(
                    seed["public_id"], expected_version=seed["public_version"]
                )
                return ("ok", None)
            except AppError as exc:
                session.rollback()
                return ("err", exc.code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, [1, 1]))
    assert sorted(state for state, _ in results) == ["err", "ok"], results
    assert [code for state, code in results if state == "err"] == ["LEAD_ALREADY_CLAIMED"]
    with Session() as session:
        lead = session.get(Lead, seed["public_id"])
        assert lead.pool_status == "PRIVATE"
        assert lead.owner_user_id == 1
        assert lead.lock_version == seed["public_version"] + 1
    engine.dispose()


def test_pg_concurrent_assignment_rule_publish_has_one_winner() -> None:
    engine, Session = _factory(_require_pg_url())
    seed = _seed(Session)
    with Session() as session:
        rule = AssignmentRuleService(session, _ctx(seed["tenant_id"])).create_rule(
            {
                "park_id": seed["park_id"],
                "code": f"PG_PUBLISH_{uuid4().hex[:12].upper()}",
                "name": "PostgreSQL 双发布规则",
                "trigger": "MANUAL_CREATE",
                "members": [{"user_id": 1, "capacity": 100, "member_order": 1}],
            }
        )
        rule_id = int(rule["id"])
        expected = int(rule["lock_version"])
    barrier = threading.Barrier(2)

    def publish() -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                AssignmentRuleService(session, _ctx(seed["tenant_id"])).publish(
                    rule_id, expected_lock_version=expected
                )
                return ("ok", None)
            except AppError as exc:
                session.rollback()
                return ("err", exc.code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: publish(), range(2)))
    assert sorted(state for state, _ in results) == ["err", "ok"], results
    assert [code for state, code in results if state == "err"] == ["VERSION_CONFLICT"]
    with Session() as session:
        published = int(
            session.scalar(
                select(func.count()).select_from(LeadAssignmentRuleVersion).where(
                    LeadAssignmentRuleVersion.rule_id == rule_id,
                    LeadAssignmentRuleVersion.status == "PUBLISHED",
                )
            )
            or 0
        )
        assert published == 1
    engine.dispose()


def test_pg_concurrent_viewing_completion_writes_one_visit() -> None:
    engine, Session = _factory(_require_pg_url())
    seed = _seed(Session)
    start = utc_now() + timedelta(days=1)
    with Session() as session:
        service = ViewingService(session, _ctx(seed["tenant_id"]))
        viewing = service.create(
            seed["first_id"],
            {
                "starts_at": start,
                "ends_at": start + timedelta(hours=1),
                "unit_ids": [seed["unit_id"]],
                "owner_user_id": 1,
                "visitor_count": 1,
            },
        )
        confirmed = service.transition(
            int(viewing["id"]),
            {"expected_version": int(viewing["lock_version"]), "status": "CONFIRMED"},
        )
        viewing_id = int(viewing["id"])
        expected = int(confirmed["lock_version"])
    barrier = threading.Barrier(2)

    def complete(index: int) -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                ViewingService(session, _ctx(seed["tenant_id"])).transition(
                    viewing_id,
                    {
                        "expected_version": expected,
                        "status": "COMPLETED",
                        "outcome": f"并发完成结果 {index}",
                        "idempotency_key": f"pg-viewing-complete-{viewing_id}-{index}",
                    },
                )
                return ("ok", None)
            except AppError as exc:
                session.rollback()
                return ("err", exc.code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(complete, range(2)))
    assert sorted(state for state, _ in results) == ["err", "ok"], results
    assert [code for state, code in results if state == "err"] == ["VERSION_CONFLICT"]
    with Session() as session:
        row = session.get(LeadViewing, viewing_id)
        visits = int(
            session.scalar(
                select(func.count()).select_from(LeadActivity).where(
                    LeadActivity.lead_id == seed["first_id"],
                    LeadActivity.activity_type == "VISIT",
                )
            )
            or 0
        )
        assert row is not None and row.status == "COMPLETED"
        assert visits == 1
    engine.dispose()


def test_pg_concurrent_signed_channel_event_is_exactly_once() -> None:
    engine, Session = _factory(_require_pg_url())
    seed = _seed(Session)
    key_ref = f"KWZY_PG_CHANNEL_{uuid4().hex.upper()}"
    secret = "postgres-local-channel-secret"
    previous = os.environ.get(key_ref)
    os.environ[key_ref] = secret
    try:
        with Session() as session:
            channel = ChannelService(session, _ctx(seed["tenant_id"])).create(
                {
                    "park_id": seed["park_id"],
                    "code": f"PG_CHANNEL_{uuid4().hex[:10].upper()}",
                    "name": "PostgreSQL 并发渠道",
                    "secret_env_key": key_ref,
                    "enabled": True,
                    "allow_auto_assign": False,
                }
            )
            channel_id = int(channel["id"])
            public_id = str(channel["public_id"])
        event_id = f"pg-event-{uuid4().hex}"
        raw = json.dumps(
            {"name": "PostgreSQL 渠道企业", "contact_phone": "13800138222"},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        timestamp = str(int(time.time()))
        body_sha = hashlib.sha256(raw).hexdigest()
        signing_input = f"v1\n{timestamp}\n{event_id}\n{body_sha}".encode()
        signature = "v1=" + hmac.new(secret.encode(), signing_input, hashlib.sha256).hexdigest()
        barrier = threading.Barrier(2)

        def receive() -> str:
            with Session() as session:
                barrier.wait(timeout=15)
                return str(
                    PublicChannelIntake(session).receive(
                        public_id=public_id,
                        raw_body=raw,
                        timestamp=timestamp,
                        external_event_id=event_id,
                        signature=signature,
                    )["status"]
                )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: receive(), range(2)))
        assert set(results) <= {"RECEIVED", "ACCEPTED"}
        with Session() as session:
            event_count = int(
                session.scalar(
                    select(func.count()).select_from(LeadChannelInboxEvent).where(
                        LeadChannelInboxEvent.channel_id == channel_id,
                        LeadChannelInboxEvent.external_event_id == event_id,
                    )
                )
                or 0
            )
            lead_count = int(
                session.scalar(
                    select(func.count()).select_from(Lead).where(
                        Lead.tenant_id == seed["tenant_id"], Lead.source_ref == event_id
                    )
                )
                or 0
            )
            event = session.scalar(
                select(LeadChannelInboxEvent).where(
                    LeadChannelInboxEvent.channel_id == channel_id,
                    LeadChannelInboxEvent.external_event_id == event_id,
                )
            )
            assert event_count == 1
            assert lead_count == 1
            assert event is not None and event.status == "ACCEPTED"
    finally:
        if previous is None:
            os.environ.pop(key_ref, None)
        else:
            os.environ[key_ref] = previous
        engine.dispose()


def test_pg_expired_lock_can_be_reacquired_without_duplicate_active_rows() -> None:
    engine, Session = _factory(_require_pg_url())
    seed = _seed(Session)
    with Session() as session:
        first = LeadService(session, _ctx(seed["tenant_id"])).acquire_unit_lock(
            seed["first_id"],
            unit_id=seed["unit_id"],
            expected_version=seed["first_version"],
            intent_id=seed["first_intent_id"],
        )
    with Session() as session:
        lock = session.get(LeadUnitLock, first["id"])
        lock.expires_at = utc_now() - timedelta(seconds=1)
        session.commit()
    with Session() as session:
        second = LeadService(session, _ctx(seed["tenant_id"])).acquire_unit_lock(
            seed["second_id"],
            unit_id=seed["unit_id"],
            expected_version=seed["second_version"],
            intent_id=seed["second_intent_id"],
        )
        assert second["status"] == "ACTIVE"
    with Session() as session:
        rows = list(
            session.scalars(
                select(LeadUnitLock).where(
                    LeadUnitLock.tenant_id == seed["tenant_id"],
                    LeadUnitLock.unit_id == seed["unit_id"],
                )
            ).all()
        )
        assert sum(row.status == "ACTIVE" for row in rows) == 1
        assert sum(row.status == "EXPIRED" for row in rows) == 1
        assert session.get(Unit, seed["unit_id"]).status == "RESERVED"
    engine.dispose()


def test_pg_lock_and_lease_activation_serialize_on_unit_row() -> None:
    engine, Session = _factory(_require_pg_url())
    seed = _seed(Session)
    with Session() as session:
        ctx = _ctx(seed["tenant_id"])
        party = PartyService(session, ctx).create_party(
            {
                "name": f"并发承租主体-{uuid4().hex[:8]}",
                "party_type": "ORGANIZATION",
                "initial_park_relation": {
                    "park_id": seed["park_id"],
                    "role_code": "LESSEE",
                },
            }
        )
        lease = LeaseService(session, ctx).create_contract(
            {
                "park_id": seed["park_id"],
                "party_id": party["id"],
                "start_date": "2026-11-01",
                "end_date": "2027-10-31",
                "units": [
                    {
                        "unit_id": seed["unit_id"],
                        "occupied_area": "80",
                        "unit_rent_price": "20",
                    }
                ],
            }
        )
        LeaseService(session, ctx).submit(int(lease["id"]))
        lease_id = int(lease["id"])
    barrier = threading.Barrier(2)

    def acquire() -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                LeadService(session, _ctx(seed["tenant_id"])).acquire_unit_lock(
                    seed["first_id"],
                    unit_id=seed["unit_id"],
                    expected_version=seed["first_version"],
                    intent_id=seed["first_intent_id"],
                )
                return ("lock", None)
            except AppError as exc:
                session.rollback()
                return ("lock_err", exc.code)

    def activate() -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                LeaseService(session, _ctx(seed["tenant_id"])).activate(lease_id)
                return ("activate", None)
            except AppError as exc:
                session.rollback()
                return ("activate_err", exc.code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(acquire), pool.submit(activate)]
        outcomes = [future.result(timeout=30) for future in results]
    successes = [state for state, _ in outcomes if not state.endswith("_err")]
    errors = [code for state, code in outcomes if state.endswith("_err")]
    assert len(successes) == 1, outcomes
    assert len(errors) == 1, outcomes
    assert errors[0] in {"UNIT_ALREADY_LOCKED", "UNIT_NOT_AVAILABLE"}
    with Session() as session:
        unit = session.get(Unit, seed["unit_id"])
        lease = session.get(LeaseContract, lease_id)
        active_locks = int(
            session.scalar(
                select(func.count()).select_from(LeadUnitLock).where(
                    LeadUnitLock.tenant_id == seed["tenant_id"],
                    LeadUnitLock.unit_id == seed["unit_id"],
                    LeadUnitLock.status == "ACTIVE",
                )
            )
            or 0
        )
        if lease.status == "ACTIVE":
            assert unit.status == "OCCUPIED"
            assert active_locks == 0
        else:
            assert lease.status == "PENDING_ACTIVE"
            assert unit.status == "RESERVED"
            assert active_locks == 1
    engine.dispose()

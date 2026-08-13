"""PostgreSQL concurrency acceptance for Investment CRM V2."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.investment import Lead, LeadUnitLock
from app.infrastructure.database.models.lease import LeaseContract
from app.infrastructure.database.models.park_property import Unit
from app.modules.identity.application.bootstrap import ensure_default_tenant
from app.modules.investment.application.lead_service import LeadService
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
        return {
            "tenant_id": tenant_id,
            "park_id": int(park["id"]),
            "unit_id": int(unit["id"]),
            "first_id": int(first["id"]),
            "first_version": int(first["lock_version"]),
            "second_id": int(second["id"]),
            "second_version": int(second["lock_version"]),
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


def test_pg_expired_lock_can_be_reacquired_without_duplicate_active_rows() -> None:
    engine, Session = _factory(_require_pg_url())
    seed = _seed(Session)
    with Session() as session:
        first = LeadService(session, _ctx(seed["tenant_id"])).acquire_unit_lock(
            seed["first_id"],
            unit_id=seed["unit_id"],
            expected_version=seed["first_version"],
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

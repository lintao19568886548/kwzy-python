"""PostgreSQL 16 constraints and concurrency for workforce governance."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.infrastructure.database.models.identity import User
from app.infrastructure.database.models.park_property import Park
from app.modules.identity.application.bootstrap import ensure_default_tenant
from app.modules.workforce.application.service import WorkforceService
from app.shared.tenant_context import ParkScopeMode, TenantContext

pytestmark = pytest.mark.pg
TODAY = datetime.now(timezone.utc).date()


def _url() -> str:
    value = os.environ.get("TEST_DATABASE_URL") or os.environ.get("POSTGRES_TEST_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL / POSTGRES_TEST_URL not set")
    parsed = make_url(value)
    if (
        not value.startswith("postgresql")
        or parsed.host not in {"127.0.0.1", "localhost"}
        or (parsed.database or "").lower() != "kwzy_party_test"
    ):
        pytest.fail("workforce acceptance requires disposable loopback PostgreSQL kwzy_party_test")
    return value


def _factory():
    engine = create_engine(_url(), pool_pre_ping=True, pool_size=6, max_overflow=6)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _ctx(tenant_id: int, user_id: int) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        username="workforce-pg",
        permissions=["*"],
        park_scope_mode=ParkScopeMode.ALL,
    )


def _seed() -> dict[str, int]:
    _, Session = _factory()
    suffix = uuid4().hex[:10]
    with Session() as session:
        tenant = ensure_default_tenant(session)
        park = Park(tenant_id=tenant.id, name=f"人力PG园-{suffix}", status="ACTIVE")
        user = User(
            tenant_id=tenant.id,
            username=f"workforce_pg_{suffix}",
            password_hash="synthetic-not-login",
            real_name="人力PG经理",
            status="ACTIVE",
            all_parks=True,
        )
        session.add_all([park, user])
        session.commit()
        service = WorkforceService(session, _ctx(int(tenant.id), int(user.id)))
        employee = service.create_employee(
            {
                "park_id": int(park.id),
                "employee_no": f"PG_{suffix}",
                "display_name": "PG并发员工",
                "start_date": TODAY,
            }
        )
        shift = service.create_shift(
            {
                "park_id": int(park.id),
                "code": f"PGDAY_{suffix[:6]}",
                "name": "PG日班",
                "start_time": time(9),
                "end_time": time(18),
                "cross_day": False,
                "break_minutes": 60,
                "late_grace_minutes": 5,
                "early_grace_minutes": 5,
            }
        )
        return {
            "tenant_id": int(tenant.id),
            "park_id": int(park.id),
            "user_id": int(user.id),
            "employee_id": employee["id"],
            "shift_version_id": shift["versions"][0]["id"],
        }


def test_pg_workforce_schema_types_indexes_and_privacy() -> None:
    engine, _ = _factory()
    inspector = inspect(engine)
    expected = {
        "workforce_employees",
        "workforce_shift_templates",
        "workforce_shift_template_versions",
        "workforce_shift_assignments",
        "workforce_attendance_policies",
        "workforce_attendance_locations",
        "workforce_attendance_punches",
        "workforce_attendance_summaries",
        "workforce_leave_requests",
        "workforce_performance_cycles",
        "workforce_performance_goals",
        "workforce_performance_reviews",
        "workforce_qualification_types",
        "workforce_employee_qualifications",
        "workforce_qualification_events",
    }
    assert expected <= set(inspector.get_table_names())
    policy_bool = next(
        column
        for column in inspector.get_columns("workforce_attendance_policies")
        if column["name"] == "allow_manual"
    )["type"]
    assert policy_bool.__class__.__name__.upper() == "BOOLEAN"
    employee_columns = {column["name"] for column in inspector.get_columns("workforce_employees")}
    assert {
        "mobile_masked",
        "mobile_fingerprint",
        "identity_masked",
        "identity_fingerprint",
    } <= employee_columns
    assert {"mobile", "identity_number", "latitude", "longitude"}.isdisjoint(employee_columns)
    assert {item["name"] for item in inspector.get_indexes("workforce_shift_assignments")} >= {
        "uk_workforce_shift_assignment_active",
        "ix_workforce_roster_scope",
    }


def test_pg_concurrent_roster_has_one_winner() -> None:
    seed = _seed()
    _, Session = _factory()
    barrier = threading.Barrier(2)

    def assign(marker: str) -> tuple[str, str | int]:
        with Session() as session:
            barrier.wait(timeout=15)
            try:
                result = WorkforceService(
                    session, _ctx(seed["tenant_id"], seed["user_id"])
                ).create_assignment(
                    {
                        "employee_id": seed["employee_id"],
                        "shift_version_id": seed["shift_version_id"],
                        "work_date": TODAY,
                        "reason": marker,
                    }
                )
                return "ok", result["id"]
            except AppError as exc:
                return "error", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(assign, ["a", "b"]))
    assert sum(1 for state, _ in results if state == "ok") == 1
    assert (
        sum(
            1
            for state, code in results
            if state == "error" and code == "WORKFORCE_ASSIGNMENT_CONFLICT"
        )
        == 1
    )

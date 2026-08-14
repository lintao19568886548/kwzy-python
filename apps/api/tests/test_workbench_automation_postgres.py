"""PostgreSQL 16 schema, claim and concurrency gates for workbench automation."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.identity import Tenant, User
from app.infrastructure.database.models.workbench_automation import (
    BusinessEvent,
    EventConsumerLog,
    SchedulerRun,
)
from app.modules.workbench.application.automation_service import WorkbenchAutomationService
from app.modules.workbench.infrastructure.automation_repository import AutomationRepository
from app.shared.tenant_context import ParkScopeMode, TenantContext
from app.workers.workbench import run_cycle

pytestmark = pytest.mark.pg


def _require_pg_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("POSTGRES_TEST_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL / POSTGRES_TEST_URL not set")
    if not url.startswith("postgresql") or not any(
        host in url for host in ("127.0.0.1", "localhost")
    ):
        pytest.fail("workbench automation tests require localhost PostgreSQL")
    if "kwzy_party_test" not in url:
        pytest.fail("database name must include kwzy_party_test")
    return url


def _factory():
    engine = create_engine(_require_pg_url(), pool_pre_ping=True, pool_size=8, max_overflow=4)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _seed_tenant(Session) -> tuple[int, int]:
    suffix = uuid4().hex[:12]
    with Session() as session:
        tenant = Tenant(code=f"workbench-pg-{suffix}", name="工作台并发验收")
        session.add(tenant)
        session.flush()
        user = User(
            tenant_id=tenant.id,
            username=f"workbench-pg-{suffix}",
            password_hash="not-used-in-direct-service-test",
            real_name="工作台并发用户",
            status="ACTIVE",
            all_parks=True,
        )
        session.add(user)
        session.commit()
        return int(tenant.id), int(user.id)


def _ctx(tenant_id: int, user_id: int) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        username=f"workbench-pg-{user_id}",
        permissions=["*"],
        park_scope_mode=ParkScopeMode.ALL,
    )


def _emit(service: WorkbenchAutomationService, key: str) -> dict:
    return service.emit_event(
        event_type="TEST_AUTOMATION_EVENT",
        source_type="PG_TEST",
        source_id=key,
        idempotency_key=f"workbench-pg:{key}",
        payload={"title": key, "status": "READY", "deep_link": "/workbench"},
        enforce_permission=False,
    )


def test_pg_workbench_schema_constraints_indexes_and_booleans() -> None:
    engine, _ = _factory()
    inspector = inspect(engine)
    expected_tables = {
        "business_events",
        "event_consumer_logs",
        "automation_rules",
        "automation_rule_versions",
        "automation_executions",
        "in_app_notifications",
        "scheduler_definitions",
        "scheduler_runs",
        "workbench_layouts",
        "workbench_widgets",
    }
    assert expected_tables <= set(inspector.get_table_names())
    unique_names = {
        constraint["name"]
        for table in expected_tables
        for constraint in inspector.get_unique_constraints(table)
    }
    assert {
        "uk_business_event_idempotency",
        "uk_event_consumer_generation",
        "uk_automation_execution",
        "uk_in_app_notification_idempotency",
        "uk_scheduler_run_idempotency",
        "uk_workbench_layout_user",
        "uk_workbench_layout_role",
    } <= unique_names
    index_names = {
        index["name"]
        for table in expected_tables
        for index in inspector.get_indexes(table)
    }
    assert {
        "ix_event_consumer_claim",
        "ix_automation_rule_match",
        "ix_in_app_notification_inbox",
        "ix_scheduler_due",
    } <= index_names
    boolean_columns = {
        ("automation_executions", "matched"),
        ("scheduler_definitions", "enabled"),
        ("workbench_layouts", "is_active"),
        ("workbench_widgets", "visible"),
        ("work_items", "source_owned"),
    }
    for table, column in boolean_columns:
        types = {item["name"]: str(item["type"]).upper() for item in inspector.get_columns(table)}
        assert types[column] == "BOOLEAN", (table, column, types[column])
    engine.dispose()


def test_pg_event_emit_is_concurrently_idempotent() -> None:
    engine, Session = _factory()
    tenant_id, user_id = _seed_tenant(Session)
    barrier = threading.Barrier(2)

    def emit() -> int:
        with Session() as session:
            barrier.wait(timeout=15)
            return int(_emit(WorkbenchAutomationService(session, _ctx(tenant_id, user_id)), "same")["id"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: emit(), range(2)))
    assert ids[0] == ids[1]
    with Session() as session:
        assert session.scalar(
            select(func.count(BusinessEvent.id)).where(
                BusinessEvent.tenant_id == tenant_id,
                BusinessEvent.idempotency_key == "workbench-pg:same",
            )
        ) == 1
        assert session.scalar(
            select(func.count(EventConsumerLog.id)).where(
                EventConsumerLog.tenant_id == tenant_id
            )
        ) == 1
    engine.dispose()


def test_pg_skip_locked_claims_are_disjoint() -> None:
    engine, Session = _factory()
    tenant_id, user_id = _seed_tenant(Session)
    with Session() as session:
        service = WorkbenchAutomationService(session, _ctx(tenant_id, user_id))
        for index in range(4):
            _emit(service, f"claim-{index}-{uuid4().hex[:6]}")
    before_claim = threading.Barrier(2)
    after_claim = threading.Barrier(2)

    def claim(worker: str) -> list[int]:
        with Session() as session:
            before_claim.wait(timeout=15)
            rows = AutomationRepository(session, _ctx(tenant_id, user_id)).claim_consumers(
                consumer_name="WORKBENCH_AUTOMATION",
                worker_id=worker,
                limit=2,
                now=utc_now(),
            )
            ids = [int(row.id) for row in rows]
            after_claim.wait(timeout=15)
            session.commit()
            return ids

    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed = list(pool.map(claim, ["worker-a", "worker-b"]))
    assert len(claimed[0]) == len(claimed[1]) == 2
    assert set(claimed[0]).isdisjoint(claimed[1])
    assert len(set(claimed[0] + claimed[1])) == 4
    engine.dispose()


def test_pg_schedule_run_and_layout_versions_have_one_winner() -> None:
    engine, Session = _factory()
    tenant_id, user_id = _seed_tenant(Session)
    context = _ctx(tenant_id, user_id)
    widgets = [
        {
            "widget_key": "OPERATIONS_METRICS",
            "position_x": 0,
            "position_y": 0,
            "width": 12,
            "height": 2,
            "visible": True,
            "config": {},
        }
    ]
    with Session() as session:
        service = WorkbenchAutomationService(session, context)
        schedule = service.create_schedule(
            {
                "code": f"PG_DISPATCH_{uuid4().hex[:8].upper()}",
                "name": "PG 并发调度",
                "handler_key": "OUTBOX_DISPATCH",
                "parameters": {"limit": 10},
                "cadence_seconds": 60,
                "enabled": False,
            }
        )
        layout = service.save_user_layout(
            {"expected_version": 0, "name": "PG 工作台", "widgets": widgets}
        )

    run_barrier = threading.Barrier(2)

    def run() -> int:
        with Session() as session:
            run_barrier.wait(timeout=15)
            result = WorkbenchAutomationService(
                session, _ctx(tenant_id, user_id)
            ).run_schedule(
                int(schedule["id"]), idempotency_key="pg-schedule-shared-key"
            )
            return int(result["id"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        run_ids = list(pool.map(lambda _: run(), range(2)))
    assert run_ids[0] == run_ids[1]
    with Session() as session:
        assert session.scalar(
            select(func.count(SchedulerRun.id)).where(
                SchedulerRun.tenant_id == tenant_id,
                SchedulerRun.idempotency_key == "pg-schedule-shared-key",
            )
        ) == 1

    layout_barrier = threading.Barrier(2)

    def save(name: str) -> tuple[str, str | None]:
        with Session() as session:
            try:
                layout_barrier.wait(timeout=15)
                WorkbenchAutomationService(session, _ctx(tenant_id, user_id)).save_user_layout(
                    {
                        "expected_version": int(layout["lock_version"]),
                        "name": name,
                        "widgets": widgets,
                    }
                )
                return "ok", None
            except AppError as exc:
                session.rollback()
                return "err", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, ["并发布局甲", "并发布局乙"]))
    assert sorted(state for state, _ in results) == ["err", "ok"]
    assert [code for state, code in results if state == "err"] == ["LAYOUT_VERSION_CONFLICT"]
    engine.dispose()


def test_pg_worker_restart_is_idempotent_and_recovers_stale_run() -> None:
    engine, Session = _factory()
    tenant_id, user_id = _seed_tenant(Session)
    with Session() as session:
        service = WorkbenchAutomationService(session, _ctx(tenant_id, user_id))
        schedule = service.create_schedule(
            {
                "code": f"PG_WORKER_{uuid4().hex[:8].upper()}",
                "name": "PG worker restart",
                "handler_key": "OUTBOX_DISPATCH",
                "parameters": {"limit": 10},
                "cadence_seconds": 60,
                "enabled": True,
                "timeout_seconds": 10,
            }
        )
        _emit(service, f"worker-{uuid4().hex[:8]}")

    first = run_cycle(Session, worker_id="pg-worker-a", batch_size=20)
    second = run_cycle(Session, worker_id="pg-worker-b", batch_size=20)
    assert first["failed_tenants"] == second["failed_tenants"] == 0
    first_tenant = first["tenant_results"][str(tenant_id)]
    second_tenant = second["tenant_results"][str(tenant_id)]
    assert first_tenant["dispatched"] == 1
    assert first_tenant["scheduled"] == 1
    assert second_tenant["dispatched"] == 0
    assert second_tenant["scheduled"] == 0

    now = utc_now()
    with Session() as session:
        stale = SchedulerRun(
            tenant_id=tenant_id,
            schedule_id=int(schedule["id"]),
            fire_at=now - timedelta(minutes=2),
            generation=1,
            idempotency_key=f"stale:{uuid4().hex}",
            status="RUNNING",
            claim_token=uuid4().hex,
            claimed_by="dead-worker",
            attempt_no=1,
            started_at=now - timedelta(minutes=2),
            heartbeat_at=now - timedelta(minutes=2),
        )
        session.add(stale)
        session.commit()
        stale_id = int(stale.id)
    recovered = run_cycle(Session, worker_id="pg-worker-c", batch_size=20)
    assert recovered["tenant_results"][str(tenant_id)]["recovered"] == 1
    with Session() as session:
        row = session.get(SchedulerRun, stale_id)
        assert row is not None and row.status == "TIMED_OUT" and row.finished_at is not None
    engine.dispose()

"""PostgreSQL 16 constraints and concurrency for tenant-service work orders."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.infrastructure.database.models.facility_ops import (
    TenantServicePrincipal,
    TenantServicePrincipalPark,
    WorkOrder,
    WorkOrderAcceptance,
    WorkOrderEvent,
    WorkOrderRating,
)
from app.infrastructure.database.models.identity import Tenant, User
from app.infrastructure.database.models.park_property import Park
from app.infrastructure.database.models.party import Party
from app.modules.facility_ops.application.work_order_service import WorkOrderService
from app.modules.identity.application.bootstrap import ensure_default_tenant
from app.shared.tenant_context import ParkScopeMode, TenantContext

pytestmark = pytest.mark.pg
NAIVE_UTC = datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc).replace(tzinfo=None)


def _url() -> str:
    value = os.environ.get("TEST_DATABASE_URL") or os.environ.get("POSTGRES_TEST_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL / POSTGRES_TEST_URL not set")
    if not value.startswith("postgresql") or "sqlite" in value.lower():
        pytest.fail("work-order acceptance requires PostgreSQL")
    parsed = make_url(value)
    if parsed.host not in {"127.0.0.1", "localhost"}:
        pytest.fail("work-order acceptance is restricted to loopback PostgreSQL")
    database = (parsed.database or "").lower()
    explicitly_disposable = database == "kwzy_party_test" or (
        database.startswith("kwzy_workorder_") and "audit" in database
    )
    if not explicitly_disposable:
        pytest.fail("work-order acceptance requires an explicitly named disposable database")
    return value


def _factory():
    engine = create_engine(_url(), pool_pre_ping=True, pool_size=5, max_overflow=5)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _ctx(tenant_id: int, *, user_id: int = 1, permissions: list[str] | None = None) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        username="admin",
        permissions=permissions or ["*"],
        park_ids=[],
        park_scope_mode=ParkScopeMode.ALL,
    )


def _seed() -> dict[str, int]:
    _, Session = _factory()
    suffix = uuid4().hex[:10]
    with Session() as session:
        tenant = ensure_default_tenant(session)
        park = Park(tenant_id=tenant.id, name=f"工单PG园-{suffix}", status="ACTIVE")
        second_park = Park(
            tenant_id=tenant.id,
            name=f"工单PG异园-{suffix}",
            status="ACTIVE",
        )
        party = Party(
            tenant_id=tenant.id,
            party_type="ORGANIZATION",
            name=f"工单PG主体-{suffix}",
            status="ACTIVE",
            risk_status="NORMAL",
        )
        assignee = User(
            tenant_id=tenant.id,
            username=f"wo_pg_{suffix}",
            password_hash="synthetic-not-a-login-secret",
            real_name="PG维修人员",
            status="ACTIVE",
            all_parks=True,
        )
        foreign_tenant = Tenant(
            code=f"wo-foreign-{suffix}",
            name=f"外租户-{suffix}",
            status="ACTIVE",
            db_strategy="SHARED",
        )
        session.add_all([park, second_park, party, assignee, foreign_tenant])
        session.flush()
        foreign_party = Party(
            tenant_id=foreign_tenant.id,
            party_type="ORGANIZATION",
            name=f"外租户主体-{suffix}",
            status="ACTIVE",
            risk_status="NORMAL",
        )
        session.add(foreign_party)
        session.flush()
        order = WorkOrder(
            tenant_id=tenant.id,
            park_id=park.id,
            order_no=f"WO-PG-{suffix}",
            party_id=party.id,
            title="并发派单验证",
            category="MAINTENANCE",
            priority="HIGH",
            status="SUBMITTED",
            source_type="PG_TEST",
            source_id=f"pg-{suffix}",
            evidence_refs_json=[],
            lock_version=1,
        )
        session.add(order)
        session.commit()
        return {
            "tenant_id": int(tenant.id),
            "park_id": int(park.id),
            "second_park_id": int(second_park.id),
            "party_id": int(party.id),
            "foreign_party_id": int(foreign_party.id),
            "assignee_id": int(assignee.id),
            "order_id": int(order.id),
        }


def test_pg_schema_indexes_types_and_tenant_park_constraints() -> None:
    seed = _seed()
    engine, Session = _factory()
    inspector = inspect(engine)
    with engine.connect() as connection:
        assert str(connection.scalar(text("SHOW server_version"))).split(".")[0] == "16"
    assert {
        "tenant_service_principals",
        "work_order_assignment_rules",
        "work_order_events",
        "work_order_quotes",
        "work_order_quote_lines",
        "work_order_cost_entries",
        "work_order_acceptances",
        "work_order_ratings",
    }.issubset(set(inspector.get_table_names()))
    quote_required = next(
        column
        for column in inspector.get_columns("work_orders")
        if column["name"] == "quote_required"
    )
    assert quote_required["type"].__class__.__name__.upper() == "BOOLEAN"
    index_names = {item["name"] for item in inspector.get_indexes("work_orders")}
    assert {
        "uk_work_orders_source_v2",
        "ix_work_orders_service_queue_v2",
        "ix_work_orders_sla_v2",
    } <= index_names
    fk_names = {item["name"] for item in inspector.get_foreign_keys("work_orders")}
    assert {
        "fk_work_orders_tenant_park_v2",
        "fk_work_orders_tenant_party_v2",
        "fk_work_orders_tenant_reporter_v2",
        "fk_work_orders_tenant_party_contact_v2",
        "fk_work_orders_tenant_unit_v2",
    } <= fk_names

    with Session() as session:
        cross_tenant = WorkOrder(
            tenant_id=seed["tenant_id"],
            park_id=seed["park_id"],
            order_no=f"WO-XTENANT-{uuid4().hex[:8]}",
            party_id=seed["foreign_party_id"],
            title="禁止跨租户主体",
            category="GENERAL",
            priority="MEDIUM",
            status="SUBMITTED",
            source_type="PG_TEST",
            source_id=f"cross-{uuid4().hex}",
            evidence_refs_json=[],
            lock_version=1,
        )
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(cross_tenant)
            session.flush()

        wrong_park_event = WorkOrderEvent(
            tenant_id=seed["tenant_id"],
            park_id=seed["second_park_id"],
            work_order_id=seed["order_id"],
            event_type="INVALID_PARK",
            actor_type="SYSTEM",
            detail_json={},
            idempotency_key=f"wrong-park-{uuid4().hex}",
            occurred_at=NAIVE_UTC,
        )
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(wrong_park_event)
            session.flush()


def test_pg_rating_dispatch_and_acceptance_decisions_are_serialized() -> None:
    seed = _seed()
    _, Session = _factory()
    with Session() as session:
        session.execute(
            text(
                "INSERT INTO work_order_ratings "
                "(tenant_id, park_id, work_order_id, score, tags_json, actor_party_id, "
                "idempotency_key, created_at) "
                "VALUES (:tenant_id, :park_id, :work_order_id, 5, '[]', :party_id, :key, now())"
            ),
            {
                **seed,
                "work_order_id": seed["order_id"],
                "key": f"rating-{uuid4().hex}",
            },
        )
        session.commit()
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(
                WorkOrderRating(
                    tenant_id=seed["tenant_id"],
                    park_id=seed["park_id"],
                    work_order_id=seed["order_id"],
                    score=4,
                    tags_json=[],
                    actor_party_id=seed["party_id"],
                    idempotency_key=f"rating-{uuid4().hex}",
                    created_at=NAIVE_UTC,
                )
            )
            session.flush()

    barrier = threading.Barrier(2)

    def dispatch(reason: str) -> tuple[str, str]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                result = WorkOrderService(session, _ctx(seed["tenant_id"])).dispatch(
                    seed["order_id"],
                    {
                        "expected_version": 1,
                        "assignee_user_id": seed["assignee_id"],
                        "reason": reason,
                    },
                )
                return "ok", str(result["lock_version"])
            except AppError as exc:
                session.rollback()
                return "error", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(dispatch, ["并发派单A", "并发派单B"]))
    assert sum(kind == "ok" for kind, _ in outcomes) == 1, outcomes
    assert [value for kind, value in outcomes if kind == "error"] == ["WORK_ORDER_VERSION_CONFLICT"]
    with Session() as session:
        order = session.scalar(select(WorkOrder).where(WorkOrder.id == seed["order_id"]))
        assert order is not None
        assert order.status == "ASSIGNED"
        assert order.lock_version == 2
        principal = TenantServicePrincipal(
            tenant_id=seed["tenant_id"],
            user_id=seed["assignee_id"],
            party_id=seed["party_id"],
            status="ACTIVE",
            created_by=seed["assignee_id"],
        )
        session.add(principal)
        session.flush()
        session.add(
            TenantServicePrincipalPark(
                tenant_id=seed["tenant_id"],
                principal_id=principal.id,
                park_id=seed["park_id"],
            )
        )
        order.status = "WAITING_ACCEPTANCE"
        order.lock_version = 7
        session.commit()

    acceptance_barrier = threading.Barrier(2)

    def decide(decision: str) -> tuple[str, str]:
        with Session() as session:
            try:
                acceptance_barrier.wait(timeout=15)
                result = WorkOrderService(
                    session,
                    _ctx(
                        seed["tenant_id"],
                        user_id=seed["assignee_id"],
                        permissions=["tenant_service:accept", "tenant_service:read_own"],
                    ),
                ).decide_acceptance(
                    seed["order_id"],
                    {
                        "expected_version": 7,
                        "decision": decision,
                        "comment": "并发验收" if decision == "ACCEPTED" else "并发返工原因",
                    },
                    idempotency_key=f"pg-acceptance-{decision.lower()}-{uuid4().hex}",
                )
                return "ok", str(result["status"])
            except AppError as exc:
                session.rollback()
                return "error", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        acceptance_outcomes = list(pool.map(decide, ["ACCEPTED", "REWORK"]))
    assert sum(kind == "ok" for kind, _ in acceptance_outcomes) == 1, acceptance_outcomes
    assert [value for kind, value in acceptance_outcomes if kind == "error"] == [
        "WORK_ORDER_VERSION_CONFLICT"
    ]
    with Session() as session:
        order = session.scalar(select(WorkOrder).where(WorkOrder.id == seed["order_id"]))
        assert order is not None
        assert order.status in {"COMPLETED", "IN_PROGRESS"}
        assert order.lock_version == 8
        decisions = list(
            session.scalars(
                select(WorkOrderAcceptance).where(
                    WorkOrderAcceptance.work_order_id == seed["order_id"]
                )
            ).all()
        )
        assert len(decisions) == 1

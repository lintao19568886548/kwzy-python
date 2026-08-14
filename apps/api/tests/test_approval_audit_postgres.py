"""PostgreSQL 16 schema and concurrency gates for approval/audit center."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.models.audit import AuditChainHead, AuditLog
from app.infrastructure.database.models.identity import User
from app.infrastructure.database.models.workflow import ApprovalEvent, ApprovalRequest, ApprovalTask
from app.modules.identity.application.bootstrap import ensure_default_tenant
from app.modules.workflow.application.approval_service import ApprovalService
from app.modules.workflow.infrastructure.audit_repository import AuditRepository
from app.shared.tenant_context import ParkScopeMode, TenantContext

pytestmark = pytest.mark.pg


def _require_pg_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("POSTGRES_TEST_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL / POSTGRES_TEST_URL not set")
    if not url.startswith("postgresql") or not any(
        host in url for host in ("127.0.0.1", "localhost")
    ):
        pytest.fail("approval/audit tests require localhost PostgreSQL")
    if "kwzy_party_test" not in url:
        pytest.fail("database name must include kwzy_party_test")
    return url


def _factory():
    engine = create_engine(_require_pg_url(), pool_pre_ping=True, pool_size=12, max_overflow=4)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _context(tenant_id: int, user_id: int, *, request_id: str = "") -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        username=f"approval-pg-{user_id}",
        permissions=["*"],
        park_scope_mode=ParkScopeMode.ALL,
        request_id=request_id,
    )


def _seed_users(Session, count: int = 3) -> tuple[int, list[int]]:
    suffix = uuid4().hex[:10]
    with Session() as session:
        tenant = ensure_default_tenant(session)
        admin = session.scalars(
            select(User).where(User.tenant_id == tenant.id, User.username == "admin")
        ).one()
        users = []
        for index in range(count):
            user = User(
                tenant_id=tenant.id,
                username=f"approval-pg-{suffix}-{index}",
                password_hash=admin.password_hash,
                real_name=f"审批并发用户{index}",
                status="ACTIVE",
            )
            session.add(user)
            users.append(user)
        session.commit()
        return int(tenant.id), [int(user.id) for user in users]


def test_pg_concurrent_publish_has_one_winner() -> None:
    engine, Session = _factory()
    tenant_id, users = _seed_users(Session, 1)
    code = f"PUBLISH_{uuid4().hex[:10].upper()}"
    with Session() as session:
        service = ApprovalService(session, _context(tenant_id, users[0]))
        definition = service.create_definition(
            {
                "code": code,
                "name": "并发发布",
                "biz_type": "PG_PUBLISH",
                "steps": [
                    {
                        "step_order": 1,
                        "name": "审批",
                        "approval_mode": "ANY",
                        "min_approvals": 1,
                        "sla_hours": 24,
                        "assignees": [{"user_id": users[0]}],
                    }
                ],
            }
        )
        definition_id = int(definition["id"])
        version_id = int(definition["versions"][0]["id"])

    barrier = threading.Barrier(2)

    def publish() -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                ApprovalService(session, _context(tenant_id, users[0])).publish_definition(
                    definition_id,
                    version_id=version_id,
                    expected_lock_version=0,
                )
                return "ok", None
            except AppError as exc:
                session.rollback()
                return "err", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: publish(), range(2)))
    assert sorted(state for state, _ in results) == ["err", "ok"], results
    assert [code for state, code in results if state == "err"] == ["VERSION_CONFLICT"]
    engine.dispose()


def test_pg_concurrent_any_decisions_advance_once() -> None:
    engine, Session = _factory()
    tenant_id, users = _seed_users(Session, 3)
    applicant_id, first_id, second_id = users
    code = f"DECIDE_{uuid4().hex[:10].upper()}"
    biz_id = uuid4().hex
    with Session() as session:
        admin_service = ApprovalService(session, _context(tenant_id, applicant_id))
        definition = admin_service.create_definition(
            {
                "code": code,
                "name": "并发决定",
                "biz_type": "PG_DECIDE",
                "steps": [
                    {
                        "step_order": 1,
                        "name": "任一审批",
                        "approval_mode": "ANY",
                        "min_approvals": 1,
                        "sla_hours": 24,
                        "assignees": [
                            {"user_id": first_id},
                            {"user_id": second_id},
                        ],
                    }
                ],
            }
        )
        version_id = int(definition["versions"][0]["id"])
        admin_service.publish_definition(
            int(definition["id"]),
            version_id=version_id,
            expected_lock_version=0,
        )
        approval = admin_service.create(
            {
                "definition_code": code,
                "biz_type": "PG_DECIDE",
                "biz_id": biz_id,
                "title": "并发决定",
                "idempotency_key": f"submit-{biz_id}",
            }
        )
        approval_id = int(approval["id"])
        task_ids = [
            int(task.id)
            for task in session.scalars(
                select(ApprovalTask)
                .where(ApprovalTask.approval_id == approval_id)
                .order_by(ApprovalTask.id)
            ).all()
        ]
    assert len(task_ids) == 2
    barrier = threading.Barrier(2)

    def decide(args: tuple[int, int]) -> tuple[str, str | None]:
        task_id, user_id = args
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                ApprovalService(session, _context(tenant_id, user_id)).decide_task(
                    task_id,
                    action="APPROVE",
                    remark="并发同意",
                    expected_version=0,
                    idempotency_key=f"decision-{biz_id}-{task_id}",
                    override_reason=None,
                )
                return "ok", None
            except AppError as exc:
                session.rollback()
                return "err", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(decide, zip(task_ids, [first_id, second_id], strict=True)))
    assert sorted(state for state, _ in results) == ["err", "ok"], results
    assert [code for state, code in results if state == "err"] == ["VERSION_CONFLICT"]
    with Session() as session:
        request = session.get(ApprovalRequest, approval_id)
        assert request is not None
        assert request.status == "APPROVED"
        assert int(request.lock_version) == 1
        statuses = list(
            session.scalars(
                select(ApprovalTask.status)
                .where(ApprovalTask.approval_id == approval_id)
                .order_by(ApprovalTask.status)
            ).all()
        )
        assert statuses == ["APPROVED", "SKIPPED"]
        decisions = session.scalar(
            select(func.count(ApprovalEvent.id)).where(
                ApprovalEvent.approval_id == approval_id,
                ApprovalEvent.action == "APPROVE",
            )
        )
        assert int(decisions or 0) == 1
    engine.dispose()


def test_pg_concurrent_audit_append_forms_one_chain() -> None:
    engine, Session = _factory()
    tenant_id, users = _seed_users(Session, 1)
    user_id = users[0]
    with Session() as session:
        before = session.get(AuditChainHead, tenant_id)
        before_sequence = int(before.sequence_no) if before is not None else 0
    barrier = threading.Barrier(8)

    def append(index: int) -> int:
        with Session() as session:
            barrier.wait(timeout=20)
            row = AuditRecorder(
                session,
                _context(tenant_id, user_id, request_id=f"pg-audit-{index}"),
            ).record(
                action="concurrent_append",
                resource_type="PG_AUDIT",
                resource_id=index,
                detail={"index": index},
            )
            session.commit()
            return int(row.sequence_no)

    with ThreadPoolExecutor(max_workers=8) as pool:
        sequences = list(pool.map(append, range(8)))
    assert sorted(sequences) == list(range(before_sequence + 1, before_sequence + 9))
    with Session() as session:
        states, summary = AuditRepository(session, _context(tenant_id, user_id)).verify_chain()
        assert summary["state"] == "VERIFIED", summary
        rows = list(
            session.scalars(
                select(AuditLog).where(
                    AuditLog.tenant_id == tenant_id,
                    AuditLog.sequence_no.in_(sequences),
                )
            ).all()
        )
        assert len(rows) == 8
        assert all(states[int(row.id)] == "VERIFIED" for row in rows)
    engine.dispose()


def test_pg_approval_audit_schema_constraints_and_indexes() -> None:
    engine, _ = _factory()
    inspector = inspect(engine)
    required = {
        "approval_definitions",
        "approval_definition_versions",
        "approval_definition_steps",
        "approval_step_assignees",
        "approval_delegations",
        "approval_tasks",
        "audit_chain_heads",
    }
    assert required <= set(inspector.get_table_names())
    task_indexes = {row["name"]: row for row in inspector.get_indexes("approval_tasks")}
    audit_indexes = {row["name"]: row for row in inspector.get_indexes("audit_logs")}
    assert task_indexes["uk_approval_task_decision_key"]["unique"] is True
    assert audit_indexes["uk_audit_logs_tenant_sequence"]["unique"] is True
    request_columns = {row["name"]: row for row in inspector.get_columns("approval_requests")}
    assert request_columns["round_no"]["nullable"] is False
    assert request_columns["lock_version"]["nullable"] is False
    engine.dispose()

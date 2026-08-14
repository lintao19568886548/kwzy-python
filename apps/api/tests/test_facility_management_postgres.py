"""PostgreSQL 16 constraints and concurrency for facility management."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.models.facility_management import (
    InspectionTask,
    IoTAlarm,
    IoTAlarmEvent,
    IoTDeviceBinding,
)
from app.infrastructure.database.models.identity import Tenant, User
from app.infrastructure.database.models.park_property import Park
from app.modules.facility_ops.application.facility_management_service import (
    FacilityManagementService,
)
from app.modules.identity.application.bootstrap import ensure_default_tenant
from app.shared.tenant_context import ParkScopeMode, TenantContext
from app.workers.facility_ops import run_cycle

pytestmark = pytest.mark.pg


def _url() -> str:
    value = os.environ.get("TEST_DATABASE_URL") or os.environ.get("POSTGRES_TEST_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL / POSTGRES_TEST_URL not set")
    if not value.startswith("postgresql") or "sqlite" in value.lower():
        pytest.fail("facility-management acceptance requires PostgreSQL")
    parsed = make_url(value)
    if parsed.host not in {"127.0.0.1", "localhost"}:
        pytest.fail("facility-management acceptance is restricted to loopback PostgreSQL")
    if (parsed.database or "").lower() != "kwzy_party_test":
        pytest.fail("facility-management acceptance requires the disposable kwzy_party_test DB")
    return value


def _factory():
    engine = create_engine(_url(), pool_pre_ping=True, pool_size=8, max_overflow=8)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _ctx(tenant_id: int, user_id: int) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        username="facility-pg",
        permissions=["*"],
        park_ids=[],
        park_scope_mode=ParkScopeMode.ALL,
    )


def _seed() -> dict[str, int]:
    _, Session = _factory()
    suffix = uuid4().hex[:10]
    with Session() as session:
        tenant = ensure_default_tenant(session)
        park = Park(tenant_id=tenant.id, name=f"设施PG园-{suffix}", status="ACTIVE")
        user = User(
            tenant_id=tenant.id,
            username=f"facility_pg_{suffix}",
            password_hash="synthetic-not-a-login-secret",
            real_name="设施PG巡检员",
            status="ACTIVE",
            all_parks=True,
        )
        foreign_tenant = Tenant(
            code=f"facility-foreign-{suffix}",
            name=f"设施外租户-{suffix}",
            status="ACTIVE",
            db_strategy="SHARED",
        )
        session.add_all([park, user, foreign_tenant])
        session.commit()
        return {
            "tenant_id": int(tenant.id),
            "park_id": int(park.id),
            "user_id": int(user.id),
            "foreign_tenant_id": int(foreign_tenant.id),
        }


def _prepare_lifecycle(seed: dict[str, int]) -> dict[str, int]:
    _, Session = _factory()
    with Session() as session:
        service = FacilityManagementService(
            session, _ctx(seed["tenant_id"], seed["user_id"])
        )
        device = service.create_device(
            {
                "park_id": seed["park_id"],
                "device_code": f"PG-FIRE-{uuid4().hex[:8]}",
                "name": "PG消防泵",
                "device_type": "FIRE",
                "location": "PG泵房",
                "criticality": "CRITICAL",
                "properties": {"rated_power_kw": 45},
            }
        )
        template = service.create_template(
            {
                "code": f"PG_FIRE_{uuid4().hex[:8]}",
                "name": "PG消防周检",
                "device_type": "FIRE",
                "items": [
                    {
                        "item_code": "RUNNING",
                        "label": "运行状态",
                        "result_type": "BOOLEAN",
                        "critical": True,
                    }
                ],
            }
        )
        version = template["versions"][0]
        published = service.publish_template_version(
            version["id"], expected_version=version["lock_version"]
        )
        now = datetime.now(timezone.utc)
        local_due = now + timedelta(hours=8, minutes=30)
        schedule = service.create_schedule(
            {
                "park_id": seed["park_id"],
                "code": f"PG-SCHEDULE-{uuid4().hex[:8]}",
                "name": "PG消防泵周检",
                "device_id": device["id"],
                "template_version_id": published["id"],
                "assignee_user_id": seed["user_id"],
                "timezone": "Asia/Shanghai",
                "weekday": local_due.isoweekday(),
                "local_due_time": local_due.strftime("%H:%M"),
                "completion_window_minutes": 10080,
                "missed_work_order": True,
            }
        )
        provider = service.create_provider(
            {
                "code": f"PG_SANDBOX_{uuid4().hex[:8]}",
                "name": "PG IoT 沙箱",
                "adapter_kind": "SANDBOX",
                "severity_mapping": {},
                "correlation_minutes": 30,
            }
        )
        binding = service.create_binding(
            {
                "provider_id": provider["id"],
                "device_id": device["id"],
                "external_device_key": f"pg-fire-{uuid4().hex[:8]}",
                "reason": "PG并发验收",
            }
        )
        return {
            **seed,
            "device_id": int(device["id"]),
            "schedule_id": int(schedule["id"]),
            "provider_id": int(provider["id"]),
            "binding_id": int(binding["id"]),
            "external_device_key": binding["external_device_key"],
        }


def test_pg_facility_schema_indexes_types_and_tenant_constraints() -> None:
    seed = _prepare_lifecycle(_seed())
    engine, Session = _factory()
    inspector = inspect(engine)
    with engine.connect() as connection:
        assert str(connection.scalar(text("SHOW server_version"))).split(".")[0] == "16"
    assert {
        "facility_devices",
        "facility_device_history",
        "inspection_templates",
        "inspection_template_versions",
        "inspection_template_items",
        "inspection_schedules",
        "inspection_tasks",
        "inspection_results",
        "inspection_exceptions",
        "iot_providers",
        "iot_device_bindings",
        "iot_alarms",
        "iot_alarm_events",
        "iot_alarm_escalations",
    }.issubset(set(inspector.get_table_names()))
    missed_type = next(
        column
        for column in inspector.get_columns("inspection_schedules")
        if column["name"] == "missed_work_order"
    )["type"]
    assert missed_type.__class__.__name__.upper() == "BOOLEAN"
    device_indexes = {item["name"] for item in inspector.get_indexes("facility_devices")}
    assert "ix_facility_device_queue" in device_indexes
    alarm_indexes = {item["name"] for item in inspector.get_indexes("iot_alarms")}
    assert {"ix_iot_alarm_queue", "uk_iot_alarm_active_correlation"} <= alarm_indexes
    task_foreign_keys = {
        item["name"] for item in inspector.get_foreign_keys("inspection_tasks")
    }
    assert {
        "fk_inspection_task_schedule",
        "fk_inspection_task_device",
        "fk_inspection_task_template_version",
        "fk_inspection_task_assignee",
    } <= task_foreign_keys

    with Session() as session:
        invalid = IoTDeviceBinding(
            tenant_id=seed["foreign_tenant_id"],
            park_id=seed["park_id"],
            provider_id=seed["provider_id"],
            device_id=seed["device_id"],
            external_device_key=f"cross-tenant-{uuid4().hex}",
            status="ACTIVE",
            lock_version=1,
            activated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            change_reason="跨租户引用必须失败",
        )
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(invalid)
            session.flush()


def test_pg_task_generation_and_alarm_ingest_are_serialized_and_idempotent() -> None:
    seed = _prepare_lifecycle(_seed())
    _, Session = _factory()
    reference = datetime.now(timezone.utc)
    barrier = threading.Barrier(2)

    def generate() -> dict[str, object]:
        with Session() as session:
            barrier.wait(timeout=15)
            return FacilityManagementService(
                session, _ctx(seed["tenant_id"], seed["user_id"])
            ).generate_tasks(as_of=reference)

    with ThreadPoolExecutor(max_workers=2) as pool:
        generated = [future.result(timeout=30) for future in [pool.submit(generate) for _ in range(2)]]
    with Session() as session:
        target_task_ids = list(
            session.scalars(
                select(InspectionTask.id).where(
                    InspectionTask.schedule_id == seed["schedule_id"]
                )
            ).all()
        )
    assert len(target_task_ids) == 1
    target_task_id = int(target_task_ids[0])
    assert all(
        target_task_id in set(result["created_ids"]) | set(result["existing_ids"])
        for result in generated
    )

    event_barrier = threading.Barrier(2)
    event_ids = [f"pg-event-{uuid4()}", f"pg-event-{uuid4()}"]

    def ingest(source_event_id: str) -> int:
        with Session() as session:
            event_barrier.wait(timeout=15)
            result = FacilityManagementService(
                session, _ctx(seed["tenant_id"], seed["user_id"])
            ).ingest_alarm(
                {
                    "provider_id": seed["provider_id"],
                    "external_device_key": seed["external_device_key"],
                    "source_event_id": source_event_id,
                    "source_time": datetime.now(timezone.utc),
                    "alarm_type": "START_FAILURE",
                    "title": "PG消防泵启动失败",
                    "severity": "CRITICAL",
                    "payload": {"error_code": source_event_id[-8:]},
                }
            )
            return int(result["alarm"]["id"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        alarm_ids = [
            future.result(timeout=30)
            for future in [pool.submit(ingest, event_id) for event_id in event_ids]
        ]
    assert len(set(alarm_ids)) == 1
    with Session() as session:
        alarm = session.get(IoTAlarm, alarm_ids[0])
        assert alarm is not None
        assert int(alarm.occurrence_count) == 2
        assert int(
            session.scalar(
                select(func.count(IoTAlarmEvent.id)).where(
                    IoTAlarmEvent.alarm_id == alarm_ids[0]
                )
            )
            or 0
        ) == 2
        assert int(
            session.scalar(
                select(func.count(InspectionTask.id)).where(
                    InspectionTask.schedule_id == seed["schedule_id"]
                )
            )
            or 0
        ) == 1

    replay_id = event_ids[0]
    with Session() as session:
        replay = FacilityManagementService(
            session, _ctx(seed["tenant_id"], seed["user_id"])
        ).ingest_alarm(
            {
                "provider_id": seed["provider_id"],
                "external_device_key": seed["external_device_key"],
                "source_event_id": replay_id,
                "source_time": session.scalar(
                    select(IoTAlarmEvent.source_time).where(
                        IoTAlarmEvent.source_event_id == replay_id
                    )
                ),
                "alarm_type": "START_FAILURE",
                "title": "PG消防泵启动失败",
                "severity": "CRITICAL",
                "payload": {"error_code": replay_id[-8:]},
            }
        )
        assert replay["replayed"] is True
        assert int(replay["alarm"]["id"]) == alarm_ids[0]


def test_pg_facility_worker_is_tenant_isolated_and_repeat_safe() -> None:
    seed = _prepare_lifecycle(_seed())
    _, Session = _factory()
    first = run_cycle(Session, worker_id="facility-pg-worker-a")
    second = run_cycle(Session, worker_id="facility-pg-worker-b")
    assert first["failed_tenants"] == 0
    assert second["failed_tenants"] == 0
    with Session() as session:
        task_count = int(
            session.scalar(
                select(func.count(InspectionTask.id)).where(
                    InspectionTask.schedule_id == seed["schedule_id"]
                )
            )
            or 0
        )
    assert task_count == 1

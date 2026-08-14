"""PostgreSQL 16 race and rollback gates for the Lease V2 aggregate."""

from __future__ import annotations

import hashlib
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.attachment import Attachment
from app.infrastructure.database.models.audit import AuditLog
from app.infrastructure.database.models.investment import (
    LeadIntentApplication,
    LeadIntentUnit,
    LeadIntentVersion,
    LeadUnitLock,
)
from app.infrastructure.database.models.lease import (
    LeaseChangeOrder,
    LeaseContract,
    LeaseContractVersion,
    LeaseExitSettlement,
    LeasePerformanceSchedule,
)
from app.infrastructure.database.models.park_property import Unit
from app.infrastructure.database.models.workbench import WorkItem
from app.infrastructure.database.models.workflow import ApprovalRequest
from app.modules.identity.application.bootstrap import ensure_default_tenant
from app.modules.investment.application.lead_service import LeadService
from app.modules.lease.application.contract_lifecycle_service import ContractLifecycleService
from app.modules.lease.application.lease_service import LeaseService
from app.modules.park_property.application.park_service import ParkService
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
        pytest.fail("Lease V2 race tests require localhost PostgreSQL")
    if "kwzy_party_test" not in url:
        pytest.fail("database name must include kwzy_party_test")
    return url


def _factory():
    engine = create_engine(_require_pg_url(), pool_pre_ping=True, pool_size=6, max_overflow=2)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _ctx(tenant_id: int) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        user_id=1,
        username="lease-v2-pg",
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
    version = LeadIntentVersion(
        tenant_id=tenant_id,
        application_id=int(application.id),
        version=1,
        starts_on=date.today(),
        ends_on=date.today() + timedelta(days=365),
        valid_until=utc_now() + timedelta(days=30),
        proposed_unit_price=Decimal("1.00"),
        currency="CNY",
        checksum=f"lease-pg-approved-{application.id}-{uuid4().hex}",
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
        title="合同并发测试批准意向",
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


def _seed_contract(Session) -> dict[str, int]:
    suffix = uuid4().hex[:10].upper()
    with Session() as session:
        tenant_id = int(ensure_default_tenant(session).id)
        session.commit()
        ctx = _ctx(tenant_id)
        park = ParkService(session, ctx).create_park({"name": f"合同并发园-{suffix}"})
        party = PartyService(session, ctx).create_party(
            {"name": f"合同并发主体-{suffix}", "party_type": "ORGANIZATION"}
        )
        contract = LeaseService(session, ctx).create_contract(
            {
                "park_id": park["id"],
                "party_id": party["id"],
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "deposit_amount": "1000",
            }
        )
        return {
            "tenant_id": tenant_id,
            "park_id": int(park["id"]),
            "contract_id": int(contract["id"]),
        }


def _seed_v2_draft(
    Session,
    *,
    tenant_id: int | None = None,
    park_id: int | None = None,
    unit_id: int | None = None,
    occupied_area: str = "80",
) -> dict[str, int]:
    suffix = uuid4().hex[:10].upper()
    with Session() as session:
        resolved_tenant_id = tenant_id or int(ensure_default_tenant(session).id)
        session.commit()
        ctx = _ctx(resolved_tenant_id)
        resolved_park_id = park_id
        if resolved_park_id is None:
            park = ParkService(session, ctx).create_park({"name": f"合同V2行锁园-{suffix}"})
            resolved_park_id = int(park["id"])
        resolved_unit_id = unit_id
        if resolved_unit_id is None:
            unit = UnitService(session, ctx).create_unit(
                {
                    "park_id": resolved_park_id,
                    "name": f"PG-{suffix}",
                    "code": f"PG{suffix}",
                    "rentable_area": "100",
                    "status": "VACANT",
                }
            )
            resolved_unit_id = int(unit["id"])
        party = PartyService(session, ctx).create_party(
            {"name": f"合同V2行锁主体-{suffix}", "party_type": "ORGANIZATION"}
        )
        draft = ContractLifecycleService(session, ctx).create_draft(
            {
                "park_id": resolved_park_id,
                "party_id": int(party["id"]),
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "deposit_amount": "1000",
                "units": [
                    {
                        "unit_id": resolved_unit_id,
                        "occupied_area": occupied_area,
                        "unit_rent_price": "5",
                    }
                ],
                "charges": [
                    {
                        "charge_code": "RENT",
                        "charge_type": "RENT",
                        "calculation_method": "FIXED",
                        "billing_cycle": "MONTHLY",
                        "start_date": "2026-01-01",
                        "end_date": "2026-12-31",
                        "amount": "1000",
                    }
                ],
            }
        )
        return {
            "tenant_id": resolved_tenant_id,
            "park_id": resolved_park_id,
            "unit_id": resolved_unit_id,
            "contract_id": int(draft["id"]),
            "expected_version": int(draft["lock_version"]),
        }


def _prepare_pending_active(Session, seed: dict[str, int]) -> dict[str, int]:
    with Session() as session:
        svc = ContractLifecycleService(session, _ctx(seed["tenant_id"]))
        submitted = svc.submit(
            seed["contract_id"],
            expected_version=seed["expected_version"],
            remark="PostgreSQL 行锁验收",
        )
        approved = svc.decide(
            seed["contract_id"],
            approval_id=int(submitted["pending_approval"]["id"]),
            approve=True,
            expected_version=int(submitted["contract"]["lock_version"]),
            remark="同意",
            override_reason="本地 PostgreSQL 合成验收",
        )
        checksum = hashlib.sha256(f"pg-document-{uuid4()}".encode()).hexdigest()
        attachment = Attachment(
            tenant_id=seed["tenant_id"],
            park_id=seed["park_id"],
            biz_type="LEASE_CONTRACT",
            biz_id=str(seed["contract_id"]),
            filename="pg-contract.txt",
            content_type="text/plain",
            size_bytes=32,
            object_key=f"test/contracts/{uuid4().hex}.txt",
            etag=checksum,
            uploaded_by=1,
            status="ACTIVE",
        )
        session.add(attachment)
        session.flush()
        document_state = svc.add_document(
            seed["contract_id"],
            expected_version=int(approved["contract"]["lock_version"]),
            attachment_id=int(attachment.id),
            document_type="MAIN_CONTRACT",
            checksum=checksum,
            is_main=True,
        )
        draft_document = document_state["documents"][-1]
        approved_document = svc.advance_document(
            seed["contract_id"],
            int(draft_document["id"]),
            expected_version=int(document_state["contract"]["lock_version"]),
            target_status="APPROVED",
        )
        return {
            **seed,
            "expected_version": int(approved_document["contract"]["lock_version"]),
        }


def _activate_prepared(Session, seed: dict[str, int]) -> dict[str, int]:
    with Session() as session:
        state = ContractLifecycleService(session, _ctx(seed["tenant_id"])).activate(
            seed["contract_id"], expected_version=seed["expected_version"]
        )
        return {**seed, "expected_version": int(state["contract"]["lock_version"])}


def _prepare_approved_renewal(Session, seed: dict[str, int]) -> dict[str, int]:
    active = _activate_prepared(Session, seed)
    with Session() as session:
        svc = ContractLifecycleService(session, _ctx(active["tenant_id"]))
        model = session.get(LeaseContract, active["contract_id"])
        assert model is not None
        proposal = deepcopy(svc._current_snapshot(model))
        proposal["contract"]["end_date"] = "2027-12-31"
        proposal["charges"][0]["end_date"] = "2027-12-31"
        created = svc.create_change(
            active["contract_id"],
            expected_version=int(model.lock_version),
            change_type="RENEWAL",
            effective_date="2027-01-01",
            reason="PostgreSQL 并发续租",
            proposed_snapshot=proposal,
        )
        change_id = int(created["changes"][-1]["id"])
        submitted = svc.submit_change(
            change_id,
            expected_version=int(created["contract"]["lock_version"]),
            remark="PostgreSQL 并发审批",
        )
        approved = svc.decide_change(
            change_id,
            approve=True,
            expected_version=int(submitted["contract"]["lock_version"]),
            remark="同意",
            override_reason="本地 PostgreSQL 合成验收",
        )
        return {
            **active,
            "change_id": change_id,
            "expected_version": int(approved["contract"]["lock_version"]),
        }


def _prepare_approved_exit(
    Session, seed: dict[str, int], *, deduction_amount: str
) -> dict[str, int]:
    active = _activate_prepared(Session, seed)
    with Session() as session:
        svc = ContractLifecycleService(session, _ctx(active["tenant_id"]))
        created = svc.create_exit(
            active["contract_id"],
            expected_version=active["expected_version"],
            handover_date="2026-12-31",
            inspection_summary="PostgreSQL 退租交接",
        )
        settlement_id = int(created["exit_settlement"]["id"])
        edited = svc.edit_exit(
            settlement_id,
            expected_version=1,
            meter_readings=[
                {"meter_code": "POWER", "previous_reading": "10", "current_reading": "12"}
            ],
            items=[
                {
                    "item_type": "DEDUCTION",
                    "amount": deduction_amount,
                    "description": "PostgreSQL 合成扣减",
                }
            ],
            inspection_summary="验房完成",
        )
        submitted = svc.submit_exit(
            settlement_id,
            expected_version=int(edited["exit_settlement"]["lock_version"]),
            contract_expected_version=int(created["contract"]["lock_version"]),
            remark="PostgreSQL 退租审批",
        )
        approved = svc.decide_exit(
            settlement_id,
            approve=True,
            expected_version=int(submitted["exit_settlement"]["lock_version"]),
            remark="同意",
            override_reason="本地 PostgreSQL 合成验收",
        )
        checksum = hashlib.sha256(f"pg-exit-{uuid4()}".encode()).hexdigest()
        attachment = Attachment(
            tenant_id=active["tenant_id"],
            park_id=active["park_id"],
            biz_type="LEASE_EXIT_SETTLEMENT",
            biz_id=str(settlement_id),
            filename="pg-exit-evidence.txt",
            content_type="text/plain",
            size_bytes=32,
            object_key=f"test/exits/{uuid4().hex}.txt",
            etag=checksum,
            uploaded_by=1,
            status="ACTIVE",
        )
        session.add(attachment)
        session.flush()
        cleared = svc.confirm_clearance(
            settlement_id,
            expected_version=int(approved["exit_settlement"]["lock_version"]),
            evidence_attachment_id=int(attachment.id),
            reference=f"PG-CLEAR-{uuid4().hex[:12]}",
            reason="本地 PostgreSQL 合成线下清算凭证复核",
        )
        exit_document = svc.add_document(
            active["contract_id"],
            expected_version=int(cleared["contract"]["lock_version"]),
            attachment_id=int(attachment.id),
            document_type="EXIT_HANDOVER",
            checksum=checksum,
            is_main=False,
            exit_settlement_id=settlement_id,
        )
        draft_document = next(
            row
            for row in exit_document["documents"]
            if row["document_type"] == "EXIT_HANDOVER" and row["status"] == "DRAFT"
        )
        document_approved = svc.advance_document(
            active["contract_id"],
            int(draft_document["id"]),
            expected_version=int(exit_document["contract"]["lock_version"]),
            target_status="APPROVED",
        )
        return {
            **active,
            "settlement_id": settlement_id,
            "settlement_expected_version": int(
                cleared["exit_settlement"]["lock_version"]
            ),
            "expected_version": int(document_approved["contract"]["lock_version"]),
        }


def _change(seed: dict[str, int], marker: str, *, status: str = "SUBMITTED") -> LeaseChangeOrder:
    return LeaseChangeOrder(
        tenant_id=seed["tenant_id"],
        park_id=seed["park_id"],
        contract_id=seed["contract_id"],
        change_no=f"PG-CHG-{marker}",
        change_type="RENEWAL",
        status=status,
        base_version_no=1,
        effective_date=date(2026, 12, 31),
        reason="PostgreSQL race gate",
        proposal_json={"schema_version": 1, "marker": marker},
        proposal_checksum=(marker.lower() * 64)[:64],
        proposal_schema_version=1,
        lock_version=1,
    )


def _exit(seed: dict[str, int], marker: str) -> LeaseExitSettlement:
    return LeaseExitSettlement(
        tenant_id=seed["tenant_id"],
        park_id=seed["park_id"],
        contract_id=seed["contract_id"],
        settlement_no=f"PG-EXIT-{marker}",
        contract_version_no=1,
        status="DRAFT",
        handover_date=date(2026, 12, 31),
        held_deposit_amount=Decimal("1000"),
        outstanding_amount=Decimal("0"),
        outstanding_source="BILLING_SCOPED_READ",
        outstanding_as_of=utc_now(),
        receivable_total=Decimal("0"),
        deduction_total=Decimal("0"),
        refund_adjustment_total=Decimal("0"),
        net_due_from_party=Decimal("0"),
        net_due_to_party=Decimal("1000"),
        financial_clearance_status="UNCONFIRMED",
        checksum=(marker.lower() * 64)[:64],
        lock_version=1,
    )


def test_pg_contract_partial_indexes_are_present() -> None:
    engine, _ = _factory()
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT indexname, indexdef FROM pg_indexes "
                    "WHERE schemaname='public' AND indexname IN "
                    "('uk_lease_change_inflight', 'uk_lease_exit_open')"
                )
            ).all()
        definitions = {str(name): str(definition) for name, definition in rows}
        assert "UNIQUE" in definitions["uk_lease_change_inflight"]
        assert "SUBMITTED" in definitions["uk_lease_change_inflight"]
        assert "UNIQUE" in definitions["uk_lease_exit_open"]
        assert "APPROVED" in definitions["uk_lease_exit_open"]
    finally:
        engine.dispose()


def test_pg_concurrent_inflight_changes_have_one_winner() -> None:
    engine, Session = _factory()
    seed = _seed_contract(Session)
    run_marker = uuid4().hex[:10].upper()
    barrier = threading.Barrier(2)

    def insert(marker: str) -> str:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                session.add(_change(seed, marker))
                session.commit()
                return "ok"
            except IntegrityError:
                session.rollback()
                return "conflict"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(insert, (f"{run_marker}-A", f"{run_marker}-B")))
        assert sorted(results) == ["conflict", "ok"]
        with Session() as session:
            count = session.scalar(
                select(func.count(LeaseChangeOrder.id)).where(
                    LeaseChangeOrder.contract_id == seed["contract_id"],
                    LeaseChangeOrder.status.in_(("SUBMITTED", "APPROVED")),
                )
            )
            assert int(count or 0) == 1
    finally:
        engine.dispose()


def test_pg_concurrent_open_exits_have_one_winner() -> None:
    engine, Session = _factory()
    seed = _seed_contract(Session)
    run_marker = uuid4().hex[:10].upper()
    barrier = threading.Barrier(2)

    def insert(marker: str) -> str:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                session.add(_exit(seed, marker))
                session.commit()
                return "ok"
            except IntegrityError:
                session.rollback()
                return "conflict"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(insert, (f"{run_marker}-C", f"{run_marker}-D")))
        assert sorted(results) == ["conflict", "ok"]
        with Session() as session:
            count = session.scalar(
                select(func.count(LeaseExitSettlement.id)).where(
                    LeaseExitSettlement.contract_id == seed["contract_id"],
                    LeaseExitSettlement.status.in_(("DRAFT", "SUBMITTED", "APPROVED")),
                )
            )
            assert int(count or 0) == 1
    finally:
        engine.dispose()


def test_pg_unique_violation_rolls_back_contract_mutation() -> None:
    engine, Session = _factory()
    seed = _seed_contract(Session)
    marker = uuid4().hex[:10].upper()
    try:
        with Session() as session:
            session.add(_change(seed, f"ROLLBACK-BASE-{marker}"))
            session.commit()
        with Session() as session:
            contract = session.get(LeaseContract, seed["contract_id"])
            assert contract is not None
            contract.status = "ACTIVE"
            session.add(_change(seed, f"ROLLBACK-LOSER-{marker}", status="APPROVED"))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
        with Session() as session:
            contract = session.get(LeaseContract, seed["contract_id"])
            assert contract is not None
            assert contract.status == "DRAFT"
            count = session.scalar(
                select(func.count(LeaseChangeOrder.id)).where(
                    LeaseChangeOrder.contract_id == seed["contract_id"]
                )
            )
            assert int(count or 0) == 1
    finally:
        engine.dispose()


def test_pg_concurrent_submit_has_one_versioned_winner() -> None:
    engine, Session = _factory()
    seed = _seed_v2_draft(Session)
    barrier = threading.Barrier(2)

    def submit(marker: str) -> str:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                ContractLifecycleService(session, _ctx(seed["tenant_id"])).submit(
                    seed["contract_id"],
                    expected_version=seed["expected_version"],
                    remark=f"concurrent-{marker}",
                )
                return "ok"
            except AppError as exc:
                session.rollback()
                return exc.code

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, ("A", "B")))
        assert results.count("ok") == 1
        assert results.count("LEASE_VERSION_CONFLICT") == 1
        with Session() as session:
            contract = session.get(LeaseContract, seed["contract_id"])
            assert contract is not None
            assert contract.status == "PENDING_APPROVAL"
            assert int(contract.lock_version) == seed["expected_version"] + 1
            approvals = session.scalar(
                select(func.count(ApprovalRequest.id)).where(
                    ApprovalRequest.biz_type == "LEASE_CONTRACT_VERSION",
                    ApprovalRequest.biz_id.like(f"{seed['contract_id']}:%"),
                )
            )
            assert int(approvals or 0) == 1
    finally:
        engine.dispose()


def test_pg_concurrent_activation_enforces_unit_capacity() -> None:
    engine, Session = _factory()
    first = _seed_v2_draft(Session, occupied_area="80")
    second = _seed_v2_draft(
        Session,
        tenant_id=first["tenant_id"],
        park_id=first["park_id"],
        unit_id=first["unit_id"],
        occupied_area="80",
    )
    first = _prepare_pending_active(Session, first)
    second = _prepare_pending_active(Session, second)
    barrier = threading.Barrier(2)

    def activate(seed: dict[str, int]) -> str:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                ContractLifecycleService(session, _ctx(seed["tenant_id"])).activate(
                    seed["contract_id"], expected_version=seed["expected_version"]
                )
                return "ok"
            except AppError as exc:
                session.rollback()
                return exc.code

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(activate, (first, second)))
        assert sorted(results) == ["OCCUPANCY_CONFLICT", "ok"]
        with Session() as session:
            active_count = session.scalar(
                select(func.count(LeaseContract.id)).where(
                    LeaseContract.id.in_((first["contract_id"], second["contract_id"])),
                    LeaseContract.status == "ACTIVE",
                )
            )
            unit = session.get(Unit, first["unit_id"])
            assert int(active_count or 0) == 1
            assert unit is not None
            assert Decimal(str(unit.used_area)) == Decimal("80")
            assert unit.status == "OCCUPIED"
    finally:
        engine.dispose()


def test_pg_crm_lock_and_activation_share_unit_write_lock() -> None:
    engine, Session = _factory()
    seed = _prepare_pending_active(Session, _seed_v2_draft(Session))
    with Session() as session:
        lead = LeadService(session, _ctx(seed["tenant_id"])).create_lead(
            {
                "park_id": seed["park_id"],
                "name": f"PG竞态线索-{uuid4().hex[:8]}",
                "contact_phone": f"139{uuid4().int % 100000000:08d}",
            }
        )
        lead_id = int(lead["id"])
        lead_version = int(lead["lock_version"])
        intent_id = _approved_intent(
            session,
            tenant_id=seed["tenant_id"],
            park_id=seed["park_id"],
            lead_id=lead_id,
            unit_id=seed["unit_id"],
        )
    barrier = threading.Barrier(2)

    def activate() -> tuple[str, str]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                ContractLifecycleService(session, _ctx(seed["tenant_id"])).activate(
                    seed["contract_id"], expected_version=seed["expected_version"]
                )
                return ("activate", "ok")
            except AppError as exc:
                session.rollback()
                return ("activate", exc.code)

    def acquire() -> tuple[str, str]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                LeadService(session, _ctx(seed["tenant_id"])).acquire_unit_lock(
                    lead_id,
                    unit_id=seed["unit_id"],
                    expected_version=lead_version,
                    intent_id=intent_id,
                )
                return ("lock", "ok")
            except AppError as exc:
                session.rollback()
                return ("lock", exc.code)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = (pool.submit(activate), pool.submit(acquire))
            results = dict(future.result(timeout=30) for future in futures)
        assert list(results.values()).count("ok") == 1
        assert results in (
            {"activate": "ok", "lock": "UNIT_NOT_AVAILABLE"},
            {"activate": "UNIT_ALREADY_LOCKED", "lock": "ok"},
        )
        with Session() as session:
            contract = session.get(LeaseContract, seed["contract_id"])
            active_lock_count = session.scalar(
                select(func.count(LeadUnitLock.id)).where(
                    LeadUnitLock.unit_id == seed["unit_id"],
                    LeadUnitLock.status == "ACTIVE",
                )
            )
            assert contract is not None
            assert (contract.status == "ACTIVE") != (int(active_lock_count or 0) == 1)
    finally:
        engine.dispose()


def test_pg_concurrent_change_replay_and_stale_base_are_fail_closed() -> None:
    engine, Session = _factory()
    seed = _prepare_approved_renewal(
        Session, _prepare_pending_active(Session, _seed_v2_draft(Session))
    )
    replay_key = f"pg-concurrent-renewal-{uuid4().hex}"
    barrier = threading.Barrier(2)

    def apply() -> str:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                ContractLifecycleService(session, _ctx(seed["tenant_id"])).apply_change(
                    seed["change_id"],
                    expected_version=seed["expected_version"],
                    idempotency_key=replay_key,
                    as_of=date(2027, 1, 1),
                )
                return "ok"
            except AppError as exc:
                session.rollback()
                return exc.code

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert list(pool.map(lambda _: apply(), (1, 2))) == ["ok", "ok"]
        with Session() as session:
            contract = session.get(LeaseContract, seed["contract_id"])
            versions = session.scalar(
                select(func.count(LeaseContractVersion.id)).where(
                    LeaseContractVersion.contract_id == seed["contract_id"]
                )
            )
            assert contract is not None
            assert contract.current_version_no == 2
            assert int(versions or 0) == 2
            stale = _change(seed, f"STALE-{uuid4().hex[:8]}", status="APPROVED")
            session.add(stale)
            session.commit()
            stale_id = int(stale.id)
            current_lock_version = int(contract.lock_version)
        with Session() as session:
            with pytest.raises(AppError) as captured:
                ContractLifecycleService(session, _ctx(seed["tenant_id"])).apply_change(
                    stale_id,
                    expected_version=current_lock_version,
                    idempotency_key="pg-stale-base",
                    as_of=date(2027, 1, 1),
                )
            session.rollback()
        assert captured.value.code == "LEASE_CHANGE_BASE_VERSION_CONFLICT"
    finally:
        engine.dispose()


def test_pg_submit_failure_rolls_back_approval_work_item_and_audit(monkeypatch) -> None:
    engine, Session = _factory()
    seed = _seed_v2_draft(Session)
    try:
        with Session() as session:
            svc = ContractLifecycleService(session, _ctx(seed["tenant_id"]))

            def fail_audit(**_kwargs) -> None:
                raise RuntimeError("synthetic audit failure")

            monkeypatch.setattr(svc.audit, "record", fail_audit)
            with pytest.raises(RuntimeError, match="synthetic audit failure"):
                svc.submit(
                    seed["contract_id"],
                    expected_version=seed["expected_version"],
                    remark="rollback",
                )
            session.rollback()
        with Session() as session:
            contract = session.get(LeaseContract, seed["contract_id"])
            approvals = session.scalar(
                select(func.count(ApprovalRequest.id)).where(
                    ApprovalRequest.biz_type == "LEASE_CONTRACT_VERSION",
                    ApprovalRequest.biz_id.like(f"{seed['contract_id']}:%"),
                )
            )
            work_items = session.scalar(
                select(func.count(WorkItem.id)).where(
                    WorkItem.item_type == "LEASE_CONTRACT_APPROVAL",
                    WorkItem.park_id == seed["park_id"],
                )
            )
            audit_rows = session.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.resource_type == "LEASE_CONTRACT",
                    AuditLog.resource_id == str(seed["contract_id"]),
                    AuditLog.action == "submit_v2",
                )
            )
            assert contract is not None
            assert contract.status == "DRAFT"
            assert contract.lock_version == seed["expected_version"]
            assert int(approvals or 0) == 0
            assert int(work_items or 0) == 0
            assert int(audit_rows or 0) == 0
    finally:
        engine.dispose()


def test_pg_activation_failure_rolls_back_version_schedule_unit_and_work_item(
    monkeypatch,
) -> None:
    engine, Session = _factory()
    seed = _prepare_pending_active(Session, _seed_v2_draft(Session))
    try:
        with Session() as session:
            svc = ContractLifecycleService(session, _ctx(seed["tenant_id"]))

            def fail_audit(**_kwargs) -> None:
                raise RuntimeError("synthetic activation audit failure")

            monkeypatch.setattr(svc.audit, "record", fail_audit)
            with pytest.raises(RuntimeError, match="synthetic activation audit failure"):
                svc.activate(
                    seed["contract_id"], expected_version=seed["expected_version"]
                )
            session.rollback()
        with Session() as session:
            contract = session.get(LeaseContract, seed["contract_id"])
            unit = session.get(Unit, seed["unit_id"])
            versions = session.scalar(
                select(func.count(LeaseContractVersion.id)).where(
                    LeaseContractVersion.contract_id == seed["contract_id"]
                )
            )
            schedules = session.scalar(
                select(func.count(LeasePerformanceSchedule.id)).where(
                    LeasePerformanceSchedule.contract_id == seed["contract_id"],
                    LeasePerformanceSchedule.contract_version_no == 1,
                )
            )
            work_items = session.scalar(
                select(func.count(WorkItem.id)).where(
                    WorkItem.source_type == "LEASE",
                    WorkItem.source_id == str(seed["contract_id"]),
                    WorkItem.item_type == "CONTRACT_EXPIRING",
                )
            )
            audit_rows = session.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.resource_type == "LEASE_CONTRACT",
                    AuditLog.resource_id == str(seed["contract_id"]),
                    AuditLog.action == "activate_v2",
                )
            )
            assert contract is not None and unit is not None
            assert contract.status == "PENDING_ACTIVE"
            assert contract.current_version_no == 0
            assert contract.lock_version == seed["expected_version"]
            assert unit.status == "VACANT"
            assert Decimal(str(unit.used_area)) == Decimal("0")
            assert int(versions or 0) == 0
            assert int(schedules or 0) == 0
            assert int(work_items or 0) == 0
            assert int(audit_rows or 0) == 0
    finally:
        engine.dispose()


def test_pg_exit_close_retains_occupancy_then_replays_once() -> None:
    engine, Session = _factory()
    seed = _prepare_approved_exit(
        Session,
        _prepare_pending_active(Session, _seed_v2_draft(Session)),
        deduction_amount="200",
    )
    replay_key = f"pg-exit-close-{uuid4().hex}"
    barrier = threading.Barrier(2)

    def close() -> str:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                ContractLifecycleService(session, _ctx(seed["tenant_id"])).close_exit(
                    seed["settlement_id"],
                    expected_version=seed["settlement_expected_version"],
                    contract_expected_version=seed["expected_version"],
                    idempotency_key=replay_key,
                )
                return "ok"
            except AppError as exc:
                session.rollback()
                return exc.code

    try:
        with Session() as session:
            unit = session.get(Unit, seed["unit_id"])
            settlement = session.get(LeaseExitSettlement, seed["settlement_id"])
            assert unit is not None and settlement is not None
            assert unit.status == "OCCUPIED"
            assert Decimal(str(unit.used_area)) == Decimal("80")
            assert Decimal(str(settlement.net_due_from_party)) == Decimal("0")
            assert Decimal(str(settlement.net_due_to_party)) == Decimal("800")
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert list(pool.map(lambda _: close(), (1, 2))) == ["ok", "ok"]
        with Session() as session:
            contract = session.get(LeaseContract, seed["contract_id"])
            settlement = session.get(LeaseExitSettlement, seed["settlement_id"])
            unit = session.get(Unit, seed["unit_id"])
            versions = session.scalar(
                select(func.count(LeaseContractVersion.id)).where(
                    LeaseContractVersion.contract_id == seed["contract_id"]
                )
            )
            assert contract is not None and settlement is not None and unit is not None
            assert contract.status == "TERMINATED"
            assert contract.current_version_no == 2
            assert settlement.status == "CLOSED"
            assert int(versions or 0) == 2
            assert unit.status == "VACANT"
            assert Decimal(str(unit.used_area)) == Decimal("0")
    finally:
        engine.dispose()


def test_pg_exit_close_failure_preserves_shortfall_and_occupancy(monkeypatch) -> None:
    engine, Session = _factory()
    seed = _prepare_approved_exit(
        Session,
        _prepare_pending_active(Session, _seed_v2_draft(Session)),
        deduction_amount="1200",
    )
    try:
        with Session() as session:
            svc = ContractLifecycleService(session, _ctx(seed["tenant_id"]))

            def fail_audit(**_kwargs) -> None:
                raise RuntimeError("synthetic exit close audit failure")

            monkeypatch.setattr(svc.audit, "record", fail_audit)
            with pytest.raises(RuntimeError, match="synthetic exit close audit failure"):
                svc.close_exit(
                    seed["settlement_id"],
                    expected_version=seed["settlement_expected_version"],
                    contract_expected_version=seed["expected_version"],
                    idempotency_key=f"pg-exit-rollback-{uuid4().hex}",
                )
            session.rollback()
        with Session() as session:
            contract = session.get(LeaseContract, seed["contract_id"])
            settlement = session.get(LeaseExitSettlement, seed["settlement_id"])
            unit = session.get(Unit, seed["unit_id"])
            versions = session.scalar(
                select(func.count(LeaseContractVersion.id)).where(
                    LeaseContractVersion.contract_id == seed["contract_id"]
                )
            )
            expiring_todo = session.scalar(
                select(func.count(WorkItem.id)).where(
                    WorkItem.source_type == "LEASE",
                    WorkItem.source_id == str(seed["contract_id"]),
                    WorkItem.item_type == "CONTRACT_EXPIRING",
                    WorkItem.status == "OPEN",
                )
            )
            audit_rows = session.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.resource_type == "LEASE_EXIT_SETTLEMENT",
                    AuditLog.resource_id == str(seed["settlement_id"]),
                    AuditLog.action == "close_exit",
                )
            )
            assert contract is not None and settlement is not None and unit is not None
            assert contract.status == "EXIT_PENDING"
            assert contract.current_version_no == 1
            assert contract.lock_version == seed["expected_version"]
            assert settlement.status == "APPROVED"
            assert settlement.lock_version == seed["settlement_expected_version"]
            assert settlement.financial_clearance_status == "CONFIRMED"
            assert Decimal(str(settlement.net_due_from_party)) == Decimal("200")
            assert Decimal(str(settlement.net_due_to_party)) == Decimal("0")
            assert unit.status == "OCCUPIED"
            assert Decimal(str(unit.used_area)) == Decimal("80")
            assert int(versions or 0) == 1
            assert int(expiring_todo or 0) == 1
            assert int(audit_rows or 0) == 0
    finally:
        engine.dispose()

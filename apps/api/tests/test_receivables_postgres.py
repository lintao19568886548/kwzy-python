"""PostgreSQL 16 schema and concurrency acceptance for receivables."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.infrastructure.database.models.billing import Bill, BillLine
from app.infrastructure.database.models.collection import PaymentAllocation
from app.infrastructure.database.models.collection_case import CollectionCase
from app.infrastructure.database.models.lease import LeaseContract, LeasePerformanceSchedule
from app.infrastructure.database.models.park_property import Park
from app.infrastructure.database.models.party import Party
from app.infrastructure.database.models.receivables import (
    CollectionRecord,
    ReceiptTransaction,
)
from app.modules.billing.application.schedule_billing_service import ScheduleBillingService
from app.modules.collection.application.payment_service import PaymentService
from app.modules.collection.application.receivables_service import ReceivablesService
from app.modules.identity.application.bootstrap import ensure_default_tenant
from app.shared.tenant_context import ParkScopeMode, TenantContext

pytestmark = pytest.mark.pg


def _url() -> str:
    value = os.environ.get("TEST_DATABASE_URL") or os.environ.get("POSTGRES_TEST_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL / POSTGRES_TEST_URL not set")
    if "sqlite" in value.lower() or not value.startswith("postgresql"):
        pytest.fail("receivables concurrency acceptance requires PostgreSQL")
    if "127.0.0.1" not in value and "localhost" not in value:
        pytest.fail("receivables tests must use a localhost database")
    if "kwzy_party_test" not in value:
        pytest.fail("receivables tests require the disposable kwzy_party_test database")
    return value


def _factory():
    engine = create_engine(_url(), pool_pre_ping=True, pool_size=10, max_overflow=10)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _ctx(tenant_id: int) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        user_id=1,
        username="admin",
        permissions=["*"],
        park_ids=[],
        park_scope_mode=ParkScopeMode.ALL,
    )


def _seed(*, with_schedule: bool = False, total: str = "1000.00") -> dict[str, int]:
    _, Session = _factory()
    suffix = uuid4().hex[:10]
    with Session() as session:
        tenant = ensure_default_tenant(session)
        session.flush()
        park = Park(tenant_id=tenant.id, name=f"应收PG园-{suffix}", status="ACTIVE")
        session.add(park)
        session.flush()
        party = Party(
            tenant_id=tenant.id,
            party_type="ORGANIZATION",
            name=f"应收PG主体-{suffix}",
            status="ACTIVE",
            risk_status="NORMAL",
        )
        session.add(party)
        session.flush()
        bill = Bill(
            tenant_id=tenant.id,
            park_id=park.id,
            party_id=party.id,
            bill_no=f"B-PG-{suffix}",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            due_date=date(2026, 1, 1),
            status="ISSUED",
            total_amount=Decimal(total),
            paid_amount=Decimal(0),
            currency="CNY",
            source="MANUAL",
            issued_at=datetime(2026, 1, 1, 9, 0),
            created_by=1,
        )
        session.add(bill)
        session.flush()
        session.add(
            BillLine(
                tenant_id=tenant.id,
                bill_id=bill.id,
                fee_code="RENT",
                description="PG receivables acceptance",
                quantity=Decimal(1),
                unit_price=Decimal(total),
                amount=Decimal(total),
                sort_order=0,
            )
        )
        contract_id = schedule_id = 0
        if with_schedule:
            contract = LeaseContract(
                tenant_id=tenant.id,
                park_id=park.id,
                party_id=party.id,
                contract_no=f"LC-PG-{suffix}",
                status="ACTIVE",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                current_version_no=1,
                lock_version=1,
                deposit_amount=Decimal(0),
                created_by=1,
            )
            session.add(contract)
            session.flush()
            schedule = LeasePerformanceSchedule(
                tenant_id=tenant.id,
                contract_id=contract.id,
                contract_version_no=1,
                charge_code="PROPERTY",
                period_start=date(2026, 2, 1),
                period_end=date(2026, 2, 28),
                due_date=date(2026, 2, 5),
                currency="CNY",
                area=Decimal(1),
                unit_price=Decimal(320),
                net_amount=Decimal(320),
                tax_amount=Decimal(0),
                gross_amount=Decimal(320),
                deterministic_key=f"schedule-{suffix}",
                status="PLANNED",
            )
            session.add(schedule)
            session.flush()
            contract_id = int(contract.id)
            schedule_id = int(schedule.id)
        session.commit()
        return {
            "tenant_id": int(tenant.id),
            "park_id": int(park.id),
            "party_id": int(party.id),
            "bill_id": int(bill.id),
            "contract_id": contract_id,
            "schedule_id": schedule_id,
        }


def test_pg_receivables_schema_constraints_indexes_and_boolean_type() -> None:
    engine, _ = _factory()
    with engine.connect() as connection:
        version = connection.scalar(text("SHOW server_version"))
        assert str(version).split(".")[0] == "16"
        tables = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename IN "
                    "('receipt_transactions','receipt_match_candidates','collection_records',"
                    "'dunning_runs','receivable_adjustments')"
                )
            )
        }
        assert tables == {
            "receipt_transactions",
            "receipt_match_candidates",
            "collection_records",
            "dunning_runs",
            "receivable_adjustments",
        }
        constraints = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT conname FROM pg_constraint WHERE conname IN "
                    "('uk_receipt_source','fk_receipt_candidate_tenant_bill',"
                    "'fk_collection_record_tenant_case','ck_bills_receivable_treatments',"
                    "'uk_collection_case_active_bill_key','fk_bills_tenant_park',"
                    "'fk_bills_tenant_party','fk_bill_lines_tenant_bill',"
                    "'fk_receipts_tenant_park','fk_receipts_tenant_party',"
                    "'fk_receipts_tenant_payment','fk_payments_tenant_park',"
                    "'fk_payments_tenant_party','fk_payments_tenant_source_receipt',"
                    "'fk_payment_allocations_tenant_payment',"
                    "'fk_payment_allocations_tenant_bill',"
                    "'fk_collection_cases_tenant_park',"
                    "'fk_collection_cases_tenant_party',"
                    "'fk_collection_cases_tenant_bill',"
                    "'fk_dunning_runs_tenant_park',"
                    "'fk_receivable_adjustments_tenant_park')"
                )
            )
        }
        assert len(constraints) == 21
        indexes = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT indexname FROM pg_indexes WHERE schemaname='public' AND indexname IN "
                    "('uk_bill_lines_source_schedule','uk_payments_source_receipt',"
                    "'uk_collection_record_source','uk_receivable_adjustment_request_key')"
                )
            )
        }
        assert len(indexes) == 4
        data_type = connection.scalar(
            text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='bills' AND column_name='collection_hold'"
            )
        )
        assert data_type == "boolean"


def test_pg_concurrent_schedule_generation_creates_one_bill() -> None:
    seed = _seed(with_schedule=True)
    _, Session = _factory()
    barrier = threading.Barrier(2)

    def run(key: str) -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                result = ScheduleBillingService(session, _ctx(seed["tenant_id"])).apply(
                    as_of="2026-02-28", park_id=seed["park_id"], idempotency_key=key
                )
                return "ok", str(result["created_count"])
            except AppError as exc:
                session.rollback()
                return "error", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(run, [f"schedule-a-{uuid4().hex}", f"schedule-b-{uuid4().hex}"]))
    assert not any(kind == "error" for kind, _ in outcomes), outcomes
    assert sorted(value for _, value in outcomes) == ["0", "1"]
    with Session() as session:
        schedule = session.get(LeasePerformanceSchedule, seed["schedule_id"])
        assert schedule is not None and schedule.bill_id is not None
        assert (
            session.scalar(
                select(func.count())
                .select_from(Bill)
                .where(Bill.contract_id == seed["contract_id"], Bill.source == "LEASE_SCHEDULE")
            )
            == 1
        )


def test_pg_concurrent_receipt_source_is_unique_and_masked() -> None:
    seed = _seed()
    _, Session = _factory()
    source_ref = f"PG-RECEIPT-{uuid4().hex}"
    barrier = threading.Barrier(2)

    def ingest() -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                result = ReceivablesService(session, _ctx(seed["tenant_id"])).ingest_receipt(
                    {
                        "park_id": seed["park_id"],
                        "party_id": seed["party_id"],
                        "amount": "100",
                        "currency": "CNY",
                        "received_at": "2026-03-01T10:00:00",
                        "channel": "BANK_IMPORT",
                        "source_provider": "PG_TEST",
                        "source_ref": source_ref,
                        "payer_account": "6222021234567890",
                    }
                )
                return "ok", str(result["id"])
            except AppError as exc:
                session.rollback()
                return "error", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: ingest(), range(2)))
    assert sum(kind == "ok" for kind, _ in outcomes) == 1, outcomes
    assert [value for kind, value in outcomes if kind == "error"] == ["RECEIPT_SOURCE_CONFLICT"]
    with Session() as session:
        rows = session.scalars(
            select(ReceiptTransaction).where(ReceiptTransaction.source_ref == source_ref)
        ).all()
        assert len(rows) == 1
        assert rows[0].payer_account_masked == "****7890"


def test_pg_concurrent_later_allocation_cannot_overspend_payment() -> None:
    seed = _seed(total="100.00")
    _, Session = _factory()
    with Session() as session:
        payment = PaymentService(session, _ctx(seed["tenant_id"])).create_payment(
            {
                "park_id": seed["park_id"],
                "party_id": seed["party_id"],
                "amount": "100",
                "paid_at": "2026-03-01T10:00:00",
                "allocations": [],
            }
        )
        payment_id = int(payment["id"])
    barrier = threading.Barrier(2)

    def allocate(key: str) -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                PaymentService(session, _ctx(seed["tenant_id"])).allocate_payment(
                    payment_id,
                    [{"bill_id": seed["bill_id"], "amount": "80"}],
                    idempotency_key=key,
                )
                return "ok", None
            except AppError as exc:
                session.rollback()
                return "error", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(allocate, [f"alloc-a-{uuid4().hex}", f"alloc-b-{uuid4().hex}"]))
    assert sum(kind == "ok" for kind, _ in outcomes) == 1, outcomes
    assert [value for kind, value in outcomes if kind == "error"] == ["ALLOCATION_EXCEEDS_PAYMENT"]
    with Session() as session:
        assert session.scalar(
            select(func.sum(PaymentAllocation.amount)).where(
                PaymentAllocation.payment_id == payment_id,
                PaymentAllocation.reversed_at.is_(None),
            )
        ) == Decimal("80.00")
        assert Decimal(str(session.get(Bill, seed["bill_id"]).paid_amount)) == Decimal("80.00")


def test_pg_concurrent_dunning_keeps_one_active_case_and_record() -> None:
    seed = _seed(total="200.00")
    _, Session = _factory()
    barrier = threading.Barrier(2)

    def run(key: str) -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                ReceivablesService(session, _ctx(seed["tenant_id"])).dunning_apply(
                    as_of="2026-03-05", park_id=seed["park_id"], idempotency_key=key
                )
                return "ok", None
            except AppError as exc:
                session.rollback()
                return "error", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(run, [f"dun-a-{uuid4().hex}", f"dun-b-{uuid4().hex}"]))
    assert sum(kind == "ok" for kind, _ in outcomes) == 1, outcomes
    assert [value for kind, value in outcomes if kind == "error"] == ["DUNNING_RUN_CONFLICT"]
    with Session() as session:
        cases = session.scalars(
            select(CollectionCase).where(
                CollectionCase.tenant_id == seed["tenant_id"],
                CollectionCase.bill_id == seed["bill_id"],
                CollectionCase.status.in_(["OPEN", "PAUSED"]),
            )
        ).all()
        assert len(cases) == 1
        assert (
            session.scalar(
                select(func.count())
                .select_from(CollectionRecord)
                .where(CollectionRecord.case_id == cases[0].id)
            )
            == 1
        )

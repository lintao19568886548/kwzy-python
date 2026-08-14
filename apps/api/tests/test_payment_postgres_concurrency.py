"""PostgreSQL 16 concurrent payment allocate / reverse / numbering tests.

Requires TEST_DATABASE_URL or POSTGRES_TEST_URL (localhost kwzy_party_test).
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.billing import Bill, BillLine
from app.infrastructure.database.models.collection import Payment, PaymentAllocation
from app.infrastructure.database.models.platform import IdempotencyKey
from app.infrastructure.platform.number_sequence import next_number
from app.modules.collection.application.payment_service import PaymentService
from app.modules.identity.application.bootstrap import ensure_default_tenant
from app.shared.tenant_context import ParkScopeMode, TenantContext

pytestmark = pytest.mark.pg


def _pg_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL") or os.environ.get("POSTGRES_TEST_URL")


def _require_pg_url() -> str:
    url = _pg_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL / POSTGRES_TEST_URL not set")
    if "sqlite" in url.lower() or not url.startswith("postgresql"):
        pytest.fail("requires postgresql test URL")
    if "127.0.0.1" not in url and "localhost" not in url:
        pytest.fail("must bind localhost")
    if "kwzy_party_test" not in url:
        pytest.fail("database name must include kwzy_party_test")
    return url


def _session_factory(url: str):
    engine = create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=5)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _ctx(tenant_id: int = 1) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        user_id=1,
        username="admin",
        permissions=["*"],
        park_ids=[],
        park_scope_mode=ParkScopeMode.ALL,
    )


def _ensure_tenant(session) -> int:
    tenant = ensure_default_tenant(session)
    session.commit()
    return int(tenant.id)


def _seed_bill(
    Session,
    *,
    tenant_id: int,
    total: str = "1000.00",
    park_name: str = "并发园",
) -> dict:
    from app.infrastructure.database.models.park_property import Park
    from app.infrastructure.database.models.party import Party

    with Session() as s:
        park = Park(tenant_id=tenant_id, name=park_name, status="ACTIVE")
        s.add(park)
        s.flush()
        party = Party(
            tenant_id=tenant_id,
            party_type="ORGANIZATION",
            name=f"并发主体-{park_name}",
            status="ACTIVE",
            risk_status="NORMAL",
        )
        s.add(party)
        s.flush()
        bill = Bill(
            tenant_id=tenant_id,
            park_id=park.id,
            party_id=party.id,
            bill_no=f"B-CONC-{park.id}-{utc_now().timestamp()}",
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 31),
            status="ISSUED",
            total_amount=Decimal(total),
            paid_amount=Decimal("0"),
            currency="CNY",
            source="MANUAL",
            issued_at=utc_now(),
            created_by=1,
        )
        s.add(bill)
        s.flush()
        s.add(
            BillLine(
                tenant_id=tenant_id,
                bill_id=bill.id,
                fee_code="RENT",
                description="concurrent",
                quantity=Decimal("1"),
                unit_price=Decimal(total),
                amount=Decimal(total),
                sort_order=0,
            )
        )
        s.commit()
        return {
            "tenant_id": tenant_id,
            "park_id": int(park.id),
            "party_id": int(party.id),
            "bill_id": int(bill.id),
            "total": total,
        }


def test_pg_concurrent_allocate_same_bill() -> None:
    """Two concurrent payments allocate the same bill; only legal results commit."""
    url = _require_pg_url()
    engine, Session = _session_factory(url)
    with Session() as s:
        tid = _ensure_tenant(s)

    seed = _seed_bill(Session, tenant_id=tid, total="1000.00", park_name="并发核销园")
    barrier = threading.Barrier(2)
    results: list[tuple[str, str | None]] = []

    def _pay(tag: str, amount: str) -> tuple[str, str | None]:
        with Session() as s:
            try:
                barrier.wait(timeout=15)
                svc = PaymentService(s, _ctx(tid))
                svc.create_payment(
                    {
                        "park_id": seed["park_id"],
                        "party_id": seed["party_id"],
                        "amount": amount,
                        "method": "TRANSFER",
                        "paid_at": "2026-07-10T10:00:00",
                        "payment_no": f"P-CONC-{tag}-{seed['bill_id']}",
                        "allocations": [{"bill_id": seed["bill_id"], "amount": amount}],
                    }
                )
                return ("ok", None)
            except AppError as exc:
                s.rollback()
                return ("err", exc.code)
            except Exception as exc:  # noqa: BLE001
                s.rollback()
                return ("exc", type(exc).__name__)

    # Both try to take 700 of 1000 — second must fail with ALLOCATION_EXCEEDS_BILL or similar
    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [
            pool.submit(_pay, "A", "700"),
            pool.submit(_pay, "B", "700"),
        ]
        for f in as_completed(futs):
            results.append(f.result())

    oks = [r for r in results if r[0] == "ok"]
    errs = [r for r in results if r[0] == "err"]
    excs = [r for r in results if r[0] == "exc"]
    assert not excs, f"unexpected exceptions: {excs}"
    assert len(oks) == 1, results
    assert len(errs) == 1, results
    assert errs[0][1] in {
        "ALLOCATION_EXCEEDS_BILL",
        "PAYMENT_NO_CONFLICT",
        "NUMBER_SEQUENCE_CONFLICT",
    }

    with Session() as s:
        bill = s.get(Bill, seed["bill_id"])
        assert bill is not None
        paid = Decimal(str(bill.paid_amount))
        total = Decimal(str(bill.total_amount))
        assert paid >= 0
        assert paid <= total
        assert paid == Decimal("700.00")
        rows = s.scalars(
            select(PaymentAllocation).where(PaymentAllocation.bill_id == seed["bill_id"])
        ).all()
        alloc_total = sum(Decimal(str(r.amount)) for r in rows)
        assert alloc_total == paid


def test_pg_concurrent_reverse_not_double_deduct() -> None:
    url = _require_pg_url()
    engine, Session = _session_factory(url)
    with Session() as s:
        tid = _ensure_tenant(s)
    seed = _seed_bill(Session, tenant_id=tid, total="500.00", park_name="并发冲正园")

    with Session() as s:
        svc = PaymentService(s, _ctx(tid))
        pay = svc.create_payment(
            {
                "park_id": seed["park_id"],
                "party_id": seed["party_id"],
                "amount": "500",
                "method": "TRANSFER",
                "paid_at": "2026-07-11T10:00:00",
                "payment_no": f"P-REV-{seed['bill_id']}",
                "allocations": [{"bill_id": seed["bill_id"], "amount": "500"}],
            }
        )
        payment_id = int(pay["id"])

    barrier = threading.Barrier(2)
    results: list[tuple[str, str | None]] = []

    def _rev() -> tuple[str, str | None]:
        with Session() as s:
            try:
                barrier.wait(timeout=15)
                PaymentService(s, _ctx(tid)).reverse_payment(payment_id)
                return ("ok", None)
            except AppError as exc:
                s.rollback()
                return ("err", exc.code)
            except Exception as exc:  # noqa: BLE001
                s.rollback()
                return ("exc", type(exc).__name__)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(_rev), pool.submit(_rev)]
        for f in as_completed(futs):
            results.append(f.result())

    oks = [r for r in results if r[0] == "ok"]
    errs = [r for r in results if r[0] == "err"]
    excs = [r for r in results if r[0] == "exc"]
    assert not excs, results
    assert len(oks) == 1, results
    assert len(errs) == 1, results
    assert errs[0][1] in {"PAYMENT_STATUS_INVALID", "PAYMENT_NOT_FOUND"}

    with Session() as s:
        bill = s.get(Bill, seed["bill_id"])
        assert Decimal(str(bill.paid_amount)) == Decimal("0")
        pay = s.get(Payment, payment_id)
        assert pay.status == "REVERSED"


def test_pg_concurrent_number_sequence_unique() -> None:
    url = _require_pg_url()
    engine, Session = _session_factory(url)
    with Session() as s:
        tid = _ensure_tenant(s)
        s.execute(
            text(
                "DELETE FROM number_sequences WHERE tenant_id = :t AND biz_type = :b AND period_key = :p"
            ),
            {"t": tid, "b": "PAYMENT", "p": "CONC-TEST"},
        )
        s.commit()

    barrier = threading.Barrier(8)
    values: list[int] = []
    lock = threading.Lock()

    def _alloc() -> int:
        with Session() as s:
            barrier.wait(timeout=20)
            n = next_number(s, tenant_id=tid, biz_type="PAYMENT", period_key="CONC-TEST")
            s.commit()
            return n

    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(_alloc) for _ in range(8)]
        for f in as_completed(futs):
            with lock:
                values.append(f.result())

    assert len(values) == 8
    assert len(set(values)) == 8
    assert sorted(values) == list(range(1, 9))


def test_pg_integrity_tables_exist() -> None:
    url = _require_pg_url()
    engine, Session = _session_factory(url)
    with engine.connect() as conn:
        tables = {
            r[0]
            for r in conn.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                    "AND tablename IN ('idempotency_keys','number_sequences')"
                )
            )
        }
        assert "idempotency_keys" in tables
        assert "number_sequences" in tables
        uk = {
            r[0]
            for r in conn.execute(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conname IN ('uk_idem_tenant_op_key','uk_number_seq')"
                )
            )
        }
        assert "uk_idem_tenant_op_key" in uk
        assert "uk_number_seq" in uk


def test_pg_concurrent_same_idempotency_key_one_payment() -> None:
    """Two connections, same key+body: one payment / one allocation / one paid delta."""
    url = _require_pg_url()
    engine, Session = _session_factory(url)
    with Session() as s:
        tid = _ensure_tenant(s)
    seed = _seed_bill(Session, tenant_id=tid, total="500.00", park_name="幂等并发园")
    barrier = threading.Barrier(2)
    results: list[tuple[str, str | None, int | None]] = []
    key = f"pg-idem-{seed['bill_id']}"

    def _pay() -> tuple[str, str | None, int | None]:
        with Session() as s:
            try:
                barrier.wait(timeout=15)
                svc = PaymentService(s, _ctx(tid))
                out = svc.create_payment(
                    {
                        "park_id": seed["park_id"],
                        "party_id": seed["party_id"],
                        "amount": "200",
                        "method": "TRANSFER",
                        "paid_at": "2026-07-20T10:00:00",
                        "remark": "same",
                        "allocations": [{"bill_id": seed["bill_id"], "amount": "200"}],
                    },
                    idempotency_key=key,
                )
                return ("ok", None, int(out["id"]))
            except AppError as exc:
                s.rollback()
                return ("err", exc.code, None)
            except Exception as exc:  # noqa: BLE001
                s.rollback()
                return ("exc", type(exc).__name__, None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(_pay), pool.submit(_pay)]
        for f in as_completed(futs):
            results.append(f.result())

    excs = [r for r in results if r[0] == "exc"]
    assert not excs, results
    oks = [r for r in results if r[0] == "ok"]
    errs = [r for r in results if r[0] == "err"]
    # At least one success; the other may be ok (cache) or IN_PROGRESS
    assert len(oks) >= 1, results
    for e in errs:
        assert e[1] in {
            "IDEMPOTENCY_IN_PROGRESS",
            "PAYMENT_NO_CONFLICT",
            "NUMBER_SEQUENCE_CONFLICT",
        }, results
    ok_ids = {r[2] for r in oks if r[2] is not None}
    assert len(ok_ids) <= 1, results

    with Session() as s:
        allocs = s.scalars(
            select(PaymentAllocation).where(PaymentAllocation.bill_id == seed["bill_id"])
        ).all()
        assert len(allocs) == 1, allocs
        bill = s.get(Bill, seed["bill_id"])
        assert Decimal(str(bill.paid_amount)) == Decimal("200.00")
        rows = s.scalars(
            select(IdempotencyKey).where(
                IdempotencyKey.tenant_id == tid,
                IdempotencyKey.operation == "payments.create",
                IdempotencyKey.idem_key == key,
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].status == "COMPLETED"


def test_pg_concurrent_same_key_different_body_conflict() -> None:
    url = _require_pg_url()
    engine, Session = _session_factory(url)
    with Session() as s:
        tid = _ensure_tenant(s)
    seed = _seed_bill(Session, tenant_id=tid, total="800.00", park_name="幂等冲突园")
    barrier = threading.Barrier(2)
    results: list[tuple[str, str | None]] = []
    key = f"pg-idem-diff-{seed['bill_id']}"

    def _pay(amount: str) -> tuple[str, str | None]:
        with Session() as s:
            try:
                barrier.wait(timeout=15)
                PaymentService(s, _ctx(tid)).create_payment(
                    {
                        "park_id": seed["park_id"],
                        "party_id": seed["party_id"],
                        "amount": amount,
                        "method": "TRANSFER",
                        "paid_at": "2026-07-21T10:00:00",
                        "remark": amount,
                        "allocations": [{"bill_id": seed["bill_id"], "amount": amount}],
                    },
                    idempotency_key=key,
                )
                return ("ok", None)
            except AppError as exc:
                s.rollback()
                return ("err", exc.code)
            except Exception as exc:  # noqa: BLE001
                s.rollback()
                return ("exc", type(exc).__name__)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(_pay, "100"), pool.submit(_pay, "150")]
        for f in as_completed(futs):
            results.append(f.result())

    assert not any(r[0] == "exc" for r in results), results
    codes = [r[1] for r in results if r[0] == "err"]
    oks = [r for r in results if r[0] == "ok"]
    # One writer wins; the other must conflict on body hash (or see in-progress then conflict).
    assert len(oks) == 1, results
    assert "IDEMPOTENCY_KEY_CONFLICT" in codes or "IDEMPOTENCY_IN_PROGRESS" in codes, results

    with Session() as s:
        rows = s.scalars(
            select(IdempotencyKey).where(
                IdempotencyKey.tenant_id == tid,
                IdempotencyKey.operation == "payments.create",
                IdempotencyKey.idem_key == key,
            )
        ).all()
        assert len(rows) == 1
        # After both finish, winner must leave COMPLETED — never permanent PROCESSING.
        assert rows[0].status == "COMPLETED", rows[0].status
        allocs = s.scalars(
            select(PaymentAllocation).where(PaymentAllocation.bill_id == seed["bill_id"])
        ).all()
        assert len(allocs) == 1

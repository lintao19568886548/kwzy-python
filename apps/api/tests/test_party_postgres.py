"""PostgreSQL 16 Party 业务矩阵（需 TEST_DATABASE_URL / POSTGRES_TEST_URL）。"""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

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
    engine = create_engine(url, pool_pre_ping=True)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _ensure_tenant(session) -> int:
    from app.modules.identity.application.bootstrap import ensure_default_tenant

    tenant = ensure_default_tenant(session)
    session.commit()
    assert tenant is not None
    return int(tenant.id)


def test_pg_credit_code_unique_conflict() -> None:
    """credit_code 租户内唯一：并发插入同码应至少一失败。"""
    url = _require_pg_url()
    engine, Session = _session_factory(url)
    code = "91310000MA1FL1YPG1"

    with Session() as s:
        tid = _ensure_tenant(s)
        s.execute(text("DELETE FROM party_addresses"))
        s.execute(text("DELETE FROM party_contacts"))
        s.execute(text("DELETE FROM party_risk_events"))
        s.execute(text("DELETE FROM party_park_relations"))
        s.execute(text("DELETE FROM party_roles"))
        s.execute(text("DELETE FROM parties WHERE credit_code = :c"), {"c": code})
        s.commit()

    barrier = threading.Barrier(2)
    results: list[str] = []

    def _insert(name: str) -> str:
        from app.infrastructure.database.models.party import Party

        with Session() as s:
            try:
                barrier.wait(timeout=10)
                s.add(
                    Party(
                        tenant_id=tid,
                        party_type="ORGANIZATION",
                        name=name,
                        credit_code=code,
                        status="ACTIVE",
                        risk_status="NORMAL",
                    )
                )
                s.commit()
                return "ok"
            except Exception:
                s.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(_insert, f"并发公司{i}") for i in (1, 2)]
        for f in as_completed(futs):
            results.append(f.result())

    assert results.count("ok") == 1
    assert results.count("conflict") == 1
    engine.dispose()


def test_pg_address_primary_partial_unique() -> None:
    """同 party+type 双 primary ACTIVE 地址应触发唯一冲突。"""
    url = _require_pg_url()
    engine, Session = _session_factory(url)
    from app.infrastructure.database.base import utc_now
    from app.infrastructure.database.models.party import Party, PartyAddress

    with Session() as s:
        tid = _ensure_tenant(s)
        p = Party(
            tenant_id=tid,
            party_type="ORGANIZATION",
            name="主键址公司",
            status="ACTIVE",
            risk_status="NORMAL",
        )
        s.add(p)
        s.flush()
        s.add(
            PartyAddress(
                tenant_id=tid,
                party_id=p.id,
                address_type="REGISTERED",
                city="测试市",
                street="园区二路1号",
                is_primary=True,
                status="ACTIVE",
                created_at=utc_now(),
            )
        )
        s.commit()
        pid = p.id
        s.add(
            PartyAddress(
                tenant_id=tid,
                party_id=pid,
                address_type="REGISTERED",
                city="测试市",
                street="园区二路2号",
                is_primary=True,
                status="ACTIVE",
                created_at=utc_now(),
            )
        )
        with pytest.raises(IntegrityError):
            s.commit()
        s.rollback()
    engine.dispose()


def test_pg_risk_event_same_transaction_with_audit() -> None:
    """blacklist 成功后 risk_events 与 audit 同事务可见。"""
    url = _require_pg_url()
    engine, Session = _session_factory(url)
    from app.infrastructure.database.models.audit import AuditLog
    from app.infrastructure.database.models.party import Party, PartyRiskEvent
    from app.modules.party.application.party_service import PartyService
    from app.shared.tenant_context import ParkScopeMode, TenantContext

    with Session() as s:
        tid = _ensure_tenant(s)
        p = Party(
            tenant_id=tid,
            party_type="ORGANIZATION",
            name="风险事务公司",
            status="ACTIVE",
            risk_status="NORMAL",
        )
        s.add(p)
        s.commit()
        pid = p.id

        ctx = TenantContext(
            tenant_id=tid,
            user_id=1,
            username="admin",
            permissions=["*"],
            park_scope_mode=ParkScopeMode.ALL,
            request_id="pg-risk-tx-test",
        )
        PartyService(s, ctx).blacklist(pid, "虚构逾期原因")

        events = list(
            s.scalars(
                select(PartyRiskEvent).where(
                    PartyRiskEvent.tenant_id == tid,
                    PartyRiskEvent.party_id == pid,
                )
            ).all()
        )
        assert len(events) >= 1
        assert events[0].event_type == "BLACKLISTED"
        audits = list(
            s.scalars(
                select(AuditLog).where(
                    AuditLog.resource_type == "PARTY",
                    AuditLog.action == "blacklist",
                    AuditLog.resource_id == str(pid),
                )
            ).all()
        )
        assert len(audits) >= 1
    engine.dispose()


def test_pg_person_preseeded_address_not_readable_via_service() -> None:
    """PG 上预置 PERSON 地址后 Application list 仍 403，不返回地址。"""
    url = _require_pg_url()
    engine, Session = _session_factory(url)
    from app.core.errors import AppError
    from app.infrastructure.database.base import utc_now
    from app.infrastructure.database.models.party import Party, PartyAddress
    from app.modules.party.application.party_service import PartyService
    from app.shared.tenant_context import ParkScopeMode, TenantContext

    with Session() as s:
        tid = _ensure_tenant(s)
        p = Party(
            tenant_id=tid,
            party_type="PERSON",
            name="PG测试人员",
            status="ACTIVE",
            risk_status="NORMAL",
        )
        s.add(p)
        s.flush()
        s.add(
            PartyAddress(
                tenant_id=tid,
                party_id=p.id,
                address_type="MAILING",
                city="测试市",
                street="虚构巷100号",
                detail="虚构室888",
                is_primary=True,
                status="ACTIVE",
                created_at=utc_now(),
            )
        )
        s.commit()
        pid = p.id

        ctx = TenantContext(
            tenant_id=tid,
            user_id=1,
            username="admin",
            permissions=["*"],
            park_scope_mode=ParkScopeMode.ALL,
        )
        svc = PartyService(s, ctx)
        with pytest.raises(AppError) as ei:
            svc.list_addresses(pid)
        assert ei.value.code == "PERSON_ADDRESS_FORBIDDEN"
        assert ei.value.status_code == 403
        assert "虚构" not in ei.value.message
    engine.dispose()

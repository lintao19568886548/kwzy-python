"""PostgreSQL 16 isolation and concurrency acceptance for enterprise Party."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.infrastructure.database.models.identity import Tenant
from app.infrastructure.database.models.party_enterprise import (
    PartyEnterpriseProfile,
    PartyEnterpriseRelationship,
    PartyEnterpriseRiskResolution,
    PartyEnterpriseTag,
)
from app.modules.identity.application.bootstrap import ensure_default_tenant
from app.modules.party.application.enterprise_service import PartyEnterpriseService
from app.modules.party.application.party_service import PartyService
from app.shared.tenant_context import ParkScopeMode, TenantContext

pytestmark = pytest.mark.pg


def _require_pg_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("POSTGRES_TEST_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL / POSTGRES_TEST_URL not set")
    if not url.startswith("postgresql") or ("127.0.0.1" not in url and "localhost" not in url):
        pytest.fail("enterprise Party tests require localhost PostgreSQL")
    if "kwzy_party_test" not in url:
        pytest.fail("database name must include kwzy_party_test")
    return url


def _factory():
    engine = create_engine(_require_pg_url(), pool_pre_ping=True, pool_size=8, max_overflow=4)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _ctx(tenant_id: int) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        user_id=1,
        username="party-enterprise-pg",
        permissions=["*"],
        park_ids=[],
        park_scope_mode=ParkScopeMode.ALL,
    )


def _seed(Session) -> dict[str, int]:
    suffix = uuid4().hex[:10].upper()
    with Session() as session:
        tenant_id = int(ensure_default_tenant(session).id)
        session.commit()
        party_service = PartyService(session, _ctx(tenant_id))
        parent = party_service.create_party(
            {
                "name": f"企业画像并发甲-{suffix}",
                "party_type": "ORGANIZATION",
                "credit_code": f"913100{suffix}A1",
            }
        )
        child = party_service.create_party(
            {"name": f"企业画像并发乙-{suffix}", "party_type": "ORGANIZATION"}
        )
        profile = PartyEnterpriseService(session, _ctx(tenant_id)).save_profile(
            int(parent["id"]),
            {"expected_lock_version": 0, "short_name": f"PG-{suffix}"},
        )
        return {
            "tenant_id": tenant_id,
            "parent_id": int(parent["id"]),
            "child_id": int(child["id"]),
            "profile_version": int(profile["lock_version"]),
        }


def test_pg_profile_optimistic_update_has_one_winner() -> None:
    engine, Session = _factory()
    seed = _seed(Session)
    barrier = threading.Barrier(2)

    def update(label: str) -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                PartyEnterpriseService(session, _ctx(seed["tenant_id"])).save_profile(
                    seed["parent_id"],
                    {
                        "expected_lock_version": seed["profile_version"],
                        "short_name": label,
                    },
                )
                return "ok", None
            except AppError as exc:
                session.rollback()
                return "err", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, ["并发版本甲", "并发版本乙"]))
    assert sorted(state for state, _ in results) == ["err", "ok"], results
    assert [code for state, code in results if state == "err"] == ["ENTERPRISE_PROFILE_CONFLICT"]
    with Session() as session:
        row = session.scalar(
            select(PartyEnterpriseProfile).where(
                PartyEnterpriseProfile.tenant_id == seed["tenant_id"],
                PartyEnterpriseProfile.party_id == seed["parent_id"],
            )
        )
        assert row is not None and row.lock_version == seed["profile_version"] + 1
    engine.dispose()


def test_pg_relationship_graph_lock_prevents_concurrent_parent_cycle() -> None:
    engine, Session = _factory()
    seed = _seed(Session)
    barrier = threading.Barrier(2)

    def link(pair: tuple[int, int]) -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                PartyEnterpriseService(session, _ctx(seed["tenant_id"])).create_relationship(
                    pair[0],
                    {"target_party_id": pair[1], "relationship_type": "PARENT_OF"},
                )
                return "ok", None
            except AppError as exc:
                session.rollback()
                return "err", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                link,
                [
                    (seed["parent_id"], seed["child_id"]),
                    (seed["child_id"], seed["parent_id"]),
                ],
            )
        )
    assert sorted(state for state, _ in results) == ["err", "ok"], results
    assert [code for state, code in results if state == "err"] == ["ENTERPRISE_RELATIONSHIP_CYCLE"]
    with Session() as session:
        count = session.scalar(
            select(func.count())
            .select_from(PartyEnterpriseRelationship)
            .where(
                PartyEnterpriseRelationship.tenant_id == seed["tenant_id"],
                PartyEnterpriseRelationship.status == "ACTIVE",
                PartyEnterpriseRelationship.relationship_type == "PARENT_OF",
                PartyEnterpriseRelationship.source_party_id.in_(
                    [seed["parent_id"], seed["child_id"]]
                ),
                PartyEnterpriseRelationship.target_party_id.in_(
                    [seed["parent_id"], seed["child_id"]]
                ),
            )
        )
        assert int(count or 0) == 1
    engine.dispose()


def test_pg_tag_uniqueness_and_risk_resolution_are_idempotent_under_concurrency() -> None:
    engine, Session = _factory()
    seed = _seed(Session)
    tag_barrier = threading.Barrier(2)

    def add_tag() -> tuple[str, int | str]:
        with Session() as session:
            try:
                tag_barrier.wait(timeout=15)
                result = PartyEnterpriseService(session, _ctx(seed["tenant_id"])).create_tag(
                    seed["parent_id"],
                    {"name": "并发资质标签", "tag_type": "QUALIFICATION"},
                )
                return "ok", int(result["id"])
            except AppError as exc:
                session.rollback()
                return "err", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        tag_results = list(pool.map(lambda _: add_tag(), range(2)))
    assert sum(state == "ok" for state, _ in tag_results) == 1, tag_results
    assert [value for state, value in tag_results if state == "err"] == ["ENTERPRISE_TAG_CONFLICT"]
    with Session() as session:
        assert (
            int(
                session.scalar(
                    select(func.count())
                    .select_from(PartyEnterpriseTag)
                    .where(
                        PartyEnterpriseTag.tenant_id == seed["tenant_id"],
                        PartyEnterpriseTag.party_id == seed["parent_id"],
                        PartyEnterpriseTag.normalized_name == "并发资质标签",
                        PartyEnterpriseTag.status == "ACTIVE",
                    )
                )
                or 0
            )
            == 1
        )
        signal = PartyEnterpriseService(session, _ctx(seed["tenant_id"])).create_risk_signal(
            seed["parent_id"],
            {
                "category": "COMPLIANCE",
                "severity": "HIGH",
                "summary": "PostgreSQL 并发处置测试",
                "source_reference": f"pg-risk-{uuid4().hex}",
            },
        )
        signal_id = int(signal["id"])

    resolution_barrier = threading.Barrier(2)

    def resolve() -> tuple[str, int]:
        with Session() as session:
            resolution_barrier.wait(timeout=15)
            result = PartyEnterpriseService(session, _ctx(seed["tenant_id"])).resolve_risk_signal(
                seed["parent_id"],
                signal_id,
                resolution_type="MITIGATED",
                reason="并发人工缓释",
            )
            resolution = result["resolution"]
            assert isinstance(resolution, dict)
            return "ok", int(resolution["id"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        resolution_results = list(pool.map(lambda _: resolve(), range(2)))
    assert resolution_results[0][1] == resolution_results[1][1]
    with Session() as session:
        assert (
            int(
                session.scalar(
                    select(func.count())
                    .select_from(PartyEnterpriseRiskResolution)
                    .where(
                        PartyEnterpriseRiskResolution.tenant_id == seed["tenant_id"],
                        PartyEnterpriseRiskResolution.signal_id == signal_id,
                    )
                )
                or 0
            )
            == 1
        )
    engine.dispose()


def test_pg_composite_foreign_keys_reject_cross_tenant_enterprise_rows() -> None:
    engine, Session = _factory()
    seed = _seed(Session)
    with Session() as session:
        other = Tenant(code=f"enterprise-isolation-{uuid4().hex[:10]}", name="企业隔离租户")
        session.add(other)
        session.commit()
        other_tenant_id = int(other.id)
    with Session() as session:
        session.add(
            PartyEnterpriseProfile(
                tenant_id=other_tenant_id,
                party_id=seed["parent_id"],
                short_name="非法跨租户引用",
                provider_status="NOT_CONNECTED",
                lock_version=1,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
    engine.dispose()

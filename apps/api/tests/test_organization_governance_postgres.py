"""PostgreSQL 16 schema and concurrency gates for organization governance."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.core.security import hash_password
from app.infrastructure.database.models.identity import User
from app.infrastructure.database.models.organization_governance import (
    OrganizationGroup,
    OrganizationRegion,
    Position,
    RegionParkAssignment,
    UserPositionAssignment,
)
from app.infrastructure.database.models.park_property import Park
from app.modules.identity.application.bootstrap import ensure_default_tenant
from app.modules.identity.application.organization_governance_service import (
    OrganizationGovernanceService,
)
from app.shared.tenant_context import ParkScopeMode, TenantContext

pytestmark = pytest.mark.pg


def _require_pg_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("POSTGRES_TEST_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL / POSTGRES_TEST_URL not set")
    if not url.startswith("postgresql") or not any(
        host in url for host in ("127.0.0.1", "localhost")
    ):
        pytest.fail("organization governance tests require localhost PostgreSQL")
    if "kwzy_party_test" not in url:
        pytest.fail("database name must include kwzy_party_test")
    return url


def _factory():
    engine = create_engine(
        _require_pg_url(), pool_pre_ping=True, pool_size=6, max_overflow=2
    )
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _context(tenant_id: int, user_id: int, park_id: int) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        username=f"org-pg-{user_id}",
        permissions=[
            "identity.org_governance.read",
            "identity.org_governance.write",
        ],
        park_ids=[park_id],
        park_scope_mode=ParkScopeMode.LIST,
    )


def _seed(Session) -> dict[str, int]:
    suffix = uuid4().hex[:10].upper()
    with Session() as session:
        tenant = ensure_default_tenant(session)
        user = User(
            tenant_id=tenant.id,
            username=f"org-pg-{suffix.lower()}",
            password_hash=hash_password("Strong#12345"),
            real_name="组织并发用户",
        )
        park = Park(tenant_id=tenant.id, name=f"组织并发园-{suffix}")
        group = OrganizationGroup(
            tenant_id=tenant.id, code=f"G-{suffix}", name="组织并发集团"
        )
        session.add_all([user, park, group])
        session.flush()
        east = OrganizationRegion(
            tenant_id=tenant.id,
            group_id=group.id,
            code=f"E-{suffix}",
            name="东区",
        )
        west = OrganizationRegion(
            tenant_id=tenant.id,
            group_id=group.id,
            code=f"W-{suffix}",
            name="西区",
        )
        first_position = Position(
            tenant_id=tenant.id, code=f"P1-{suffix}", name="第一岗位"
        )
        second_position = Position(
            tenant_id=tenant.id, code=f"P2-{suffix}", name="第二岗位"
        )
        session.add_all([east, west, first_position, second_position])
        session.commit()
        return {
            "tenant_id": int(tenant.id),
            "user_id": int(user.id),
            "park_id": int(park.id),
            "east_id": int(east.id),
            "west_id": int(west.id),
            "first_position_id": int(first_position.id),
            "second_position_id": int(second_position.id),
        }


def test_pg_concurrent_region_reassignment_preserves_one_current_row() -> None:
    engine, Session = _factory()
    seed = _seed(Session)
    barrier = threading.Barrier(2)

    def assign(region_id: int) -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                OrganizationGovernanceService(
                    session,
                    _context(seed["tenant_id"], seed["user_id"], seed["park_id"]),
                ).assign_park(
                    {
                        "region_id": region_id,
                        "park_id": seed["park_id"],
                        "reason": "concurrency gate",
                    }
                )
                return "ok", None
            except AppError as exc:
                session.rollback()
                return "err", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(assign, [seed["east_id"], seed["west_id"]]))

    assert all(state == "ok" for state, _ in results), results
    with Session() as session:
        current = session.scalar(
            select(func.count(RegionParkAssignment.id)).where(
                RegionParkAssignment.tenant_id == seed["tenant_id"],
                RegionParkAssignment.park_id == seed["park_id"],
                RegionParkAssignment.effective_to.is_(None),
            )
        )
        historical = session.scalar(
            select(func.count(RegionParkAssignment.id)).where(
                RegionParkAssignment.tenant_id == seed["tenant_id"],
                RegionParkAssignment.park_id == seed["park_id"],
            )
        )
        assert int(current or 0) == 1
        assert int(historical or 0) == 2
    engine.dispose()


def test_pg_concurrent_primary_position_assignment_has_one_winner() -> None:
    engine, Session = _factory()
    seed = _seed(Session)
    barrier = threading.Barrier(2)

    def assign(position_id: int) -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                OrganizationGovernanceService(
                    session,
                    _context(seed["tenant_id"], seed["user_id"], seed["park_id"]),
                ).assign_user(
                    {
                        "user_id": seed["user_id"],
                        "position_id": position_id,
                        "park_id": seed["park_id"],
                        "is_primary": True,
                    }
                )
                return "ok", None
            except AppError as exc:
                session.rollback()
                return "err", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                assign,
                [seed["first_position_id"], seed["second_position_id"]],
            )
        )

    assert sorted(state for state, _ in results) == ["err", "ok"], results
    error_codes = [code for state, code in results if state == "err"]
    assert len(error_codes) == 1
    assert error_codes[0] in {
        "PRIMARY_POSITION_CONFLICT",
        "POSITION_ASSIGNMENT_CONFLICT",
    }
    with Session() as session:
        current_primary = session.scalar(
            select(func.count(UserPositionAssignment.id)).where(
                UserPositionAssignment.tenant_id == seed["tenant_id"],
                UserPositionAssignment.user_id == seed["user_id"],
                UserPositionAssignment.ends_at.is_(None),
                UserPositionAssignment.is_primary.is_(True),
            )
        )
        assert int(current_primary or 0) == 1
    engine.dispose()


def test_pg_migration_schema_matches_required_constraints_and_boolean() -> None:
    engine, _ = _factory()
    inspector = inspect(engine)
    required = {
        "organization_groups",
        "organization_regions",
        "region_park_assignments",
        "positions",
        "user_position_assignments",
        "field_access_policies",
    }
    assert required <= set(inspector.get_table_names())
    assignment_columns = {
        column["name"]: column for column in inspector.get_columns("user_position_assignments")
    }
    assert str(assignment_columns["is_primary"]["type"]).upper() == "BOOLEAN"
    assert assignment_columns["is_primary"]["nullable"] is False
    region_indexes = {
        index["name"]: index for index in inspector.get_indexes("region_park_assignments")
    }
    primary_indexes = {
        index["name"]: index for index in inspector.get_indexes("user_position_assignments")
    }
    assert region_indexes["uk_region_park_current"]["unique"] is True
    assert primary_indexes["uk_user_primary_position_current"]["unique"] is True
    assert "effective_to IS NULL" in str(
        region_indexes["uk_region_park_current"].get("dialect_options")
    )
    engine.dispose()

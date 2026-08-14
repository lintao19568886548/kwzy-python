"""PostgreSQL row-lock and uniqueness acceptance for asset rent control V2."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.infrastructure.database.models.identity import Tenant
from app.infrastructure.database.models.lease import LeaseContract, LeaseContractUnit
from app.infrastructure.database.models.park_property import (
    AssetTemplate,
    AssetTemplateVersion,
    Building,
    Unit,
    UnitLineage,
)
from app.infrastructure.database.models.party import Party
from app.modules.identity.application.bootstrap import ensure_default_tenant
from app.modules.lease.application.lease_service import LeaseService
from app.modules.park_property.application.asset_template_service import AssetTemplateService
from app.modules.park_property.application.park_service import ParkService
from app.modules.park_property.application.spatial_service import SpatialService
from app.modules.park_property.application.unit_service import UnitService
from app.shared.tenant_context import ParkScopeMode, TenantContext

pytestmark = pytest.mark.pg


def _require_pg_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("POSTGRES_TEST_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL / POSTGRES_TEST_URL not set")
    if not url.startswith("postgresql") or ("127.0.0.1" not in url and "localhost" not in url):
        pytest.fail("asset concurrency tests require localhost PostgreSQL")
    if "kwzy_party_test" not in url:
        pytest.fail("database name must include kwzy_party_test")
    return url


def _factory(url: str):
    engine = create_engine(url, pool_pre_ping=True, pool_size=8, max_overflow=4)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _ctx(tenant_id: int) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        user_id=1,
        username="asset-pg-admin",
        permissions=["*"],
        park_ids=[],
        park_scope_mode=ParkScopeMode.ALL,
    )


def _tenant(Session) -> int:
    with Session() as session:
        tenant = ensure_default_tenant(session)
        session.commit()
        return int(tenant.id)


def _seed_unit(Session, tenant_id: int, *, area: str = "100") -> dict[str, int]:
    suffix = uuid4().hex[:10].upper()
    with Session() as session:
        ctx = _ctx(tenant_id)
        park = ParkService(session, ctx).create_park({"name": f"资产并发园-{suffix}"})
        space = SpatialService(session, ctx).create(
            {
                "park_id": park["id"],
                "code": f"B-{suffix}",
                "name": f"并发楼栋-{suffix}",
                "node_type": "BUILDING",
            }
        )
        unit = UnitService(session, ctx).create_unit(
            {
                "park_id": park["id"],
                "building_id": space["id"],
                "code": f"U-{suffix}",
                "name": f"并发单元-{suffix}",
                "rentable_area": area,
            }
        )
        return {"park_id": park["id"], "space_id": space["id"], "unit_id": unit["id"]}


def test_pg_root_space_code_concurrency_is_database_enforced() -> None:
    engine, Session = _factory(_require_pg_url())
    tenant_id = _tenant(Session)
    with Session() as session:
        park = ParkService(session, _ctx(tenant_id)).create_park(
            {"name": f"根空间唯一园-{uuid4().hex[:8]}"}
        )
    barrier = threading.Barrier(2)

    def create_root(tag: str) -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                SpatialService(session, _ctx(tenant_id)).create(
                    {
                        "park_id": park["id"],
                        "code": "ROOT-DUP",
                        "name": f"并发根节点-{tag}",
                        "node_type": "BUILDING",
                    }
                )
                return ("ok", None)
            except AppError as exc:
                session.rollback()
                return ("err", exc.code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create_root, ["A", "B"]))
    assert sorted(state for state, _ in results) == ["err", "ok"]
    assert [code for state, code in results if state == "err"] == ["SPACE_CODE_CONFLICT"]
    engine.dispose()


def test_pg_concurrent_first_request_bootstraps_one_builtin_template_set() -> None:
    engine, Session = _factory(_require_pg_url())
    suffix = uuid4().hex[:10]
    with Session() as session:
        tenant = Tenant(code=f"asset-bootstrap-{suffix}", name="资产模板并发租户")
        session.add(tenant)
        session.commit()
        tenant_id = int(tenant.id)
    barrier = threading.Barrier(2)

    def bootstrap() -> tuple[str, int]:
        with Session() as session:
            barrier.wait(timeout=15)
            rows = AssetTemplateService(session, _ctx(tenant_id)).list_templates()
            return ("ok", len(rows))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: bootstrap(), range(2)))
    assert results == [("ok", 7), ("ok", 7)]
    with Session() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(AssetTemplate)
                .where(AssetTemplate.tenant_id == tenant_id)
            )
            == 7
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(AssetTemplateVersion)
                .where(AssetTemplateVersion.tenant_id == tenant_id)
            )
            == 7
        )
    engine.dispose()


def test_pg_database_rejects_cross_tenant_asset_references() -> None:
    engine, Session = _factory(_require_pg_url())
    first_tenant_id = _tenant(Session)
    suffix = uuid4().hex[:10]
    with Session() as session:
        second_tenant = Tenant(code=f"asset-isolation-{suffix}", name="资产隔离租户")
        session.add(second_tenant)
        session.commit()
        second_tenant_id = int(second_tenant.id)

    with Session() as session:
        AssetTemplateService(session, _ctx(first_tenant_id)).list_templates()
    with Session() as session:
        AssetTemplateService(session, _ctx(second_tenant_id)).list_templates()
    with Session() as session:
        first_office = session.scalar(
            select(AssetTemplateVersion)
            .join(AssetTemplate, AssetTemplate.id == AssetTemplateVersion.template_id)
            .where(
                AssetTemplate.tenant_id == first_tenant_id,
                AssetTemplate.code == "OFFICE",
                AssetTemplateVersion.status == "PUBLISHED",
            )
        )
        assert first_office is not None
        cross_tenant_version = AssetTemplateVersion(
            tenant_id=second_tenant_id,
            template_id=first_office.template_id,
            version=999,
            status="PUBLISHED",
            field_schema_json=[],
            defaults_json={},
            schema_checksum="0" * 64,
        )
        session.add(cross_tenant_version)
        with pytest.raises(IntegrityError):
            session.commit()

    second_seed = _seed_unit(Session, second_tenant_id)
    with Session() as session:
        first_office_id = session.scalar(
            select(AssetTemplateVersion.id)
            .join(AssetTemplate, AssetTemplate.id == AssetTemplateVersion.template_id)
            .where(
                AssetTemplate.tenant_id == first_tenant_id,
                AssetTemplate.code == "OFFICE",
                AssetTemplateVersion.status == "PUBLISHED",
            )
        )
        second_unit = session.get(Unit, second_seed["unit_id"])
        assert first_office_id is not None and second_unit is not None
        second_unit.asset_template_version_id = int(first_office_id)
        with pytest.raises(IntegrityError):
            session.commit()
    engine.dispose()


def test_pg_template_publish_and_geometry_updates_have_one_winner() -> None:
    engine, Session = _factory(_require_pg_url())
    tenant_id = _tenant(Session)
    suffix = uuid4().hex[:10].upper()
    with Session() as session:
        template = AssetTemplateService(session, _ctx(tenant_id)).create(
            {
                "code": f"PG-OFFICE-{suffix}",
                "name": "并发办公模板",
                "category": "OFFICE",
                "fields": [],
            }
        )
    barrier = threading.Barrier(2)

    def publish() -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                AssetTemplateService(session, _ctx(tenant_id)).publish(
                    int(template["id"]), int(template["lock_version"])
                )
                return ("ok", None)
            except AppError as exc:
                session.rollback()
                return ("err", exc.code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        publish_results = list(pool.map(lambda _: publish(), range(2)))
    assert sum(state == "ok" for state, _ in publish_results) == 1
    assert [code for state, code in publish_results if state == "err"] == [
        "ASSET_TEMPLATE_VERSION_CONFLICT"
    ]

    with Session() as session:
        ctx = _ctx(tenant_id)
        park = ParkService(session, ctx).create_park({"name": f"几何并发园-{suffix}"})
        space = SpatialService(session, ctx).create(
            {
                "park_id": park["id"],
                "code": f"GEO-{suffix}",
                "name": "几何并发楼",
                "node_type": "BUILDING",
                "geometry": {"type": "Point", "coordinates": [1, 1]},
                "coordinate_reference": "LOCAL",
            }
        )
    geometry_barrier = threading.Barrier(2)

    def update_geometry(x: int) -> tuple[str, str | None]:
        with Session() as session:
            try:
                geometry_barrier.wait(timeout=15)
                SpatialService(session, _ctx(tenant_id)).update(
                    int(space["id"]),
                    {
                        "geometry": {"type": "Point", "coordinates": [x, x]},
                        "coordinate_reference": "LOCAL",
                        "expected_geometry_version": 1,
                    },
                )
                return ("ok", None)
            except AppError as exc:
                session.rollback()
                return ("err", exc.code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        geometry_results = list(pool.map(update_geometry, [2, 3]))
    assert sum(state == "ok" for state, _ in geometry_results) == 1
    assert [code for state, code in geometry_results if state == "err"] == [
        "SPACE_GEOMETRY_VERSION_CONFLICT"
    ]
    with Session() as session:
        stored = session.get(Building, int(space["id"]))
        assert stored is not None and stored.geometry_version == 2
        assert stored.geometry_json["coordinates"] in ([2.0, 2.0], [3.0, 3.0])
    engine.dispose()


def test_pg_concurrent_split_has_one_winner_and_complete_lineage() -> None:
    engine, Session = _factory(_require_pg_url())
    tenant_id = _tenant(Session)
    seed = _seed_unit(Session, tenant_id)
    barrier = threading.Barrier(2)

    def split(tag: str) -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                UnitService(session, _ctx(tenant_id)).split(
                    {
                        "unit_id": seed["unit_id"],
                        "expected_lock_version": 1,
                        "targets": [
                            {
                                "code": f"{tag}-A-{seed['unit_id']}",
                                "name": f"{tag}A",
                                "rentable_area": 40,
                            },
                            {
                                "code": f"{tag}-B-{seed['unit_id']}",
                                "name": f"{tag}B",
                                "rentable_area": 60,
                            },
                        ],
                    }
                )
                return ("ok", None)
            except AppError as exc:
                session.rollback()
                return ("err", exc.code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(split, tag) for tag in ("LEFT", "RIGHT")]
        results = [future.result() for future in as_completed(futures)]
    assert sum(state == "ok" for state, _ in results) == 1
    assert [code for state, code in results if state == "err"] == ["UNIT_VERSION_CONFLICT"]

    with Session() as session:
        source = session.get(Unit, seed["unit_id"])
        assert source is not None and source.valid_to is not None and source.status == "RETIRED"
        targets = session.scalars(
            select(Unit).where(
                Unit.tenant_id == tenant_id,
                Unit.park_id == seed["park_id"],
                Unit.valid_to.is_(None),
                Unit.is_deleted.is_(False),
            )
        ).all()
        assert len(targets) == 2
        assert sum(Decimal(str(row.rentable_area)) for row in targets) == Decimal("100.00")
        edges = session.scalars(
            select(UnitLineage).where(UnitLineage.source_unit_id == seed["unit_id"])
        ).all()
        assert len(edges) == 2
        assert len({edge.operation_id for edge in edges}) == 1
    engine.dispose()


def test_pg_concurrent_structural_version_has_one_winner() -> None:
    engine, Session = _factory(_require_pg_url())
    tenant_id = _tenant(Session)
    seed = _seed_unit(Session, tenant_id)
    barrier = threading.Barrier(2)

    def version(area: int) -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                UnitService(session, _ctx(tenant_id)).create_version(
                    seed["unit_id"],
                    {"expected_lock_version": 1, "rentable_area": area},
                )
                return ("ok", None)
            except AppError as exc:
                session.rollback()
                return ("err", exc.code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(version, [110, 120]))
    assert sum(state == "ok" for state, _ in results) == 1
    assert [code for state, code in results if state == "err"] == ["UNIT_VERSION_CONFLICT"]
    with Session() as session:
        versions = session.scalars(select(Unit).where(Unit.supersedes_id == seed["unit_id"])).all()
        assert len(versions) == 1 and versions[0].version_no == 2
    engine.dispose()


def test_pg_concurrent_merge_has_one_winner_and_rollback_is_atomic() -> None:
    engine, Session = _factory(_require_pg_url())
    tenant_id = _tenant(Session)
    seed = _seed_unit(Session, tenant_id, area="40")
    suffix = uuid4().hex[:8].upper()
    with Session() as session:
        second = UnitService(session, _ctx(tenant_id)).create_unit(
            {
                "park_id": seed["park_id"],
                "building_id": seed["space_id"],
                "code": f"SECOND-{suffix}",
                "name": "第二来源",
                "rentable_area": 60,
            }
        )
    barrier = threading.Barrier(2)

    def merge(tag: str) -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                UnitService(session, _ctx(tenant_id)).merge(
                    {
                        "sources": [
                            {"unit_id": seed["unit_id"], "expected_lock_version": 1},
                            {"unit_id": second["id"], "expected_lock_version": 1},
                        ],
                        "code": f"MERGED-{tag}-{suffix}",
                        "name": f"合并结果{tag}",
                    }
                )
                return ("ok", None)
            except AppError as exc:
                session.rollback()
                return ("err", exc.code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(merge, ["A", "B"]))
    assert sum(state == "ok" for state, _ in results) == 1
    assert [code for state, code in results if state == "err"] == ["UNIT_VERSION_CONFLICT"]
    with Session() as session:
        current = session.scalars(
            select(Unit).where(
                Unit.park_id == seed["park_id"],
                Unit.valid_to.is_(None),
                Unit.is_deleted.is_(False),
            )
        ).all()
        assert len(current) == 1
        assert Decimal(str(current[0].rentable_area)) == Decimal("100.00")
        assert (
            session.scalar(
                select(func.count())
                .select_from(UnitLineage)
                .where(UnitLineage.target_unit_id == current[0].id)
            )
            == 2
        )

    rollback_seed = _seed_unit(Session, tenant_id)
    with Session() as session:
        existing = UnitService(session, _ctx(tenant_id)).create_unit(
            {
                "park_id": rollback_seed["park_id"],
                "building_id": rollback_seed["space_id"],
                "code": f"ROLLBACK-DUP-{suffix}",
                "name": "冲突目标",
                "rentable_area": 10,
            }
        )
        with pytest.raises(AppError) as error:
            UnitService(session, _ctx(tenant_id)).split(
                {
                    "unit_id": rollback_seed["unit_id"],
                    "expected_lock_version": 1,
                    "targets": [
                        {"code": f"ROLLBACK-OK-{suffix}", "name": "临时目标", "rentable_area": 50},
                        {"code": existing["code"], "name": "重复目标", "rentable_area": 50},
                    ],
                }
            )
        assert error.value.code == "UNIT_CODE_CONFLICT"
    with Session() as session:
        source = session.get(Unit, rollback_seed["unit_id"])
        assert source is not None and source.valid_to is None and source.status == "VACANT"
        assert (
            session.scalar(
                select(func.count()).select_from(Unit).where(Unit.code == f"ROLLBACK-OK-{suffix}")
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(UnitLineage)
                .where(UnitLineage.source_unit_id == rollback_seed["unit_id"])
            )
            == 0
        )
    engine.dispose()


def test_pg_split_and_lease_activation_are_serialized() -> None:
    engine, Session = _factory(_require_pg_url())
    tenant_id = _tenant(Session)
    seed = _seed_unit(Session, tenant_id)
    suffix = uuid4().hex[:10].upper()
    with Session() as session:
        party = Party(
            tenant_id=tenant_id,
            party_type="ORGANIZATION",
            name=f"租控并发客户-{suffix}",
            status="ACTIVE",
            risk_status="NORMAL",
        )
        session.add(party)
        session.flush()
        lease = LeaseContract(
            tenant_id=tenant_id,
            park_id=seed["park_id"],
            party_id=party.id,
            contract_no=f"RC-RACE-{suffix}",
            status="PENDING_ACTIVE",
            start_date=date(2026, 8, 1),
            end_date=date(2027, 7, 31),
            deposit_amount=Decimal("0"),
            created_by=1,
        )
        session.add(lease)
        session.flush()
        session.add(
            LeaseContractUnit(
                tenant_id=tenant_id,
                contract_id=lease.id,
                unit_id=seed["unit_id"],
                occupied_area=Decimal("60"),
                unit_rent_price=Decimal("30"),
            )
        )
        session.commit()
        lease_id = int(lease.id)

    barrier = threading.Barrier(2)

    def activate() -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                LeaseService(session, _ctx(tenant_id)).activate(lease_id)
                return ("activate_ok", None)
            except AppError as exc:
                session.rollback()
                return ("activate_err", exc.code)

    def split() -> tuple[str, str | None]:
        with Session() as session:
            try:
                barrier.wait(timeout=15)
                UnitService(session, _ctx(tenant_id)).split(
                    {
                        "unit_id": seed["unit_id"],
                        "expected_lock_version": 1,
                        "targets": [
                            {"code": f"RACE-A-{suffix}", "name": "竞态A", "rentable_area": 50},
                            {"code": f"RACE-B-{suffix}", "name": "竞态B", "rentable_area": 50},
                        ],
                    }
                )
                return ("split_ok", None)
            except AppError as exc:
                session.rollback()
                return ("split_err", exc.code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(activate), pool.submit(split)]
        results = [future.result() for future in as_completed(futures)]

    states = {state for state, _ in results}
    assert states in ({"activate_ok", "split_err"}, {"activate_err", "split_ok"})
    errors = {code for state, code in results if state.endswith("err")}
    assert errors <= {"UNIT_IN_USE", "UNIT_NOT_FOUND"}

    with Session() as session:
        lease_state = session.get(LeaseContract, lease_id)
        source = session.get(Unit, seed["unit_id"])
        lineage_count = int(
            session.scalar(
                select(func.count())
                .select_from(UnitLineage)
                .where(UnitLineage.source_unit_id == seed["unit_id"])
            )
            or 0
        )
        assert lease_state is not None and source is not None
        if lease_state.status == "ACTIVE":
            assert source.valid_to is None
            assert Decimal(str(source.used_area)) == Decimal("60.00")
            assert source.status == "OCCUPIED"
            assert lineage_count == 0
        else:
            assert lease_state.status == "PENDING_ACTIVE"
            assert source.valid_to is not None and source.status == "RETIRED"
            assert lineage_count == 2
    engine.dispose()

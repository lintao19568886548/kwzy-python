"""Architecture tests: tenant isolation + park data scope."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.models.identity import Tenant
from app.modules.park_property.application.park_service import ParkService
from app.modules.park_property.application.rent_control_service import RentControlService
from app.modules.park_property.application.spatial_service import SpatialService
from app.modules.park_property.application.unit_service import UnitService
from app.shared.tenant_context import ParkScopeMode, TenantContext


def _admin(tenant_id: int) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        user_id=1,
        username="admin",
        park_ids=[],
        permissions=["*"],
        park_scope_mode=ParkScopeMode.ALL,
    )


def _scoped(tenant_id: int, park_ids: list[int]) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        user_id=2,
        username="scoped",
        park_ids=park_ids,
        permissions=[],
        park_scope_mode=ParkScopeMode.LIST,
    )


def test_empty_park_ids_is_not_all_access() -> None:
    ctx = TenantContext(tenant_id=1, park_ids=[], permissions=[])
    assert ctx.has_all_park_access is False
    assert ctx.allows_park(1) is False


def test_star_permission_is_not_all_park_access() -> None:
    """BREAKING：* 仅动作权限，不再授予全园区。"""
    ctx = TenantContext(
        tenant_id=1,
        park_ids=[],
        permissions=["*"],
        park_scope_mode=ParkScopeMode.NONE,
    )
    assert ctx.has_permission("park:write") is True
    assert ctx.has_all_park_access is False
    assert ctx.allows_park(99) is False


def test_explicit_all_parks_mode() -> None:
    ctx = TenantContext(
        tenant_id=1,
        park_ids=[],
        permissions=["park:read"],
        park_scope_mode=ParkScopeMode.ALL,
    )
    assert ctx.has_all_park_access is True
    assert ctx.allows_park(99) is True
    assert ctx.has_permission("park:write") is False


def test_tenant_isolation_park_list(db_session: Session) -> None:
    # tenant 1 parks
    svc1 = ParkService(db_session, _admin(1))
    p1 = svc1.create_park({"name": "T1-园"})

    # tenant 2
    t2 = Tenant(code="t2", name="租户2", status="ACTIVE")
    db_session.add(t2)
    db_session.flush()
    svc2 = ParkService(db_session, _admin(t2.id))
    p2 = svc2.create_park({"name": "T2-园"})

    # tenant1 cannot see tenant2 park
    with pytest.raises(AppError) as ei:
        svc1.get_park(p2["id"])
    assert ei.value.code == "PARK_NOT_FOUND"

    listed = svc1.list_parks()
    names = {i["name"] for i in listed["items"]}
    assert "T1-园" in names
    assert "T2-园" not in names

    # tenant2 cannot see tenant1
    with pytest.raises(AppError):
        svc2.get_park(p1["id"])


def test_park_scope_blocks_other_park(db_session: Session) -> None:
    admin = ParkService(db_session, _admin(1))
    park_a = admin.create_park({"name": "园A"})
    park_b = admin.create_park({"name": "园B"})

    scoped = ParkService(db_session, _scoped(1, [park_a["id"]]))
    # can read A
    got = scoped.get_park(park_a["id"])
    assert got["id"] == park_a["id"]
    # cannot read B
    with pytest.raises(AppError) as ei:
        scoped.get_park(park_b["id"])
    assert ei.value.code == "PARK_NOT_FOUND"

    listed = scoped.list_parks()
    ids = {i["id"] for i in listed["items"]}
    assert park_a["id"] in ids
    assert park_b["id"] not in ids


def test_unit_scope_and_tenant(db_session: Session) -> None:
    admin = ParkService(db_session, _admin(1))
    unit_admin = UnitService(db_session, _admin(1))
    park_a = admin.create_park({"name": "园A2"})
    park_b = admin.create_park({"name": "园B2"})
    u_a = unit_admin.create_unit(
        {"park_id": park_a["id"], "code": "A1", "name": "A单元", "status": "VACANT"}
    )
    u_b = unit_admin.create_unit(
        {"park_id": park_b["id"], "code": "B1", "name": "B单元", "status": "VACANT"}
    )

    scoped_unit = UnitService(db_session, _scoped(1, [park_a["id"]]))
    assert scoped_unit.get_unit(u_a["id"])["id"] == u_a["id"]
    with pytest.raises(AppError):
        scoped_unit.get_unit(u_b["id"])

    # cannot create unit on out-of-scope park
    with pytest.raises(AppError) as ei:
        scoped_unit.create_unit(
            {"park_id": park_b["id"], "code": "X", "name": "越权", "status": "VACANT"}
        )
    assert ei.value.status_code in (403, 404)


def test_tenant_id_spoof_on_create_is_overwritten(db_session: Session) -> None:
    svc = ParkService(db_session, _admin(1))
    park = svc.create_park({"name": "强制租户"})
    assert park["tenant_id"] == 1


def test_asset_tree_and_rent_control_enforce_tenant_and_park_scope(
    db_session: Session,
) -> None:
    admin1 = _admin(1)
    parks1 = ParkService(db_session, admin1)
    spaces1 = SpatialService(db_session, admin1)
    units1 = UnitService(db_session, admin1)
    allowed = parks1.create_park({"name": "范围内园区"})
    denied = parks1.create_park({"name": "范围外园区"})
    allowed_space = spaces1.create(
        {
            "park_id": allowed["id"],
            "code": "A-B1",
            "name": "范围内楼栋",
            "node_type": "BUILDING",
        }
    )
    denied_space = spaces1.create(
        {
            "park_id": denied["id"],
            "code": "D-B1",
            "name": "范围外楼栋",
            "node_type": "BUILDING",
        }
    )
    allowed_unit = units1.create_unit(
        {
            "park_id": allowed["id"],
            "building_id": allowed_space["id"],
            "code": "A-101",
            "name": "范围内单元",
            "rentable_area": 80,
        }
    )
    denied_unit = units1.create_unit(
        {
            "park_id": denied["id"],
            "building_id": denied_space["id"],
            "code": "D-101",
            "name": "范围外单元",
            "rentable_area": 90,
        }
    )

    scoped_ctx = _scoped(1, [allowed["id"]])
    scoped_spaces = SpatialService(db_session, scoped_ctx)
    scoped_rent = RentControlService(db_session, scoped_ctx)
    assert scoped_spaces.tree(allowed["id"])[0]["id"] == allowed_space["id"]
    with pytest.raises(AppError) as park_error:
        scoped_spaces.tree(denied["id"])
    assert park_error.value.code == "PARK_NOT_FOUND"
    assert scoped_rent.summary()["inventory_count"] == 1
    assert scoped_rent.detail(allowed_unit["id"])["id"] == allowed_unit["id"]
    with pytest.raises(AppError) as unit_error:
        scoped_rent.detail(denied_unit["id"])
    assert unit_error.value.code == "UNIT_NOT_FOUND"

    tenant2 = Tenant(code="asset-t2", name="资产租控租户2", status="ACTIVE")
    db_session.add(tenant2)
    db_session.commit()
    foreign_rent = RentControlService(db_session, _admin(int(tenant2.id)))
    assert foreign_rent.summary()["inventory_count"] == 0
    with pytest.raises(AppError) as tenant_error:
        foreign_rent.detail(allowed_unit["id"])
    assert tenant_error.value.code == "UNIT_NOT_FOUND"

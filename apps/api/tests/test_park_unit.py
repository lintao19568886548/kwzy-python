"""Phase06 step1 tests: DB + Park + Unit CRUD and relations."""

from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.infrastructure.database.models.identity import Tenant
from app.infrastructure.database.models.park_property import Building, Park, Unit
from app.modules.park_property.application.park_service import ParkService
from app.modules.park_property.application.unit_service import UnitService
from app.shared.tenant_context import ParkScopeMode, TenantContext


def _ctx(tenant_id: int = 1) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        user_id=1,
        username="admin",
        park_ids=[],
        permissions=["*"],
        park_scope_mode=ParkScopeMode.ALL,
    )


def test_database_connection(db_session: Session) -> None:
    result = db_session.execute(text("SELECT 1")).scalar()
    assert result == 1
    tenant = db_session.scalars(select(Tenant).where(Tenant.code == "default")).first()
    assert tenant is not None
    assert tenant.id >= 1


def test_create_park_service(db_session: Session) -> None:
    svc = ParkService(db_session, _ctx())
    park = svc.create_park(
        {
            "name": "测试园区A",
            "address": "深圳南山",
            "area": 12000,
            "status": "ACTIVE",
        }
    )
    assert park["id"] > 0
    assert park["name"] == "测试园区A"
    assert park["tenant_id"] == 1

    listed = svc.list_parks()
    assert listed["total"] >= 1
    got = svc.get_park(park["id"])
    assert got["address"] == "深圳南山"


def test_create_unit_bound_to_park(db_session: Session) -> None:
    park_svc = ParkService(db_session, _ctx())
    unit_svc = UnitService(db_session, _ctx())

    park = park_svc.create_park({"name": "园区B", "address": "东莞"})
    unit = unit_svc.create_unit(
        {
            "park_id": park["id"],
            "code": "3F-A",
            "name": "三楼A区",
            "rentable_area": 800,
            "base_rent_price": 25.5,
            "status": "VACANT",
        }
    )
    assert unit["park_id"] == park["id"]
    assert unit["building_id"] > 0
    assert unit["status"] == "VACANT"

    # relation: unit -> park -> building
    u = db_session.get(Unit, unit["id"])
    assert u is not None
    assert u.park_id == park["id"]
    b = db_session.get(Building, u.building_id)
    assert b is not None
    assert b.park_id == park["id"]
    p = db_session.get(Park, u.park_id)
    assert p is not None
    assert p.name == "园区B"


def test_unit_status_transition(db_session: Session) -> None:
    park_svc = ParkService(db_session, _ctx())
    unit_svc = UnitService(db_session, _ctx())
    park = park_svc.create_park({"name": "园区C"})
    unit = unit_svc.create_unit(
        {"park_id": park["id"], "code": "U1", "name": "单元1", "status": "VACANT"}
    )
    updated = unit_svc.change_status(unit["id"], "RESERVED")
    assert updated["status"] == "RESERVED"


def test_api_park_unit_flow(client) -> None:
    # create park
    r = client.post(
        "/api/v1/parks",
        json={"name": "API园区", "address": "广州", "area": 5000},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == "OK"
    park_id = body["data"]["id"]

    # list parks
    r = client.get("/api/v1/parks")
    assert r.status_code == 200
    assert r.json()["data"]["total"] >= 1

    # create unit
    r = client.post(
        "/api/v1/units",
        json={
            "park_id": park_id,
            "code": "B1-01",
            "name": "一号厂房",
            "rentable_area": 1000,
            "status": "VACANT",
        },
    )
    assert r.status_code == 200
    unit = r.json()["data"]
    assert unit["park_id"] == park_id

    # list units by park
    r = client.get(f"/api/v1/units?park_id={park_id}")
    assert r.status_code == 200
    assert r.json()["data"]["total"] >= 1

    # patch unit status
    r = client.patch(
        f"/api/v1/units/{unit['id']}/status",
        json={"status": "MAINTENANCE"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "MAINTENANCE"

    # get park
    r = client.get(f"/api/v1/parks/{park_id}")
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "API园区"

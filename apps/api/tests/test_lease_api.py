"""Lease API integration tests (SQLite)."""

from __future__ import annotations

from decimal import Decimal

from app.core.security import create_access_token
from app.infrastructure.database.models.park_property import Unit
from sqlalchemy import select
from sqlalchemy.orm import Session


def _admin_headers() -> dict:
    token = create_access_token(
        subject="admin",
        claims={
            "uid": 1,
            "tenant_id": 1,
            "permissions": ["*"],
            "park_ids": [],
            "park_scope_mode": "ALL",
        },
    )
    return {"Authorization": f"Bearer {token}"}


def _token(*, permissions: list[str], mode: str = "ALL", park_ids: list[int] | None = None) -> dict:
    token = create_access_token(
        subject="lease-user",
        claims={
            "uid": 1,
            "tenant_id": 1,
            "permissions": permissions,
            "park_ids": park_ids or [],
            "park_scope_mode": mode,
        },
    )
    return {"Authorization": f"Bearer {token}"}


def _seed_park_unit_party(client, h: dict) -> tuple[int, int, int]:
    park = client.post("/api/v1/parks", headers=h, json={"name": "租约园A", "address": "测试路1号"}).json()[
        "data"
    ]
    # building optional via unit create path
    unit = client.post(
        "/api/v1/units",
        headers=h,
        json={
            "park_id": park["id"],
            "name": "A-101",
            "code": "A101",
            "rentable_area": 100,
            "status": "VACANT",
        },
    )
    assert unit.status_code == 200, unit.text
    unit_id = unit.json()["data"]["id"]
    party = client.post(
        "/api/v1/parties",
        headers=h,
        json={"name": "承租企业甲", "party_type": "ORGANIZATION"},
    ).json()["data"]
    return int(park["id"]), int(unit_id), int(party["id"])


def test_lease_lifecycle_and_used_area(client, db_session: Session) -> None:
    h = _admin_headers()
    park_id, unit_id, party_id = _seed_park_unit_party(client, h)

    created = client.post(
        "/api/v1/leases",
        headers=h,
        json={
            "park_id": park_id,
            "party_id": party_id,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "deposit_amount": "10000",
            "units": [{"unit_id": unit_id, "occupied_area": "80", "unit_rent_price": "50"}],
            "terms": [{"term_type": "INCREASE", "rate": "0.05", "description": "年增5%"}],
        },
    )
    assert created.status_code == 200, created.text
    cid = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "DRAFT"
    assert len(created.json()["data"]["units"]) == 1

    sub = client.post(f"/api/v1/leases/{cid}/submit", headers=h)
    assert sub.status_code == 200
    assert sub.json()["data"]["status"] == "PENDING_ACTIVE"

    act = client.post(f"/api/v1/leases/{cid}/activate", headers=h)
    assert act.status_code == 200, act.text
    assert act.json()["data"]["status"] == "ACTIVE"

    unit = db_session.scalars(select(Unit).where(Unit.id == unit_id)).first()
    db_session.refresh(unit)
    assert Decimal(str(unit.used_area)) == Decimal("80")
    assert unit.status == "OCCUPIED"

    # conflict: second contract over capacity
    p2 = client.post(
        "/api/v1/parties",
        headers=h,
        json={"name": "承租企业乙", "party_type": "ORGANIZATION"},
    ).json()["data"]["id"]
    c2 = client.post(
        "/api/v1/leases",
        headers=h,
        json={
            "park_id": park_id,
            "party_id": p2,
            "start_date": "2026-01-01",
            "end_date": "2026-06-30",
            "units": [{"unit_id": unit_id, "occupied_area": "30", "unit_rent_price": "1"}],
        },
    ).json()["data"]["id"]
    client.post(f"/api/v1/leases/{c2}/submit", headers=h)
    conflict = client.post(f"/api/v1/leases/{c2}/activate", headers=h)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "OCCUPANCY_CONFLICT"

    term = client.post(f"/api/v1/leases/{cid}/terminate", headers=h)
    assert term.status_code == 200
    assert term.json()["data"]["status"] == "TERMINATED"
    db_session.refresh(unit)
    assert Decimal(str(unit.used_area)) == Decimal("0")
    assert unit.status == "VACANT"


def test_lease_permission_denied(client) -> None:
    h = _admin_headers()
    park_id, unit_id, party_id = _seed_park_unit_party(client, h)
    limited = _token(permissions=["lease:read"], mode="ALL")
    r = client.post(
        "/api/v1/leases",
        headers=limited,
        json={
            "park_id": park_id,
            "party_id": party_id,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "units": [{"unit_id": unit_id, "occupied_area": "10"}],
        },
    )
    assert r.status_code == 403


def test_lease_empty_park_scope(client) -> None:
    h = _admin_headers()
    park_id, unit_id, party_id = _seed_park_unit_party(client, h)
    client.post(
        "/api/v1/leases",
        headers=h,
        json={
            "park_id": park_id,
            "party_id": party_id,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "units": [{"unit_id": unit_id, "occupied_area": "10"}],
        },
    )
    empty = _token(permissions=["lease:read"], mode="NONE", park_ids=[])
    listed = client.get("/api/v1/leases", headers=empty)
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] == 0

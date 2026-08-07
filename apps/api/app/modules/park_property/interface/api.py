"""Park / Unit REST interface."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.park_property.application.park_service import ParkService
from app.modules.park_property.application.unit_service import UnitService
from app.modules.park_property.interface.schemas import (
    ParkCreate,
    ParkUpdate,
    UnitCreate,
    UnitStatusUpdate,
    UnitUpdate,
)
from app.shared.deps import TenantContext, get_tenant_context, require_permissions
from app.shared.response import ok

router = APIRouter(tags=["Parks", "Units"])


def _park_service(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> ParkService:
    return ParkService(db, ctx)


def _unit_service(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> UnitService:
    return UnitService(db, ctx)


@router.get("/parks", dependencies=[Depends(require_permissions("park:read"))])
def list_parks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    svc: ParkService = Depends(_park_service),
) -> dict:
    data = svc.list_parks(page=page, page_size=page_size, keyword=keyword, status=status)
    return ok(data)


@router.post("/parks", dependencies=[Depends(require_permissions("park:write"))])
def create_park(
    body: ParkCreate,
    svc: ParkService = Depends(_park_service),
) -> dict:
    data = svc.create_park(body.model_dump())
    return ok(data, message="created")


@router.get(
    "/parks/{park_id}",
    dependencies=[Depends(require_permissions("park:read"))],
)
def get_park(park_id: int, svc: ParkService = Depends(_park_service)) -> dict:
    return ok(svc.get_park(park_id))


@router.patch(
    "/parks/{park_id}",
    dependencies=[Depends(require_permissions("park:write"))],
)
def update_park(
    park_id: int,
    body: ParkUpdate,
    svc: ParkService = Depends(_park_service),
) -> dict:
    data = svc.update_park(park_id, body.model_dump(exclude_unset=True))
    return ok(data, message="updated")


@router.delete(
    "/parks/{park_id}",
    dependencies=[Depends(require_permissions("park:write"))],
)
def delete_park(park_id: int, svc: ParkService = Depends(_park_service)) -> dict:
    svc.delete_park(park_id)
    return ok(None, message="deleted")


@router.get("/units", dependencies=[Depends(require_permissions("unit:read"))])
def list_units(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    park_id: Optional[int] = None,
    status: Optional[str] = None,
    svc: UnitService = Depends(_unit_service),
) -> dict:
    data = svc.list_units(page=page, page_size=page_size, park_id=park_id, status=status)
    return ok(data)


@router.post("/units", dependencies=[Depends(require_permissions("unit:write"))])
def create_unit(body: UnitCreate, svc: UnitService = Depends(_unit_service)) -> dict:
    data = svc.create_unit(body.model_dump())
    return ok(data, message="created")


@router.get(
    "/units/{unit_id}",
    dependencies=[Depends(require_permissions("unit:read"))],
)
def get_unit(unit_id: int, svc: UnitService = Depends(_unit_service)) -> dict:
    return ok(svc.get_unit(unit_id))


@router.patch(
    "/units/{unit_id}",
    dependencies=[Depends(require_permissions("unit:write"))],
)
def update_unit(
    unit_id: int,
    body: UnitUpdate,
    svc: UnitService = Depends(_unit_service),
) -> dict:
    data = svc.update_unit(unit_id, body.model_dump(exclude_unset=True))
    return ok(data, message="updated")


@router.patch(
    "/units/{unit_id}/status",
    dependencies=[Depends(require_permissions("unit:write"))],
)
def change_unit_status(
    unit_id: int,
    body: UnitStatusUpdate,
    svc: UnitService = Depends(_unit_service),
) -> dict:
    data = svc.change_status(unit_id, body.status)
    return ok(data, message="status_updated")


@router.delete(
    "/units/{unit_id}",
    dependencies=[Depends(require_permissions("unit:write"))],
)
def delete_unit(unit_id: int, svc: UnitService = Depends(_unit_service)) -> dict:
    svc.delete_unit(unit_id)
    return ok(None, message="deleted")

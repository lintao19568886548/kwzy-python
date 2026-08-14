"""Park / Unit REST interface."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.park_property.application.asset_template_service import AssetTemplateService
from app.modules.park_property.application.park_service import ParkService
from app.modules.park_property.application.rent_control_service import RentControlService
from app.modules.park_property.application.spatial_service import SpatialService
from app.modules.park_property.application.unit_service import UnitService
from app.modules.park_property.interface.schemas import (
    AssetTemplateCreate,
    AssetTemplateDraftUpdate,
    ExpectedVersionCommand,
    ParkCreate,
    ParkUpdate,
    SpatialCreate,
    SpatialUpdate,
    UnitCreate,
    UnitMergeRequest,
    UnitSplitRequest,
    UnitStatusUpdate,
    UnitUpdate,
    UnitVersionCreate,
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


def _spatial_service(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> SpatialService:
    return SpatialService(db, ctx)


def _rent_control_service(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> RentControlService:
    return RentControlService(db, ctx)


def _asset_template_service(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> AssetTemplateService:
    return AssetTemplateService(db, ctx)


@router.get(
    "/asset-templates",
    dependencies=[Depends(require_permissions("asset.template.read"))],
)
def list_asset_templates(svc: AssetTemplateService = Depends(_asset_template_service)) -> dict:
    return ok(svc.list_templates())


@router.post(
    "/asset-templates",
    dependencies=[Depends(require_permissions("asset.template.write"))],
)
def create_asset_template(
    body: AssetTemplateCreate,
    svc: AssetTemplateService = Depends(_asset_template_service),
) -> dict:
    return ok(svc.create(body.model_dump()), message="created")


@router.get(
    "/asset-templates/{template_id}",
    dependencies=[Depends(require_permissions("asset.template.read"))],
)
def get_asset_template(
    template_id: int,
    svc: AssetTemplateService = Depends(_asset_template_service),
) -> dict:
    return ok(svc.get_template(template_id))


@router.put(
    "/asset-templates/{template_id}/draft",
    dependencies=[Depends(require_permissions("asset.template.write"))],
)
def update_asset_template_draft(
    template_id: int,
    body: AssetTemplateDraftUpdate,
    svc: AssetTemplateService = Depends(_asset_template_service),
) -> dict:
    return ok(svc.update_draft(template_id, body.model_dump(exclude_unset=True)), message="updated")


@router.post(
    "/asset-templates/{template_id}/publish",
    dependencies=[Depends(require_permissions("asset.template.write"))],
)
def publish_asset_template(
    template_id: int,
    body: ExpectedVersionCommand,
    svc: AssetTemplateService = Depends(_asset_template_service),
) -> dict:
    return ok(svc.publish(template_id, body.expected_version), message="published")


@router.post(
    "/asset-templates/{template_id}/drafts",
    dependencies=[Depends(require_permissions("asset.template.write"))],
)
def new_asset_template_draft(
    template_id: int,
    body: ExpectedVersionCommand,
    svc: AssetTemplateService = Depends(_asset_template_service),
) -> dict:
    return ok(svc.new_draft(template_id, body.expected_version), message="draft_created")


@router.post(
    "/asset-templates/{template_id}/retire",
    dependencies=[Depends(require_permissions("asset.template.write"))],
)
def retire_asset_template(
    template_id: int,
    body: ExpectedVersionCommand,
    svc: AssetTemplateService = Depends(_asset_template_service),
) -> dict:
    return ok(svc.retire(template_id, body.expected_version), message="retired")


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


@router.get("/spaces/tree", dependencies=[Depends(require_permissions("unit:read"))])
def spatial_tree(
    park_id: int,
    svc: SpatialService = Depends(_spatial_service),
) -> dict:
    return ok(svc.tree(park_id))


@router.get("/spaces/{node_id}", dependencies=[Depends(require_permissions("unit:read"))])
def get_space(node_id: int, svc: SpatialService = Depends(_spatial_service)) -> dict:
    return ok(svc.get(node_id))


@router.post("/spaces", dependencies=[Depends(require_permissions("unit:write"))])
def create_space(
    body: SpatialCreate,
    svc: SpatialService = Depends(_spatial_service),
) -> dict:
    return ok(svc.create(body.model_dump()), message="created")


@router.patch("/spaces/{node_id}", dependencies=[Depends(require_permissions("unit:write"))])
def update_space(
    node_id: int,
    body: SpatialUpdate,
    svc: SpatialService = Depends(_spatial_service),
) -> dict:
    return ok(svc.update(node_id, body.model_dump(exclude_unset=True)), message="updated")


@router.delete("/spaces/{node_id}", dependencies=[Depends(require_permissions("unit:write"))])
def deactivate_space(
    node_id: int,
    svc: SpatialService = Depends(_spatial_service),
) -> dict:
    return ok(svc.deactivate(node_id), message="deactivated")


@router.get(
    "/rent-control/summary",
    dependencies=[Depends(require_permissions("unit:read"))],
)
def rent_control_summary(
    park_id: Optional[int] = None,
    space_id: Optional[int] = None,
    status: Optional[str] = None,
    usage_type: Optional[str] = None,
    keyword: Optional[str] = None,
    svc: RentControlService = Depends(_rent_control_service),
) -> dict:
    return ok(svc.summary(park_id=park_id, space_id=space_id, status=status, usage_type=usage_type, keyword=keyword))


@router.get(
    "/rent-control/units",
    dependencies=[Depends(require_permissions("unit:read"))],
)
def rent_control_units(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    park_id: Optional[int] = None,
    space_id: Optional[int] = None,
    status: Optional[str] = None,
    usage_type: Optional[str] = None,
    keyword: Optional[str] = None,
    svc: RentControlService = Depends(_rent_control_service),
) -> dict:
    return ok(svc.list_units(page=page, page_size=page_size, park_id=park_id, space_id=space_id, status=status, usage_type=usage_type, keyword=keyword))


@router.get(
    "/rent-control/matrix",
    dependencies=[Depends(require_permissions("unit:read"))],
)
def rent_control_matrix(
    park_id: Optional[int] = None,
    space_id: Optional[int] = None,
    status: Optional[str] = None,
    usage_type: Optional[str] = None,
    keyword: Optional[str] = None,
    svc: RentControlService = Depends(_rent_control_service),
) -> dict:
    return ok(svc.matrix(park_id=park_id, space_id=space_id, status=status, usage_type=usage_type, keyword=keyword))


@router.get(
    "/rent-control/map",
    dependencies=[Depends(require_permissions("unit:read"))],
)
def rent_control_map(
    park_id: Optional[int] = None,
    space_id: Optional[int] = None,
    status: Optional[str] = None,
    usage_type: Optional[str] = None,
    keyword: Optional[str] = None,
    svc: RentControlService = Depends(_rent_control_service),
) -> dict:
    return ok(svc.map_projection(park_id=park_id, space_id=space_id, status=status, usage_type=usage_type, keyword=keyword))


@router.get(
    "/rent-control/vacancies",
    dependencies=[Depends(require_permissions("unit:read"))],
)
def rent_control_vacancies(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    as_of: Optional[date] = None,
    park_id: Optional[int] = None,
    space_id: Optional[int] = None,
    status: Optional[str] = None,
    usage_type: Optional[str] = None,
    keyword: Optional[str] = None,
    svc: RentControlService = Depends(_rent_control_service),
) -> dict:
    return ok(svc.vacancies(page=page, page_size=page_size, as_of=as_of, park_id=park_id, space_id=space_id, status=status, usage_type=usage_type, keyword=keyword))


@router.get(
    "/rent-control/expiries",
    dependencies=[Depends(require_permissions("unit:read"))],
)
def rent_control_expiries(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    date_from: Optional[date] = None,
    days: int = Query(90, ge=1, le=366),
    park_id: Optional[int] = None,
    space_id: Optional[int] = None,
    svc: RentControlService = Depends(_rent_control_service),
) -> dict:
    return ok(svc.expiries(page=page, page_size=page_size, date_from=date_from, days=days, park_id=park_id, space_id=space_id))


@router.get(
    "/rent-control/analysis",
    dependencies=[Depends(require_permissions("unit:read"))],
)
def rent_control_analysis(
    park_id: Optional[int] = None,
    space_id: Optional[int] = None,
    status: Optional[str] = None,
    usage_type: Optional[str] = None,
    keyword: Optional[str] = None,
    svc: RentControlService = Depends(_rent_control_service),
) -> dict:
    return ok(svc.analysis(park_id=park_id, space_id=space_id, status=status, usage_type=usage_type, keyword=keyword))


@router.get(
    "/rent-control/units/{unit_id}",
    dependencies=[Depends(require_permissions("unit:read"))],
)
def rent_control_detail(
    unit_id: int,
    svc: RentControlService = Depends(_rent_control_service),
) -> dict:
    return ok(svc.detail(unit_id))


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


@router.post("/units/split", dependencies=[Depends(require_permissions("unit:write"))])
def split_unit(body: UnitSplitRequest, svc: UnitService = Depends(_unit_service)) -> dict:
    return ok(svc.split(body.model_dump()), message="split")


@router.post("/units/merge", dependencies=[Depends(require_permissions("unit:write"))])
def merge_units(body: UnitMergeRequest, svc: UnitService = Depends(_unit_service)) -> dict:
    return ok(svc.merge(body.model_dump()), message="merged")


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


@router.get(
    "/units/{unit_id}/history",
    dependencies=[Depends(require_permissions("unit:read"))],
)
def unit_history(unit_id: int, svc: UnitService = Depends(_unit_service)) -> dict:
    return ok(svc.history(unit_id))


@router.get(
    "/units/{unit_id}/lineage",
    dependencies=[Depends(require_permissions("unit:read"))],
)
def unit_lineage(unit_id: int, svc: UnitService = Depends(_unit_service)) -> dict:
    return ok(svc.lineage(unit_id))


@router.post(
    "/units/{unit_id}/versions",
    dependencies=[Depends(require_permissions("unit:write"))],
)
def create_unit_version(
    unit_id: int,
    body: UnitVersionCreate,
    svc: UnitService = Depends(_unit_service),
) -> dict:
    return ok(svc.create_version(unit_id, body.model_dump(exclude_unset=True)), message="version_created")

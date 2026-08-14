"""平台组织治理 REST 路由；仅负责 Schema、Depends 与应用服务调用。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.identity.application.organization_governance_service import (
    FieldPolicyAdminService,
    OrganizationGovernanceService,
)
from app.modules.identity.interface.organization_governance_schemas import (
    AssignmentEndRequest,
    FieldPolicyUpsertRequest,
    GroupCreateRequest,
    GroupUpdateRequest,
    ParkAssignmentRequest,
    PositionCreateRequest,
    PositionUpdateRequest,
    RegionCreateRequest,
    RegionUpdateRequest,
    UserPositionAssignmentRequest,
)
from app.shared.deps import require_permissions
from app.shared.response import ok
from app.shared.tenant_context import TenantContext

router = APIRouter(
    prefix="/system/organization-governance",
    tags=["OrganizationGovernance"],
)


def _governance(db: Session, ctx: TenantContext) -> OrganizationGovernanceService:
    return OrganizationGovernanceService(db, ctx)


@router.get("/hierarchy")
def hierarchy(
    ctx: TenantContext = Depends(require_permissions("identity.org_governance.read")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(_governance(db, ctx).hierarchy())


@router.post("/groups")
def create_group(
    body: GroupCreateRequest,
    ctx: TenantContext = Depends(require_permissions("identity.org_governance.write")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(_governance(db, ctx).create_group(body.model_dump()), message="created")


@router.patch("/groups/{group_id}")
def update_group(
    group_id: int,
    body: GroupUpdateRequest,
    ctx: TenantContext = Depends(require_permissions("identity.org_governance.write")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(
        _governance(db, ctx).update_group(
            group_id,
            body.model_dump(exclude_unset=True),
        ),
        message="updated",
    )


@router.post("/regions")
def create_region(
    body: RegionCreateRequest,
    ctx: TenantContext = Depends(require_permissions("identity.org_governance.write")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(_governance(db, ctx).create_region(body.model_dump()), message="created")


@router.patch("/regions/{region_id}")
def update_region(
    region_id: int,
    body: RegionUpdateRequest,
    ctx: TenantContext = Depends(require_permissions("identity.org_governance.write")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(
        _governance(db, ctx).update_region(
            region_id,
            body.model_dump(exclude_unset=True),
        ),
        message="updated",
    )


@router.post("/park-assignments")
def assign_park(
    body: ParkAssignmentRequest,
    ctx: TenantContext = Depends(require_permissions("identity.org_governance.write")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(_governance(db, ctx).assign_park(body.model_dump()), message="assigned")


@router.get("/parks/{park_id}/assignment-history")
def park_assignment_history(
    park_id: int,
    ctx: TenantContext = Depends(require_permissions("identity.org_governance.read")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(_governance(db, ctx).park_assignment_history(park_id))


@router.get("/positions")
def list_positions(
    ctx: TenantContext = Depends(require_permissions("identity.org_governance.read")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(_governance(db, ctx).list_positions())


@router.post("/positions")
def create_position(
    body: PositionCreateRequest,
    ctx: TenantContext = Depends(require_permissions("identity.org_governance.write")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(_governance(db, ctx).create_position(body.model_dump()), message="created")


@router.patch("/positions/{position_id}")
def update_position(
    position_id: int,
    body: PositionUpdateRequest,
    ctx: TenantContext = Depends(require_permissions("identity.org_governance.write")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(
        _governance(db, ctx).update_position(
            position_id,
            body.model_dump(exclude_unset=True),
        ),
        message="updated",
    )


@router.get("/user-assignments")
def list_user_assignments(
    user_id: int | None = Query(default=None, gt=0),
    current_only: bool = False,
    ctx: TenantContext = Depends(require_permissions("identity.org_governance.read")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(
        _governance(db, ctx).list_user_assignments(
            user_id=user_id,
            current_only=current_only,
        )
    )


@router.post("/user-assignments")
def assign_user(
    body: UserPositionAssignmentRequest,
    ctx: TenantContext = Depends(require_permissions("identity.org_governance.write")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(_governance(db, ctx).assign_user(body.model_dump()), message="assigned")


@router.post("/user-assignments/{assignment_id}/end")
def end_user_assignment(
    assignment_id: int,
    body: AssignmentEndRequest | None = None,
    ctx: TenantContext = Depends(require_permissions("identity.org_governance.write")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(
        _governance(db, ctx).end_user_assignment(
            assignment_id,
            body.model_dump() if body else {},
        ),
        message="ended",
    )


@router.get("/protected-fields")
def list_protected_fields(
    ctx: TenantContext = Depends(require_permissions("identity.field_policy.read")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(FieldPolicyAdminService(db, ctx).list_protected_fields())


@router.get("/field-policies")
def list_field_policies(
    ctx: TenantContext = Depends(require_permissions("identity.field_policy.read")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(FieldPolicyAdminService(db, ctx).list_policies())


@router.put("/field-policies")
def upsert_field_policy(
    body: FieldPolicyUpsertRequest,
    ctx: TenantContext = Depends(require_permissions("identity.field_policy.write")),
    db: Session = Depends(get_db),
) -> dict:
    return ok(
        FieldPolicyAdminService(db, ctx).upsert_policy(body.model_dump()),
        message="saved",
    )

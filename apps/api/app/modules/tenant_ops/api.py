from fastapi import APIRouter, Depends

from app.shared.deps import CurrentUser, get_current_user
from app.shared.response import ok

router = APIRouter(prefix="/tenants", tags=["TenantOps"])


@router.get("/current")
def current_tenant(user: CurrentUser = Depends(get_current_user)) -> dict:
    return ok({"id": user.tenant_id, "status": "ACTIVE"})

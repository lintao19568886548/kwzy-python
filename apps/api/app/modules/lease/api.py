from fastapi import APIRouter, Depends

from app.shared.deps import CurrentUser, get_current_user
from app.shared.response import ok

router = APIRouter(tags=["Leases"])


@router.get("/parties")
def list_parties(user: CurrentUser = Depends(get_current_user)) -> dict:
    _ = user
    return ok({"total": 0, "page": 1, "page_size": 20, "items": []})


@router.get("/leases")
def list_leases(user: CurrentUser = Depends(get_current_user)) -> dict:
    _ = user
    return ok({"total": 0, "page": 1, "page_size": 20, "items": []})


@router.post("/leases")
def create_lease(payload: dict, user: CurrentUser = Depends(get_current_user)) -> dict:
    _ = user
    return ok({"id": 0, "status": "DRAFT", **payload}, message="created (stub)")


@router.post("/leases/{lease_id}/activate")
def activate_lease(lease_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    _ = user
    return ok({"id": lease_id, "status": "ACTIVE"}, message="activated (stub)")

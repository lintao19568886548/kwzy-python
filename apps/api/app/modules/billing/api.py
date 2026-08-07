from fastapi import APIRouter, Depends

from app.shared.deps import CurrentUser, get_current_user
from app.shared.response import ok

router = APIRouter(tags=["Bills"])


@router.get("/bills")
def list_bills(user: CurrentUser = Depends(get_current_user)) -> dict:
    _ = user
    return ok({"total": 0, "page": 1, "page_size": 20, "items": []})


@router.post("/bills")
def create_bill(payload: dict, user: CurrentUser = Depends(get_current_user)) -> dict:
    _ = user
    return ok({"id": 0, "status": "DRAFT", **payload}, message="created (stub)")


@router.post("/bills/{bill_id}/issue")
def issue_bill(bill_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    _ = user
    return ok({"id": bill_id, "status": "ISSUED"}, message="issued (stub)")


@router.post("/bills/duplicate-check")
def duplicate_check(payload: dict, user: CurrentUser = Depends(get_current_user)) -> dict:
    _ = user
    _ = payload
    return ok({"has_duplicate": False, "candidates": []})

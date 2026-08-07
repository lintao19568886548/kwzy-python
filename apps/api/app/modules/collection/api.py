from fastapi import APIRouter, Depends

from app.shared.deps import CurrentUser, get_current_user
from app.shared.response import ok

router = APIRouter(tags=["Payments", "Collection"])


@router.get("/payments")
def list_payments(user: CurrentUser = Depends(get_current_user)) -> dict:
    _ = user
    return ok({"total": 0, "page": 1, "page_size": 20, "items": []})


@router.post("/payments")
def create_payment(payload: dict, user: CurrentUser = Depends(get_current_user)) -> dict:
    _ = user
    return ok({"id": 0, "status": "CONFIRMED", **payload}, message="created (stub)")


@router.post("/collection/sms/preview")
def preview_sms(payload: dict, user: CurrentUser = Depends(get_current_user)) -> dict:
    _ = user
    bill_ids = payload.get("bill_ids") or []
    items = [{"bill_id": bid, "phone": "", "content": f"催缴预览(stub) bill={bid}"} for bid in bill_ids]
    return ok({"items": items})

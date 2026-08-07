from fastapi import APIRouter, Depends

from app.shared.deps import CurrentUser, get_current_user
from app.shared.response import ok

router = APIRouter(tags=["Leads"])


@router.get("/leads")
def list_leads(user: CurrentUser = Depends(get_current_user)) -> dict:
    _ = user
    return ok({"total": 0, "page": 1, "page_size": 20, "items": []})


@router.post("/leads")
def create_lead(payload: dict, user: CurrentUser = Depends(get_current_user)) -> dict:
    _ = user
    return ok({"id": 0, "status": "NEW", **payload}, message="created (stub)")


@router.post("/leads/{lead_id}/convert")
def convert_lead(lead_id: int, payload: dict | None = None, user: CurrentUser = Depends(get_current_user)) -> dict:
    _ = user
    _ = payload
    return ok(
        {
            "lead": {"id": lead_id, "status": "WON"},
            "party": {"id": 0},
            "lease": {"id": 0, "status": "DRAFT"},
        },
        message="converted (stub)",
    )

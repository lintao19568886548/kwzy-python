from fastapi import APIRouter, Depends

from app.shared.deps import CurrentUser, get_current_user
from app.shared.response import ok

router = APIRouter(prefix="/ledger", tags=["Finance"])


@router.get("/entries")
def list_entries(user: CurrentUser = Depends(get_current_user)) -> dict:
    _ = user
    return ok({"total": 0, "page": 1, "page_size": 20, "items": []})

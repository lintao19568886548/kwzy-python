from fastapi import APIRouter, Depends

from app.shared.deps import CurrentUser, get_current_user
from app.shared.response import ok

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/workbench")
def workbench(user: CurrentUser = Depends(get_current_user)) -> dict:
    _ = user
    return ok(
        {
            "todos": [],
            "expiring_contracts": 0,
            "unpaid_bills": 0,
            "open_collection_cases": 0,
        }
    )

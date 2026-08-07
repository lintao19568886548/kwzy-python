from fastapi import APIRouter, Depends

from app.shared.deps import CurrentUser, get_current_user
from app.shared.response import ok

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/bill-recognize/jobs")
def create_job(user: CurrentUser = Depends(get_current_user)) -> dict:
    _ = user
    return ok({"id": 0, "job_type": "BILL_RECOGNIZE", "status": "PENDING"}, message="created (stub)")


@router.get("/bill-recognize/jobs/{job_id}")
def get_job(job_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    _ = user
    return ok({"id": job_id, "job_type": "BILL_RECOGNIZE", "status": "SUCCEEDED", "result_meta": {}})

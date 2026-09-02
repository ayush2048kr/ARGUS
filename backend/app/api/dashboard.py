from fastapi import APIRouter, Depends

from app.auth.dependencies import require_role
from app.services.dashboard_service import get_dashboard_summary


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)


@router.get("/summary")
def dashboard_summary(
    current_user: dict = Depends(require_role(["admin", "analyst"]))
):
    return get_dashboard_summary()
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_current_user, require_role
from app.models.alert import Alert
from app.services.alert_service import (
    create_alert,
    get_alert_by_id,
    get_all_alerts,
    update_alert_status,
)


router = APIRouter(
    prefix="/alerts",
    tags=["Alerts"]
)


@router.post("/")
def create_new_alert(
    alert: Alert,
    current_user: dict = Depends(require_role(["admin", "analyst"]))
):
    return create_alert(alert.model_dump())


@router.get("/")
def list_alerts(
    current_user: dict = Depends(require_role(["admin", "analyst"]))
):
    return get_all_alerts()


@router.get("/{alert_id}")
def get_alert(
    alert_id: str,
    current_user: dict = Depends(require_role(["admin", "analyst"]))
):
    alert = get_alert_by_id(alert_id)

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    return alert


@router.patch("/{alert_id}/status")
def update_status(
    alert_id: str,
    new_status: Literal["open", "investigating", "resolved"],
    current_user: dict = Depends(require_role(["admin", "analyst"]))
):
    success = update_alert_status(
        alert_id,
        new_status
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    return {
        "message": "Alert status updated successfully",
        "alert_id": alert_id,
        "status": new_status
    }
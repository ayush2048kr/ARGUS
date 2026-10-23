from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import require_role
from app.models.risk import RiskAssessment
from app.services.risk_service import (
    create_risk_assessment,
    get_risk_by_id,
    get_risks_for_user,
    get_all_risks,
)


router = APIRouter(
    prefix="/risks",
    tags=["Risks"]
)


@router.post("/")
def create_risk(
    risk: RiskAssessment,
    current_user: dict = Depends(require_role(["admin", "analyst"]))
):
    return create_risk_assessment(risk.model_dump())


@router.get("/")
def list_risks(
    current_user: dict = Depends(require_role(["admin", "analyst"]))
):
    return get_all_risks()


@router.get("/user/{user_id}")
def list_user_risks(
    user_id: str,
    current_user: dict = Depends(require_role(["admin", "analyst"]))
):
    return get_risks_for_user(user_id)


@router.get("/{risk_id}")
def get_risk(
    risk_id: str,
    current_user: dict = Depends(require_role(["admin", "analyst"]))
):
    risk = get_risk_by_id(risk_id)

    if not risk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Risk assessment not found"
        )

    return risk
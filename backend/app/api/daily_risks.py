
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.errors import BulkWriteError, PyMongoError

from app.auth.dependencies import require_role
from app.models.daily_risk import DailyRisk
from app.services.daily_risk_service import (
    upsert_daily_risks,
    get_daily_risks,
    get_daily_risks_for_user,
)
from app.services.daily_risk_service import (
    upsert_daily_risks,
    get_daily_risks,
    get_daily_risks_for_user,
    get_latest_daily_risks,
)
router = APIRouter(prefix="/daily-risks", tags=["Daily ML Risks"])


@router.post("/bulk")
def import_daily_risks(
    records: list[DailyRisk],
    current_user: dict = Depends(require_role(["admin", "analyst"])),
):
    if not records:
        raise HTTPException(status_code=400, detail="No records provided")

    keys = [(r.user_id, r.date) for r in records]
    if len(keys) != len(set(keys)):
        raise HTTPException(
            status_code=422,
            detail="Duplicate user/date records in request",
        )

    try:
        return upsert_daily_risks([r.model_dump() for r in records])
    except BulkWriteError:
        raise HTTPException(status_code=409, detail="Daily risk database conflict")
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database unavailable")


@router.get("/")
def list_daily_risks(
    user_id: str | None = None,
    risk_date: date | None = Query(default=None),
    risk_level: str | None = None,
    limit: int = Query(default=500, ge=1, le=5000),
    current_user: dict = Depends(require_role(["admin", "analyst"])),
):
    allowed_levels = {"LOW", "MEDIUM", "HIGH", "CRITICAL", "UNAVAILABLE"}

    if risk_level and risk_level.upper() not in allowed_levels:
        raise HTTPException(status_code=422, detail="Invalid risk level")

    try:
        return get_daily_risks(
            user_id=user_id,
            date_value=risk_date.isoformat() if risk_date else None,
            risk_level=risk_level.upper() if risk_level else None,
            limit=limit,
        )
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database unavailable")

@router.get("/latest")
def list_latest_daily_risks(
    limit: int = Query(default=5000, ge=1, le=5000),
    current_user: dict = Depends(require_role(["admin", "analyst"])),
):
    try:
        return get_latest_daily_risks(limit=limit)
    except PyMongoError:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        )
@router.get("/user/{user_id}")
def list_user_daily_risks(
    user_id: str,
    current_user: dict = Depends(require_role(["admin", "analyst"])),
):
    try:
        return get_daily_risks_for_user(user_id)
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database unavailable")

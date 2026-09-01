from fastapi import APIRouter, Depends

from app.models.event import Event
from app.database.mongodb import events_collection
from app.auth.dependencies import get_current_user, require_role


router = APIRouter(
    prefix="/events",
    tags=["Events"]
)


@router.post("/")
def create_event(
    event: Event,
    current_user: dict = Depends(get_current_user)
):
    event_data = event.model_dump()

    events_collection.insert_one(event_data)

    return {
        "message": "Event created successfully",
        "event_id": event.event_id
    }


@router.get("/")
def get_events(
    current_user: dict = Depends(get_current_user)
):
    events = list(events_collection.find())

    for event in events:
        event["_id"] = str(event["_id"])

    return events


@router.get("/protected")
def protected_test(
    current_user: dict = Depends(get_current_user)
):
    return {
        "message": "Authentication successful",
        "user": current_user
    }


@router.get("/admin-test")
def admin_test(
    current_user: dict = Depends(require_role(["admin"]))
):
    return {
        "message": "Admin access successful",
        "user": current_user
    }
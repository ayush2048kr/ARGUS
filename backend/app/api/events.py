from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_current_user, require_role
from app.models.event import Event
from app.services.event_service import (
    create_event,
    get_event_by_id,
    get_all_events,
    get_events_for_user,
)


router = APIRouter(
    prefix="/events",
    tags=["Events"]
)


@router.post("/")
def create_new_event(
    event: Event,
    current_user: dict = Depends(get_current_user)
):
    event_data = create_event(event.model_dump())

    return {
        "message": "Event created successfully",
        "event_id": event_data["event_id"]
    }


@router.get("/")
def list_events(
    current_user: dict = Depends(require_role(["admin", "analyst"]))
):
    return get_all_events()


@router.get("/user/{user_id}")
def list_user_events(
    user_id: str,
    current_user: dict = Depends(require_role(["admin", "analyst"]))
):
    return get_events_for_user(user_id)


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


@router.get("/{event_id}")
def get_event(
    event_id: str,
    current_user: dict = Depends(require_role(["admin", "analyst"]))
):
    event = get_event_by_id(event_id)

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )

    return event
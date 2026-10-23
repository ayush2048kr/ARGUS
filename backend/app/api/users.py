from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_current_user, require_role
from app.models.user import User
from app.services.user_service import (
    get_user_by_id,
    get_all_users,
    deactivate_user,
)


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


@router.get("/me")
def get_my_profile(
    current_user: dict = Depends(get_current_user)
):
    user = get_user_by_id(current_user["user_id"])

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


@router.get("/")
def list_users(
    current_user: dict = Depends(require_role(["admin"]))
):
    return get_all_users()


@router.get("/{user_id}")
def get_user(
    user_id: str,
    current_user: dict = Depends(require_role(["admin"]))
):
    user = get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


@router.patch("/{user_id}/deactivate")
def deactivate(
    user_id: str,
    current_user: dict = Depends(require_role(["admin"]))
):
    success = deactivate_user(user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or already inactive"
        )

    return {
        "message": "User deactivated successfully",
        "user_id": user_id
    }
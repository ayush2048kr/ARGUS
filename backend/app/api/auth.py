from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database.mongodb import users_collection
from app.auth.password import hash_password, verify_password
from app.auth.jwt import create_access_token


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


# =========================
# REQUEST MODELS
# =========================

class RegisterRequest(BaseModel):
    user_id: str
    password: str
    role: str = "analyst"


class LoginRequest(BaseModel):
    user_id: str
    password: str


# =========================
# REGISTER
# =========================

@router.post("/register")
def register_user(data: RegisterRequest):

    existing_user = users_collection.find_one(
        {"user_id": data.user_id}
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="User already exists"
        )

    user = {
        "user_id": data.user_id,
        "password": hash_password(data.password),
        "role": data.role,
        "is_active": True
    }

    users_collection.insert_one(user)

    return {
        "message": "User registered successfully",
        "user_id": data.user_id,
        "role": data.role
    }


# =========================
# LOGIN
# =========================

@router.post("/login")
def login_user(data: LoginRequest):

    user = users_collection.find_one(
        {"user_id": data.user_id}
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid user ID or password"
        )

    if not verify_password(
        data.password,
        user["password"]
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid user ID or password"
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=403,
            detail="User account is inactive"
        )

    token = create_access_token(
        user_id=user["user_id"],
        role=user.get("role", "analyst")
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user["user_id"],
        "role": user.get("role", "analyst")
    }
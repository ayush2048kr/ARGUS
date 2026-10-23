
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from pymongo.errors import DuplicateKeyError

from app.database.mongodb import users_collection
from app.auth.password import hash_password, verify_password
from app.auth.jwt import create_access_token


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


class RegisterRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("User ID cannot be empty")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Password cannot be empty or whitespace")
        return value


class LoginRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("User ID cannot be empty")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Password cannot be empty or whitespace")
        return value


@router.post("/register")
def register_user(data: RegisterRequest):
    existing_user = users_collection.find_one(
        {"user_id": data.user_id}
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="User already exists",
        )

    user = {
        "user_id": data.user_id,
        "password": hash_password(data.password),
        "role": "analyst",
        "is_active": True,
    }

    try:
        users_collection.insert_one(user)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail="User already exists",
        )

    return {
        "message": "User registered successfully",
        "user_id": data.user_id,
        "role": "analyst",
    }


@router.post("/login")
def login_user(data: LoginRequest):
    user = users_collection.find_one(
        {"user_id": data.user_id}
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid user ID or password",
        )

    if not verify_password(data.password, user["password"]):
        raise HTTPException(
            status_code=401,
            detail="Invalid user ID or password",
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=403,
            detail="User account is inactive",
        )

    token = create_access_token(
        user_id=user["user_id"],
        role=user.get("role", "analyst"),
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user["user_id"],
        "role": user.get("role", "analyst"),
    }

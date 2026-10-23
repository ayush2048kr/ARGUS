
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth.jwt import create_access_token, decode_access_token
from app.auth.password import hash_password, verify_password
from app.database.mongodb import users_collection


client = TestClient(app)


@pytest.fixture
def test_user_id():
    """Create a unique test user ID and clean up its database record."""
    user_id = f"TEST_AUTH_{uuid.uuid4().hex[:12]}"

    yield user_id

    users_collection.delete_one({"user_id": user_id})


def test_create_and_decode_access_token():
    token = create_access_token(
        user_id="EMP001",
        role="analyst",
    )

    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "EMP001"
    assert payload["role"] == "analyst"


def test_invalid_access_token():
    payload = decode_access_token("invalid-token")

    assert payload is None


def test_register_user_success(test_user_id):
    password = "StrongTestPass123!"

    response = client.post(
        "/auth/register",
        json={
            "user_id": test_user_id,
            "password": password,
        },
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == test_user_id
    assert response.json()["role"] == "analyst"
    assert "password" not in response.json()
    assert "access_token" not in response.json()

    stored_user = users_collection.find_one(
        {"user_id": test_user_id}
    )

    assert stored_user is not None
    assert stored_user["password"] != password
    assert verify_password(password, stored_user["password"])


def test_register_duplicate_user_returns_conflict(test_user_id):
    users_collection.insert_one(
        {
            "user_id": test_user_id,
            "password": hash_password("ExistingPassword123!"),
            "role": "analyst",
            "is_active": True,
        }
    )

    response = client.post(
        "/auth/register",
        json={
            "user_id": test_user_id,
            "password": "AnotherStrongPass123!",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "User already exists"


def test_login_success(test_user_id):
    password = "StrongTestPass123!"

    registration = client.post(
        "/auth/register",
        json={
            "user_id": test_user_id,
            "password": password,
        },
    )

    assert registration.status_code == 200

    response = client.post(
        "/auth/login",
        json={
            "user_id": test_user_id,
            "password": password,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["token_type"] == "bearer"
    assert body["user_id"] == test_user_id
    assert body["role"] == "analyst"
    assert "access_token" in body

    payload = decode_access_token(body["access_token"])

    assert payload is not None
    assert payload["sub"] == test_user_id
    assert payload["role"] == "analyst"


def test_login_unknown_user_returns_401():
    user_id = f"UNKNOWN_AUTH_{uuid.uuid4().hex[:12]}"

    response = client.post(
        "/auth/login",
        json={
            "user_id": user_id,
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid user ID or password"
    )


def test_login_wrong_password_returns_401(test_user_id):
    users_collection.insert_one(
        {
            "user_id": test_user_id,
            "password": hash_password("CorrectPassword123!"),
            "role": "analyst",
            "is_active": True,
        }
    )

    response = client.post(
        "/auth/login",
        json={
            "user_id": test_user_id,
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid user ID or password"
    )


def test_inactive_user_login_returns_403(test_user_id):
    users_collection.insert_one(
        {
            "user_id": test_user_id,
            "password": hash_password("StrongTestPass123!"),
            "role": "analyst",
            "is_active": False,
        }
    )

    response = client.post(
        "/auth/login",
        json={
            "user_id": test_user_id,
            "password": "StrongTestPass123!",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "User account is inactive"


@pytest.mark.parametrize(
    "payload",
    [
        {"user_id": "", "password": "StrongTestPass123!"},
        {"user_id": "   ", "password": "StrongTestPass123!"},
        {"user_id": "EMP_VALID", "password": ""},
        {"user_id": "EMP_VALID", "password": "   "},
        {"user_id": "U" * 65, "password": "StrongTestPass123!"},
        {"user_id": "EMP_VALID", "password": "P" * 129},
    ],
)
def test_register_rejects_invalid_input(payload):
    response = client.post(
        "/auth/register",
        json=payload,
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"user_id": "", "password": "StrongTestPass123!"},
        {"user_id": "EMP_VALID", "password": ""},
        {"user_id": "EMP_VALID", "password": "   "},
        {"user_id": "U" * 65, "password": "StrongTestPass123!"},
        {"user_id": "EMP_VALID", "password": "P" * 129},
    ],
)
def test_login_rejects_invalid_input(payload):
    response = client.post(
        "/auth/login",
        json=payload,
    )

    assert response.status_code == 422

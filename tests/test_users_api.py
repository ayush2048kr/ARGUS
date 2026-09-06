import os

from fastapi.testclient import TestClient

from app.main import app
from app.database.mongodb import users_collection
from app.auth.password import hash_password
from app.auth.jwt import create_access_token


client = TestClient(app)

TEST_USER_ID = "TEST_EMP_API"
TEST_ADMIN_ID = "TEST_ADMIN_API"


def setup_module():
    users_collection.delete_many(
        {
            "user_id": {
                "$in": [TEST_USER_ID, TEST_ADMIN_ID]
            }
        }
    )

    users_collection.insert_many(
        [
            {
                "user_id": TEST_USER_ID,
                "password": hash_password("TestPassword123!"),
                "role": "analyst",
                "is_active": True
            },
            {
                "user_id": TEST_ADMIN_ID,
                "password": hash_password("AdminPassword123!"),
                "role": "admin",
                "is_active": True
            }
        ]
    )


def teardown_module():
    users_collection.delete_many(
        {
            "user_id": {
                "$in": [TEST_USER_ID, TEST_ADMIN_ID]
            }
        }
    )


def test_get_my_profile():
    token = create_access_token(
        TEST_USER_ID,
        "analyst"
    )

    response = client.get(
        "/users/me",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["user_id"] == TEST_USER_ID
    assert data["role"] == "analyst"
    assert data["is_active"] is True
    assert "password" not in data
    assert "_id" not in data


def test_get_my_profile_without_token():
    response = client.get("/users/me")

    assert response.status_code == 401


def test_analyst_cannot_list_users():
    token = create_access_token(
        TEST_USER_ID,
        "analyst"
    )

    response = client.get(
        "/users/",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 403


def test_admin_can_list_users():
    token = create_access_token(
        TEST_ADMIN_ID,
        "admin"
    )

    response = client.get(
        "/users/",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    user_ids = [
        user["user_id"]
        for user in response.json()
    ]

    assert TEST_USER_ID in user_ids
    assert TEST_ADMIN_ID in user_ids


def test_admin_can_get_user():
    token = create_access_token(
        TEST_ADMIN_ID,
        "admin"
    )

    response = client.get(
        f"/users/{TEST_USER_ID}",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == TEST_USER_ID


def test_admin_get_missing_user():
    token = create_access_token(
        TEST_ADMIN_ID,
        "admin"
    )

    response = client.get(
        "/users/DOES_NOT_EXIST",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 404


def test_admin_can_deactivate_user():
    token = create_access_token(
        TEST_ADMIN_ID,
        "admin"
    )

    response = client.patch(
        f"/users/{TEST_USER_ID}/deactivate",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    user = users_collection.find_one(
        {"user_id": TEST_USER_ID}
    )

    assert user["is_active"] is False

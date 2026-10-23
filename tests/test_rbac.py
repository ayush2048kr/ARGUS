
import pytest
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.database.mongodb import users_collection
from app.main import app

client = TestClient(app)


@pytest.fixture
def test_user():
    """Create test users and remove them after each test."""
    created_user_ids = []

    def create_user(
        user_id: str,
        role: str,
        is_active: bool = True,
    ):
        users_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "role": role,
                    "is_active": is_active,
                }
            },
            upsert=True,
        )
        created_user_ids.append(user_id)

    yield create_user

    users_collection.delete_many(
        {"user_id": {"$in": created_user_ids}}
    )


def test_analyst_can_access_protected_endpoint(test_user):
    user_id = "RBAC_TEST_ANALYST"
    test_user(user_id, "analyst")

    token = create_access_token(user_id=user_id, role="analyst")
    response = client.get(
        "/events/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["user_id"] == user_id
    assert response.json()["user"]["role"] == "analyst"


def test_analyst_cannot_access_admin_endpoint(test_user):
    user_id = "RBAC_TEST_ANALYST_ADMIN"
    test_user(user_id, "analyst")

    token = create_access_token(user_id=user_id, role="analyst")
    response = client.get(
        "/events/admin-test",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_admin_can_access_admin_endpoint(test_user):
    user_id = "RBAC_TEST_ADMIN"
    test_user(user_id, "admin")

    token = create_access_token(user_id=user_id, role="admin")
    response = client.get(
        "/events/admin-test",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["user_id"] == user_id
    assert response.json()["user"]["role"] == "admin"


def test_missing_token_is_rejected():
    response = client.get("/events/protected")

    assert response.status_code == 401


def test_deactivated_user_cannot_use_existing_token(test_user):
    user_id = "RBAC_TEST_DEACTIVATED"
    test_user(user_id, "analyst", is_active=True)

    # Issue the token while the account is active.
    token = create_access_token(user_id=user_id, role="analyst")

    # Deactivate the account after issuing the token.
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"is_active": False}},
    )

    response = client.get(
        "/events/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_deleted_user_cannot_use_existing_token(test_user):
    user_id = "RBAC_TEST_DELETED"
    test_user(user_id, "analyst")

    token = create_access_token(user_id=user_id, role="analyst")

    users_collection.delete_one({"user_id": user_id})

    response = client.get(
        "/events/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_role_change_takes_effect_for_existing_token(test_user):
    user_id = "RBAC_TEST_ROLE_CHANGE"
    test_user(user_id, "admin")

    # The token contains the old admin role.
    token = create_access_token(user_id=user_id, role="admin")

    # Change the user's role in the database.
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"role": "analyst"}},
    )

    response = client.get(
        "/events/admin-test",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403

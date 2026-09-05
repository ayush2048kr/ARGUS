from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.main import app


client = TestClient(app)


def test_analyst_can_access_protected_endpoint():
    token = create_access_token(
        user_id="EMP001",
        role="analyst"
    )

    response = client.get(
        "/events/protected",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["user"]["user_id"] == "EMP001"
    assert response.json()["user"]["role"] == "analyst"


def test_analyst_cannot_access_admin_endpoint():
    token = create_access_token(
        user_id="EMP001",
        role="analyst"
    )

    response = client.get(
        "/events/admin-test",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_admin_can_access_admin_endpoint():
    token = create_access_token(
        user_id="EMP002",
        role="admin"
    )

    response = client.get(
        "/events/admin-test",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["user"]["user_id"] == "EMP002"
    assert response.json()["user"]["role"] == "admin"


def test_missing_token_is_rejected():
    response = client.get("/events/protected")

    assert response.status_code == 401

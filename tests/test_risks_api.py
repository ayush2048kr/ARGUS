from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.database.mongodb import db
from app.auth.jwt import create_access_token

client = TestClient(app)

risks_collection = db["risks"]

TEST_USER_ID = "TEST_EMP_RISK"
TEST_RISK_ID = "TEST_RISK_API"

TEST_RISK = {
    "risk_id": TEST_RISK_ID,
    "user_id": TEST_USER_ID,
    "event_id": "TEST_EVT_RISK",
    "risk_score": 75.5,
    "severity": "HIGH",
    "behavior_deviation_score": 80.0,
    "peer_deviation_score": 70.0,
    "context_risk_score": 65.0,
    "activity_severity": 75.0,
    "evidence": [
        "Behavior deviation score is elevated",
        "Sensitive resource accessed"
    ],
    "reason": "Unusual sensitive resource access",
    "created_at": "2026-09-07T10:30:00"
}


def setup_module():
    risks_collection.delete_many({"risk_id": TEST_RISK_ID})


def teardown_module():
    risks_collection.delete_many({"risk_id": TEST_RISK_ID})


def get_analyst_token():
    return create_access_token(TEST_USER_ID, "analyst")


def test_create_risk():
    token = get_analyst_token()

    response = client.post(
        "/risks/",
        json=TEST_RISK,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200

    data = response.json()

    assert data["risk_id"] == TEST_RISK_ID
    assert data["user_id"] == TEST_USER_ID
    assert data["risk_score"] == 75.5
    assert data["severity"] == "HIGH"
    assert "_id" not in data


def test_risk_persisted_in_mongodb():
    saved_risk = risks_collection.find_one(
        {"risk_id": TEST_RISK_ID},
        {"_id": 0}
    )

    assert saved_risk is not None
    assert saved_risk["risk_id"] == TEST_RISK_ID
    assert saved_risk["risk_score"] == 75.5
    assert saved_risk["severity"] == "HIGH"
    assert saved_risk["created_at"] == datetime.fromisoformat(
        TEST_RISK["created_at"]
    )


def test_get_risk():
    token = get_analyst_token()

    response = client.get(
        f"/risks/{TEST_RISK_ID}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200

    data = response.json()

    assert data["risk_id"] == TEST_RISK_ID
    assert data["reason"] == TEST_RISK["reason"]


def test_list_risks():
    token = get_analyst_token()

    response = client.get(
        "/risks/",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200

    risk_ids = [risk["risk_id"] for risk in response.json()]

    assert TEST_RISK_ID in risk_ids


def test_list_user_risks():
    token = get_analyst_token()

    response = client.get(
        f"/risks/user/{TEST_USER_ID}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200

    risk_ids = [risk["risk_id"] for risk in response.json()]

    assert TEST_RISK_ID in risk_ids


def test_missing_risk():
    token = get_analyst_token()

    response = client.get(
        "/risks/DOES_NOT_EXIST",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


def test_create_risk_without_token():
    response = client.post(
        "/risks/",
        json=TEST_RISK
    )

    assert response.status_code == 401


def test_get_risk_without_token():
    response = client.get(
        f"/risks/{TEST_RISK_ID}"
    )

    assert response.status_code == 401

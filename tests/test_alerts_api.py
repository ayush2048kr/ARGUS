from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.database.mongodb import alerts_collection
from app.auth.jwt import create_access_token


client = TestClient(app)

TEST_USER_ID = "TEST_EMP_ALERTS"
TEST_ALERT_ID = "TEST_ALERT_API"


TEST_ALERT = {
    "alert_id": TEST_ALERT_ID,
    "user_id": TEST_USER_ID,
    "event_id": "TEST_EVT_ALERT",
    "risk_score": 75.5,
    "severity": "HIGH",
    "reason": "Unusual sensitive resource access",
    "evidence": [
        "Behavior deviation score is elevated",
        "Sensitive resource accessed"
    ],
    "status": "open",
    "created_at": "2026-09-07T10:30:00"
}


def setup_module():
    alerts_collection.delete_many(
        {"alert_id": TEST_ALERT_ID}
    )


def teardown_module():
    alerts_collection.delete_many(
        {"alert_id": TEST_ALERT_ID}
    )


def get_analyst_token():
    return create_access_token(
        TEST_USER_ID,
        "analyst"
    )


def test_create_alert():
    token = get_analyst_token()

    response = client.post(
        "/alerts/",
        json=TEST_ALERT,
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["alert_id"] == TEST_ALERT_ID
    assert data["user_id"] == TEST_USER_ID
    assert data["status"] == "open"


def test_alert_persisted_in_mongodb():
    saved_alert = alerts_collection.find_one(
        {"alert_id": TEST_ALERT_ID},
        {"_id": 0}
    )

    assert saved_alert is not None
    assert saved_alert["alert_id"] == TEST_ALERT_ID
    assert saved_alert["risk_score"] == 75.5
    assert saved_alert["severity"] == "HIGH"
    assert saved_alert["status"] == "open"

    assert saved_alert["created_at"] == datetime.fromisoformat(
        TEST_ALERT["created_at"]
    )


def test_get_alert():
    token = get_analyst_token()

    response = client.get(
        f"/alerts/{TEST_ALERT_ID}",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["alert_id"] == TEST_ALERT_ID
    assert data["reason"] == TEST_ALERT["reason"]


def test_list_alerts():
    token = get_analyst_token()

    response = client.get(
        "/alerts/",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    alert_ids = [
        alert["alert_id"]
        for alert in response.json()
    ]

    assert TEST_ALERT_ID in alert_ids


def test_update_alert_status():
    token = get_analyst_token()

    response = client.patch(
        f"/alerts/{TEST_ALERT_ID}/status",
        params={
            "new_status": "investigating"
        },
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "investigating"

    saved_alert = alerts_collection.find_one(
        {"alert_id": TEST_ALERT_ID}
    )

    assert saved_alert["status"] == "investigating"


def test_invalid_alert_status_rejected():
    token = get_analyst_token()

    response = client.patch(
        f"/alerts/{TEST_ALERT_ID}/status",
        params={
            "new_status": "invalid_status"
        },
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 422


def test_missing_alert():
    token = get_analyst_token()

    response = client.get(
        "/alerts/DOES_NOT_EXIST",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 404


def test_create_alert_without_token():
    response = client.post(
        "/alerts/",
        json=TEST_ALERT
    )

    assert response.status_code == 401

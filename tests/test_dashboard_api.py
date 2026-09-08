from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.database.mongodb import (
    users_collection,
    events_collection,
    alerts_collection,
)
from app.main import app


client = TestClient(app)

TEST_USER_ID = "TEST_EMP_DASHBOARD"
TEST_EVENT_ID = "TEST_EVT_DASHBOARD"
TEST_ALERT_PREFIX = "TEST_ALERT_DASHBOARD"


def setup_module():
    users_collection.delete_many(
        {"user_id": TEST_USER_ID}
    )

    events_collection.delete_many(
        {"event_id": TEST_EVENT_ID}
    )

    alerts_collection.delete_many(
        {"alert_id": {"$regex": f"^{TEST_ALERT_PREFIX}"}}
    )

    users_collection.insert_one({
        "user_id": TEST_USER_ID,
        "password": "test-password-hash",
        "role": "analyst",
        "is_active": True,
    })

    events_collection.insert_one({
        "event_id": TEST_EVENT_ID,
        "user_id": TEST_USER_ID,
        "timestamp": "2026-09-07T10:30:00",
    })

    alerts_collection.insert_many([
        {
            "alert_id": f"{TEST_ALERT_PREFIX}_CRITICAL",
            "severity": "CRITICAL",
        },
        {
            "alert_id": f"{TEST_ALERT_PREFIX}_HIGH",
            "severity": "HIGH",
        },
        {
            "alert_id": f"{TEST_ALERT_PREFIX}_HIGH_2",
            "severity": "HIGH",
        },
        {
            "alert_id": f"{TEST_ALERT_PREFIX}_MEDIUM",
            "severity": "MEDIUM",
        },
        {
            "alert_id": f"{TEST_ALERT_PREFIX}_LOW",
            "severity": "LOW",
        },
    ])


def teardown_module():
    users_collection.delete_many(
        {"user_id": TEST_USER_ID}
    )

    events_collection.delete_many(
        {"event_id": TEST_EVENT_ID}
    )

    alerts_collection.delete_many(
        {"alert_id": {"$regex": f"^{TEST_ALERT_PREFIX}"}}
    )


def get_analyst_token():
    return create_access_token(
        TEST_USER_ID,
        "analyst"
    )


def test_dashboard_summary():
    token = get_analyst_token()

    response = client.get(
        "/dashboard/summary",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200

    data = response.json()

    assert "total_users" in data
    assert "total_events" in data
    assert "total_alerts" in data
    assert "alerts_by_severity" in data


def test_dashboard_counts():
    token = get_analyst_token()

    response = client.get(
        "/dashboard/summary",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_users"] >= 1
    assert data["total_events"] >= 1
    assert data["total_alerts"] >= 5


def test_dashboard_alert_severity_counts():
    token = get_analyst_token()

    response = client.get(
        "/dashboard/summary",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200

    severity = response.json()["alerts_by_severity"]

    assert severity["critical"] >= 1
    assert severity["high"] >= 2
    assert severity["medium"] >= 1
    assert severity["low"] >= 1


def test_dashboard_without_token():
    response = client.get(
        "/dashboard/summary"
    )

    assert response.status_code == 401

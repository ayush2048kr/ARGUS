from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.database.mongodb import events_collection
from app.auth.jwt import create_access_token

client = TestClient(app)

TEST_USER_ID = "TEST_EMP_EVENTS"
TEST_EVENT_ID = "TEST_EVT_API"


TEST_EVENT = {
    "event_id": TEST_EVENT_ID,
    "user_id": TEST_USER_ID,
    "timestamp": "2026-09-07T10:30:00",
    "source": "CERT",
    "event_type": "file",
    "action": "download",
    "resource": "test_document.pdf",
    "resource_sensitivity": "high",
    "source_ip": "192.168.1.100",
    "destination": "internal-server",
    "device_id": "TEST_DEV_001",
    "location": "Office",
    "role": "analyst",
    "department": "IT",
    "work_schedule": "09:00-18:00",
    "access_level": "standard",
    "is_external": False
}


def setup_module():
    events_collection.delete_many(
        {"event_id": TEST_EVENT_ID}
    )


def teardown_module():
    events_collection.delete_many(
        {"event_id": TEST_EVENT_ID}
    )


def get_analyst_token():
    return create_access_token(
        TEST_USER_ID,
        "analyst"
    )


def test_create_event():
    token = get_analyst_token()

    response = client.post(
        "/events/",
        json=TEST_EVENT,
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == "Event created successfully"
    assert data["event_id"] == TEST_EVENT_ID


def test_event_persisted_in_mongodb():
    saved_event = events_collection.find_one(
        {"event_id": TEST_EVENT_ID},
        {"_id": 0}
    )



def test_get_event():
    token = get_analyst_token()

    response = client.get(
        f"/events/{TEST_EVENT_ID}",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200
    assert response.json() == TEST_EVENT


def test_get_events_for_user():
    token = get_analyst_token()

    response = client.get(
        f"/events/user/{TEST_USER_ID}",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    events = response.json()

    assert any(
        event["event_id"] == TEST_EVENT_ID
        for event in events
    )


def test_missing_event():
    token = get_analyst_token()

    response = client.get(
        "/events/DOES_NOT_EXIST",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 404


def test_create_event_without_token():
    response = client.post(
        "/events/",
        json=TEST_EVENT
    )

    assert response.status_code == 401


def test_invalid_event_rejected():
    token = get_analyst_token()

    invalid_event = TEST_EVENT.copy()
    invalid_event["is_external"] = "not-a-boolean"

    response = client.post(
        "/events/",
        json=invalid_event,
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 422

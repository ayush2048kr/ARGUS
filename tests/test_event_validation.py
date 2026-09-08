from datetime import datetime

from app.models.event import Event

from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.main import app


client = TestClient(app)


def test_event_missing_required_field_is_rejected():
    token = create_access_token(
        user_id="EMP001",
        role="analyst"
    )

    event = {
        "event_id": "EVT001",
        "user_id": "EMP001",
        "timestamp": "2026-09-05T10:30:00",
        "source": "CERT",
        "event_type": "file",
        "action": "download",
        "resource": "document.pdf",
        "resource_sensitivity": "high",
        "source_ip": "192.168.1.10",
        "destination": "internal-server",
        "device_id": "DEV001",
        "location": "Office",
        "role": "analyst",
        "department": "IT",
        "work_schedule": "09:00-18:00",
        "access_level": "standard",
        # is_external is intentionally missing
    }

    response = client.post(
        "/events/",
        json=event,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 422
def test_event_invalid_timestamp_is_rejected():
    token = create_access_token(
        user_id="EMP001",
        role="analyst"
    )

    event = {
        "event_id": "EVT002",
        "user_id": "EMP001",
        "timestamp": "not-a-timestamp",
        "source": "CERT",
        "event_type": "file",
        "action": "download",
        "resource": "document.pdf",
        "resource_sensitivity": "high",
        "source_ip": "192.168.1.10",
        "destination": "internal-server",
        "device_id": "DEV001",
        "location": "Office",
        "role": "analyst",
        "department": "IT",
        "work_schedule": "09:00-18:00",
        "access_level": "standard",
        "is_external": False
    }

    response = client.post(
        "/events/",
        json=event,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 422
def test_event_invalid_boolean_is_rejected():
    token = create_access_token(
        user_id="EMP001",
        role="analyst"
    )

    event = {
        "event_id": "EVT003",
        "user_id": "EMP001",
        "timestamp": "2026-09-05T10:30:00",
        "source": "CERT",
        "event_type": "file",
        "action": "download",
        "resource": "document.pdf",
        "resource_sensitivity": "high",
        "source_ip": "192.168.1.10",
        "destination": "internal-server",
        "device_id": "DEV001",
        "location": "Office",
        "role": "analyst",
        "department": "IT",
        "work_schedule": "09:00-18:00",
        "access_level": "standard",
        "is_external": "definitely-not-a-boolean"
    }

    response = client.post(
        "/events/",
        json=event,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 422
def test_valid_event_schema_is_accepted():
    event = Event(
        event_id="EVT004",
        user_id="EMP001",
        timestamp=datetime.fromisoformat("2026-09-05T10:30:00"),
        source="CERT",
        event_type="file",
        action="download",
        resource="document.pdf",
        resource_sensitivity="high",
        source_ip="192.168.1.10",
        destination="internal-server",
        device_id="DEV001",
        location="Office",
        role="analyst",
        department="IT",
        work_schedule="09:00-18:00",
        access_level="standard",
        is_external=False,
    )

    assert event.event_id == "EVT004"
    assert event.user_id == "EMP001"
    assert event.is_external is False
    assert event.timestamp == datetime.fromisoformat(
        "2026-09-05T10:30:00"
    )
def test_event_with_nullable_context_fields_is_accepted():
    event = Event(
        event_id="ARG-RAW-001",
        user_id="EMP001",
        timestamp=datetime.fromisoformat("2026-09-05T10:30:00"),
        source="DEVICE",
        event_type="DEVICE_ACTIVITY",
        action="Connect",
        resource=None,
        resource_sensitivity=None,
        source_ip=None,
        destination=None,
        device_id="PC001",
        location=None,
        role=None,
        department=None,
        work_schedule=None,
        access_level=None,
        is_external=None,
    )

    assert event.event_id == "ARG-RAW-001"
    assert event.user_id == "EMP001"
    assert event.device_id == "PC001"
    assert event.resource is None
    assert event.role is None
    assert event.is_external is None 


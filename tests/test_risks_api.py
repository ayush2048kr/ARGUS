
from datetime import datetime

import pytest
from pymongo.errors import DuplicateKeyError
from fastapi.testclient import TestClient

from app.main import app
from app.database.mongodb import alerts_collection, db, users_collection
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
        "Sensitive resource accessed",
    ],
    "reason": "Unusual sensitive resource access",
    "created_at": "2026-09-07T10:30:00",
}

TEST_RISK_IDS = [
    TEST_RISK_ID,
    "TEST_RISK_INVALID_HIGH",
    "TEST_RISK_INVALID_LOW",
    "TEST_RISK_SEVERITY_UNKNOWN",
    "TEST_RISK_SEVERITY_critical",
    "TEST_RISK_SEVERITY_EMPTY",
    "TEST_RISK_EMPTY_EVIDENCE",
    "TEST_RISK_EMPTY_REASON",
    "TEST_RISK_MEDIUM_NO_ALERT",
    "TEST_RISK_LOW_NO_ALERT",
    "TEST_RISK_AUTO_HIGH",
    "TEST_RISK_AUTO_CRITICAL",
    "TEST_RISK_AUTO_DUPLICATE",
    "TEST_BOUNDARY_0",
    "TEST_BOUNDARY_30",
    "TEST_BOUNDARY_30_1",
    "TEST_BOUNDARY_60",
    "TEST_BOUNDARY_60_1",
    "TEST_BOUNDARY_80",
    "TEST_BOUNDARY_80_1",
    "TEST_BOUNDARY_100",
]


def setup_module():
    users_collection.update_one(
        {"user_id": TEST_USER_ID},
        {
            "$set": {
                "user_id": TEST_USER_ID,
                "role": "analyst",
                "is_active": True,
            }
        },
        upsert=True,
    )

    risks_collection.delete_many(
        {"risk_id": {"$in": TEST_RISK_IDS}}
    )

    alerts_collection.delete_many(
        {"risk_id": {"$in": TEST_RISK_IDS}}
    )


def teardown_module():
    risks_collection.delete_many(
        {"risk_id": {"$in": TEST_RISK_IDS}}
    )

    alerts_collection.delete_many(
        {"risk_id": {"$in": TEST_RISK_IDS}}
    )

    users_collection.delete_one({"user_id": TEST_USER_ID})


def get_analyst_token():
    return create_access_token(TEST_USER_ID, "analyst")


def test_create_risk():
    token = get_analyst_token()

    response = client.post(
        "/risks/",
        json=TEST_RISK,
        headers={"Authorization": f"Bearer {token}"},
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
        {"_id": 0},
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
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["risk_id"] == TEST_RISK_ID
    assert data["reason"] == TEST_RISK["reason"]


def test_list_risks():
    token = get_analyst_token()

    response = client.get(
        "/risks/",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert any(
        risk["risk_id"] == TEST_RISK_ID
        for risk in response.json()
    )


def test_list_user_risks():
    token = get_analyst_token()

    response = client.get(
        f"/risks/user/{TEST_USER_ID}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert any(
        risk["risk_id"] == TEST_RISK_ID
        for risk in response.json()
    )


def test_missing_risk():
    token = get_analyst_token()

    response = client.get(
        "/risks/DOES_NOT_EXIST",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


def test_create_risk_without_token():
    response = client.post("/risks/", json=TEST_RISK)

    assert response.status_code == 401


def test_risk_score_above_100_is_rejected():
    token = get_analyst_token()

    invalid_risk = TEST_RISK.copy()
    invalid_risk["risk_id"] = "TEST_RISK_INVALID_HIGH"
    invalid_risk["risk_score"] = 101

    response = client.post(
        "/risks/",
        json=invalid_risk,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


def test_behavior_deviation_score_below_0_is_rejected():
    token = get_analyst_token()

    invalid_risk = TEST_RISK.copy()
    invalid_risk["risk_id"] = "TEST_RISK_INVALID_LOW"
    invalid_risk["behavior_deviation_score"] = -1

    response = client.post(
        "/risks/",
        json=invalid_risk,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize("severity", ["UNKNOWN", "critical", ""])
def test_invalid_risk_severity_is_rejected(severity):
    token = get_analyst_token()

    invalid_risk = TEST_RISK.copy()
    invalid_risk["risk_id"] = (
        f"TEST_RISK_SEVERITY_{severity or 'EMPTY'}"
    )
    invalid_risk["severity"] = severity

    response = client.post(
        "/risks/",
        json=invalid_risk,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


def test_empty_risk_evidence_is_rejected():
    token = get_analyst_token()

    invalid_risk = TEST_RISK.copy()
    invalid_risk["risk_id"] = "TEST_RISK_EMPTY_EVIDENCE"
    invalid_risk["evidence"] = []

    response = client.post(
        "/risks/",
        json=invalid_risk,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


def test_empty_risk_reason_is_rejected():
    token = get_analyst_token()

    invalid_risk = TEST_RISK.copy()
    invalid_risk["risk_id"] = "TEST_RISK_EMPTY_REASON"
    invalid_risk["reason"] = ""

    response = client.post(
        "/risks/",
        json=invalid_risk,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("severity", "risk_score", "risk_id"),
    [
        ("MEDIUM", 50.0, "TEST_RISK_MEDIUM_NO_ALERT"),
        ("LOW", 20.0, "TEST_RISK_LOW_NO_ALERT"),
    ],
)
def test_low_and_medium_risks_do_not_generate_alert(
    severity, risk_score, risk_id
):
    token = get_analyst_token()

    payload = {
        **TEST_RISK,
        "risk_id": risk_id,
        "severity": severity,
        "risk_score": risk_score,
    }

    response = client.post(
        "/risks/",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    saved_risk = risks_collection.find_one(
        {"risk_id": risk_id}
    )
    assert saved_risk is not None

    generated_alert = alerts_collection.find_one(
        {"risk_id": risk_id}
    )
    assert generated_alert is None


def test_high_risk_generates_explainable_alert():
    token = get_analyst_token()
    risk_id = "TEST_RISK_AUTO_HIGH"

    payload = {
        **TEST_RISK,
        "risk_id": risk_id,
    }

    response = client.post(
        "/risks/",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    generated_alert = alerts_collection.find_one(
        {"risk_id": risk_id},
        {"_id": 0},
    )

    assert generated_alert is not None
    assert generated_alert["alert_id"] == f"ALERT_{risk_id}"
    assert generated_alert["risk_id"] == risk_id
    assert generated_alert["user_id"] == payload["user_id"]
    assert generated_alert["event_id"] == payload["event_id"]
    assert generated_alert["risk_score"] == payload["risk_score"]
    assert generated_alert["severity"] == "HIGH"
    assert generated_alert["reason"] == payload["reason"]
    assert generated_alert["evidence"] == payload["evidence"]
    assert generated_alert["status"] == "open"


def test_critical_risk_generates_alert():
    token = get_analyst_token()
    risk_id = "TEST_RISK_AUTO_CRITICAL"

    payload = {
        **TEST_RISK,
        "risk_id": risk_id,
        "risk_score": 90.0,
        "severity": "CRITICAL",
    }

    response = client.post(
        "/risks/",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    generated_alert = alerts_collection.find_one(
        {"risk_id": risk_id},
        {"_id": 0},
    )

    assert generated_alert is not None
    assert generated_alert["alert_id"] == f"ALERT_{risk_id}"
    assert generated_alert["risk_id"] == risk_id
    assert generated_alert["severity"] == "CRITICAL"
    assert generated_alert["risk_score"] == 90.0
    assert generated_alert["evidence"] == payload["evidence"]


def test_duplicate_alert_for_same_risk_is_rejected():
    token = get_analyst_token()
    risk_id = "TEST_RISK_AUTO_DUPLICATE"

    payload = {
        **TEST_RISK,
        "risk_id": risk_id,
    }

    response = client.post(
        "/risks/",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    first_alert = alerts_collection.find_one(
        {"risk_id": risk_id}
    )
    assert first_alert is not None

    duplicate_alert = {
        **first_alert,
        "alert_id": f"ALERT_DUPLICATE_{risk_id}",
    }
    duplicate_alert.pop("_id", None)

    with pytest.raises(DuplicateKeyError):
        alerts_collection.insert_one(duplicate_alert)

    assert alerts_collection.count_documents(
        {"risk_id": risk_id}
    ) == 1


@pytest.mark.parametrize(
    ("risk_score", "severity"),
    [
        (0, "LOW"),
        (30, "LOW"),
        (30.1, "MEDIUM"),
        (60, "MEDIUM"),
        (60.1, "HIGH"),
        (80, "HIGH"),
        (80.1, "CRITICAL"),
        (100, "CRITICAL"),
    ],
)
def test_risk_score_severity_boundaries_are_valid(risk_score, severity):
    token = get_analyst_token()

    risk_id = f"TEST_BOUNDARY_{str(risk_score).replace('.', '_')}"

    payload = {
        **TEST_RISK,
        "risk_id": risk_id,
        "risk_score": risk_score,
        "severity": severity,
    }

    response = client.post(
        "/risks/",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["severity"] == severity


@pytest.mark.parametrize(
    ("risk_score", "severity"),
    [
        (90, "LOW"),
        (25, "MEDIUM"),
        (50, "HIGH"),
        (75, "CRITICAL"),
        (100, "HIGH"),
    ],
)
def test_inconsistent_risk_severity_is_rejected(risk_score, severity):
    token = get_analyst_token()

    payload = {
        **TEST_RISK,
        "risk_id": f"TEST_MISMATCH_{risk_score}_{severity}",
        "risk_score": risk_score,
        "severity": severity,
    }

    response = client.post(
        "/risks/",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422

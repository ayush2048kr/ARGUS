
from app.database.mongodb import db, alerts_collection
risks_collection = db["risks"]


def create_risk_assessment(risk_data: dict):
    risks_collection.insert_one(risk_data)

    saved_risk = risks_collection.find_one(
        {"risk_id": risk_data["risk_id"]},
        {"_id": 0},
    )

    if saved_risk and saved_risk["severity"] in {"HIGH", "CRITICAL"}:
        alert_data = {
            "alert_id": f"ALERT_{saved_risk['risk_id']}",
            "risk_id": saved_risk["risk_id"],
            "user_id": saved_risk["user_id"],
            "event_id": saved_risk["event_id"],
            "risk_score": saved_risk["risk_score"],
            "severity": saved_risk["severity"],
            "reason": saved_risk["reason"],
            "evidence": saved_risk["evidence"],
            "status": "open",
            "created_at": saved_risk["created_at"],
        }

        alerts_collection.update_one(
            {"risk_id": saved_risk["risk_id"]},
            {"$setOnInsert": alert_data},
            upsert=True,
        )

    return saved_risk


def get_risk_by_id(risk_id: str):
    return risks_collection.find_one(
        {"risk_id": risk_id},
        {"_id": 0},
    )


def get_risks_for_user(user_id: str):
    return list(
        risks_collection.find(
            {"user_id": user_id},
            {"_id": 0},
        )
    )


def get_all_risks():
    return list(
        risks_collection.find(
            {},
            {"_id": 0},
        )
    )

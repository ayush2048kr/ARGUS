from app.database.mongodb import db


risks_collection = db["risks"]


def create_risk_assessment(risk_data: dict):
    risks_collection.insert_one(risk_data)

    return risk_data


def get_risk_by_id(risk_id: str):
    return risks_collection.find_one(
        {"risk_id": risk_id},
        {"_id": 0}
    )


def get_risks_for_user(user_id: str):
    return list(
        risks_collection.find(
            {"user_id": user_id},
            {"_id": 0}
        )
    )


def get_all_risks():
    return list(
        risks_collection.find(
            {},
            {"_id": 0}
        )
    )





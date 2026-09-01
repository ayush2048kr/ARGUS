from app.database.mongodb import alerts_collection


def create_alert(alert_data: dict):
    alerts_collection.insert_one(alert_data)

    return alert_data


def get_alert_by_id(alert_id: str):
    return alerts_collection.find_one(
        {"alert_id": alert_id},
        {"_id": 0}
    )


def get_all_alerts():
    return list(
        alerts_collection.find(
            {},
            {"_id": 0}
        )
    )


def update_alert_status(alert_id: str, status: str) -> bool:
    result = alerts_collection.update_one(
        {"alert_id": alert_id},
        {"$set": {"status": status}}
    )

    return result.modified_count > 0
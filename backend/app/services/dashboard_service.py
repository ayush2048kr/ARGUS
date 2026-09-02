
from app.database.mongodb import db


events_collection = db["events"]
alerts_collection = db["alerts"]
users_collection = db["users"]


def get_dashboard_summary():
    total_users = users_collection.count_documents({})
    total_events = events_collection.count_documents({})
    total_alerts = alerts_collection.count_documents({})

    critical_alerts = alerts_collection.count_documents(
        {"severity": "CRITICAL"}
    )

    high_alerts = alerts_collection.count_documents(
        {"severity": "HIGH"}
    )

    medium_alerts = alerts_collection.count_documents(
        {"severity": "MEDIUM"}
    )

    low_alerts = alerts_collection.count_documents(
        {"severity": "LOW"}
    )

    return {
        "total_users": total_users,
        "total_events": total_events,
        "total_alerts": total_alerts,
        "alerts_by_severity": {
            "critical": critical_alerts,
            "high": high_alerts,
            "medium": medium_alerts,
            "low": low_alerts,
        },
    }

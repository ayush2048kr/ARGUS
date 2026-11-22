
from datetime import datetime, timezone

from pymongo import UpdateOne

from app.database.mongodb import daily_risks_collection


def upsert_daily_risks(records: list[dict]) -> dict:
    operations = []

    for record in records:
        document = dict(record)
        document["date"] = document["date"].isoformat()

        now = datetime.now(timezone.utc)

        operations.append(
            UpdateOne(
                {
                    "user_id": document["user_id"],
                    "date": document["date"],
                },
                {
                    "$set": {
                        **document,
                        "updated_at": now,
                    },
                    "$setOnInsert": {
                        "created_at": now,
                    },
                },
                upsert=True,
            )
        )

    if not operations:
        return {"received": 0, "inserted": 0, "modified": 0}

    result = daily_risks_collection.bulk_write(
        operations,
        ordered=True,
    )

    return {
        "received": len(records),
        "inserted": result.upserted_count,
        "modified": result.modified_count,
    }


def get_daily_risks(
    user_id=None,
    date_value=None,
    risk_level=None,
    limit=500,
):
    query = {}

    if user_id:
        query["user_id"] = user_id

    if date_value:
        query["date"] = date_value

    if risk_level:
        query["risk_level"] = risk_level

    return list(
        daily_risks_collection.find(query, {"_id": 0})
        .sort([("date", -1), ("risk_score", -1)])
        .limit(limit)
    )


def get_daily_risks_for_user(user_id):
    return get_daily_risks(user_id=user_id)


def get_latest_daily_risks(limit=5000):
    pipeline = [
        {"$sort": {"user_id": 1, "date": -1}},
        {
            "$group": {
                "_id": "$user_id",
                "record": {"$first": "$$ROOT"},
            }
        },
        {"$replaceRoot": {"newRoot": "$record"}},
        {"$sort": {"risk_score": -1}},
        {"$limit": limit},
        {"$project": {"_id": 0}},
    ]

    return list(daily_risks_collection.aggregate(pipeline))

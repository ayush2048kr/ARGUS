from app.database.mongodb import events_collection


def create_event(event_data: dict):
    events_collection.insert_one(event_data)

    return event_data


def get_event_by_id(event_id: str):
    return events_collection.find_one(
        {"event_id": event_id},
        {"_id": 0}
    )


def get_all_events():
    return list(
        events_collection.find(
            {},
            {"_id": 0}
        )
    )


def get_events_for_user(user_id: str):
    return list(
        events_collection.find(
            {"user_id": user_id},
            {"_id": 0}
        )
    )
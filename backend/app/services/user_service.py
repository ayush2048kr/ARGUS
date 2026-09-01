from app.database.mongodb import users_collection


def get_user_by_id(user_id: str):
    return users_collection.find_one(
        {"user_id": user_id},
        {"_id": 0, "password": 0}
    )


def get_all_users():
    users = list(
        users_collection.find(
            {},
            {"_id": 0, "password": 0}
        )
    )

    return users


def deactivate_user(user_id: str) -> bool:
    result = users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"is_active": False}}
    )

    return result.modified_count > 0
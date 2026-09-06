import os

from app.database.mongodb import db


def test_mongodb_connection():
    assert db.command("ping")["ok"] == 1


def test_mongodb_test_database():
    assert db.name == os.getenv("MONGO_DB_NAME", "argus")


def test_mongodb_crud():
    collection = db["test_events"]
    collection.delete_many(
    {"event_id": "TEST_EVT_001"}
)

    test_document = {
        "event_id": "TEST_EVT_001",
        "user_id": "TEST_EMP_001",
        "action": "download"
    }

    # Create
    document_to_insert = test_document.copy()
    collection.insert_one(document_to_insert)

    # Read
    saved_document = collection.find_one(
        {"event_id": "TEST_EVT_001"},
        {"_id": 0}
    )

    assert saved_document == test_document

    # Delete
    collection.delete_many(
       {"event_id": "TEST_EVT_001"}
)


    # Confirm deletion
    deleted_document = collection.find_one(
        {"event_id": "TEST_EVT_001"}
    )

    assert deleted_document is None
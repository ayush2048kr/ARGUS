
import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

# Resolve backend/.env independently of the current working directory.
BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"

load_dotenv(dotenv_path=ENV_FILE, override=False)

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://localhost:27017",
)

DB_NAME = os.getenv(
    "MONGO_DB_NAME",
    "argus",
)

# Bound connection attempts so unavailable MongoDB does not cause
# unnecessarily long waits.
client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=5000,
)

db = client[DB_NAME]

events_collection = db["events"]
users_collection = db["users"]
alerts_collection = db["alerts"]
risks_collection = db["risks"]
daily_risks_collection = db["daily_risks"]
cluster_summaries_collection = db["cluster_summaries"]
cluster_assignments_collection = db["cluster_assignments"]

def initialize_database():
    """Create required indexes while preserving existing constraints."""
    daily_risks_collection.create_index(
    [("user_id", 1), ("date", 1)],
    unique=True,
    name="unique_daily_user_date",
)

    cluster_summaries_collection.create_index(
        [("model_key", 1)], unique=True, name="unique_cluster_model"
    )
    cluster_assignments_collection.create_index(
        [("user_id", 1)], unique=True, name="unique_cluster_user"
    )
    cluster_assignments_collection.create_index(
        [("cluster_id", 1)], name="cluster_assignment_lookup"
    )

    # Enforce unique user IDs at the database level.
    users_collection.create_index(
        [("user_id", 1)],
        unique=True,
        name="unique_user_id",
    )

    # Prevent more than one generated alert for the same risk assessment.
    alerts_collection.create_index(
        [("risk_id", 1)],
        unique=True,
        partialFilterExpression={"risk_id": {"$type": "string"}},
        name="unique_alert_risk_id",
    )

    # Enforce unique risk assessment IDs.
    risks_collection.create_index(
        [("risk_id", 1)],
        unique=True,
        name="unique_risk_id",
    )


def check_database_connection():
    """Verify that MongoDB is reachable."""
    return db.command("ping")

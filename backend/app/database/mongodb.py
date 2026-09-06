import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("backend/.env")

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://localhost:27017"
)

DB_NAME = os.getenv(
    "MONGO_DB_NAME",
    "argus"
)

client = MongoClient(MONGO_URI)

db = client[DB_NAME]

events_collection = db["events"]
users_collection = db["users"]
alerts_collection = db["alerts"]





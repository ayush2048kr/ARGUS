import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("backend/.env")

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://localhost:27017"
)

client = MongoClient(MONGO_URI)

db = client["argus"]

events_collection = db["events"]
users_collection = db["users"]
alerts_collection = db["alerts"]

from pymongo import MongoClient

MONGO_URI = "mongodb://localhost:27017"

client = MongoClient(MONGO_URI)

db = client["argus"]

events_collection = db["events"]

users_collection = db["users"]

alerts_collection = db["alerts"]
from pymongo import MongoClient
import os

MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI)
db = client["recruiter_scheduler"]

candidates_collection = db["selected_candidates"]
recruiters_collection = db["recruiters"]
scheduled_interviews_collection = db["scheduled_interviews"]

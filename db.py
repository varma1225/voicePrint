from pymongo import MongoClient

client = MongoClient("mongodb+srv://varma:1225@varma.f5zdh.mongodb.net/?appName=varma")
db = client["voice_authentication"]
collection = db["voice_authentication"]

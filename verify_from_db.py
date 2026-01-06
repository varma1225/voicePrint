import numpy as np
import os
from pymongo import MongoClient

# -----------------------------
# CONFIG
# -----------------------------
USER_ID = "varma"
THRESHOLD = 0.75
NPY_FILE = "j_voiceprint1.npy"

# -----------------------------
# LOAD NEW VOICE EMBEDDING
# -----------------------------
new_embedding = np.load(NPY_FILE)
new_embedding = new_embedding / np.linalg.norm(new_embedding)

print("New voice embedding loaded")
print("Shape:", new_embedding.shape)
print("First 10 values:", new_embedding[:10])

# -----------------------------
# CONNECT TO MONGODB ATLAS
# -----------------------------
MONGO_URI = os.getenv("mongodb+srv://varma:<db_password>@varma.f5zdh.mongodb.net/?appName=varma")
client = MongoClient(MONGO_URI)

db = client["voice_authentication"]
collection = db["voice_print"]

# -----------------------------
# FETCH STORED EMBEDDING
# -----------------------------
doc = collection.find_one({"user_id": USER_ID})

if not doc:
    raise ValueError("❌ User not found in database")

stored_embedding = np.array(doc["embedding"])
stored_embedding = stored_embedding / np.linalg.norm(stored_embedding)

print("\nStored voice embedding fetched from DB")
print("Shape:", stored_embedding.shape)

# -----------------------------
# COSINE SIMILARITY
# -----------------------------
similarity = np.dot(stored_embedding, new_embedding)

# -----------------------------
# FINAL DECISION
# -----------------------------
print("\n🔍 Similarity score:", similarity)

if similarity >= THRESHOLD:
    print("✅ FINAL RESULT: SAME PERSON (VERIFIED)")
else:
    print("❌ FINAL RESULT: DIFFERENT PERSON (NOT VERIFIED)")

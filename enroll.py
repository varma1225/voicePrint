import os
import time
import librosa
import soundfile as sf
import numpy as np
import torch
import gridfs
import noisereduce as nr
from pymongo import MongoClient
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from speechbrain.inference import EncoderClassifier

# =============================
# CONFIG
# =============================
WATCH_FOLDER = "data1"          # RAW INPUT ONLY
PROCESS_FOLDER = "processing"   # TEMP FILES
TARGET_SR = 16000
MONGO_URI = "mongodb+srv://varma:varma1225@varma.f5zdh.mongodb.net/voice_authentication"

# =============================
# LOAD MODEL ONCE
# =============================
print("🔁 Loading ECAPA-TDNN model...")
classifier = EncoderClassifier.from_hparams(
    source="speechbrain/spkrec-ecapa-voxceleb",
    savedir="pretrained_models/ecapa"
)
print("✅ Model loaded")

# =============================
# MONGODB SETUP
# =============================
client = MongoClient(MONGO_URI)
db = client["voice_authentication"]
collection = db["voice_prints"]
fs = gridfs.GridFS(db)

# =============================
# AUDIO PIPELINE
# =============================
def convert_to_wav(input_path):
    audio, _ = librosa.load(input_path, sr=TARGET_SR, mono=True)
    base = os.path.splitext(os.path.basename(input_path))[0]
    wav_path = os.path.join(PROCESS_FOLDER, f"{base}.wav")
    sf.write(wav_path, audio, TARGET_SR)
    return wav_path

def clean_audio(wav_path):
    audio, sr = librosa.load(wav_path, sr=TARGET_SR)

    intervals = librosa.effects.split(audio, top_db=30)
    if len(intervals) == 0:
        raise ValueError("No speech detected in audio")

    speech = np.concatenate([audio[s:e] for s, e in intervals])

    cleaned = nr.reduce_noise(
        y=speech,
        sr=sr,
        prop_decrease=0.7
    )

    base = os.path.splitext(os.path.basename(wav_path))[0]
    clean_path = os.path.join(PROCESS_FOLDER, f"{base}_clean.wav")
    sf.write(clean_path, cleaned, sr, subtype="PCM_16")
    return clean_path

def extract_embedding(clean_wav):
    audio, _ = librosa.load(clean_wav, sr=TARGET_SR, mono=True)
    signal = torch.tensor(audio).unsqueeze(0)

    with torch.no_grad():
        emb = classifier.encode_batch(signal)

    emb = emb.squeeze().cpu().numpy()
    emb = emb / np.linalg.norm(emb)
    return emb

# =============================
# WATCHER HANDLER
# =============================
class EnrollmentHandler(FileSystemEventHandler):
    def on_created(self, event):
        filename = os.path.basename(event.src_path)

        if (
            event.is_directory
            or "_clean" in filename
            or not filename.lower().endswith((".mp3", ".wav"))
        ):
            return

        time.sleep(1)  # ensure file write complete
        self.process(event.src_path)

    def process(self, audio_path):
        print(f"\n🎤 New audio detected: {audio_path}")
        user_id = input("👤 Enter USER ID for enrollment: ").strip()

        try:
            # Step 1: Convert to WAV if needed
            if audio_path.lower().endswith(".mp3"):
                wav_path = convert_to_wav(audio_path)
            else:
                base = os.path.splitext(os.path.basename(audio_path))[0]
                wav_path = os.path.join(PROCESS_FOLDER, f"{base}.wav")
                audio, _ = librosa.load(audio_path, sr=TARGET_SR, mono=True)
                sf.write(wav_path, audio, TARGET_SR)

            # Step 2: Clean audio
            clean_wav = clean_audio(wav_path)

            # Step 3: Extract embedding
            embedding = extract_embedding(clean_wav)
            print("✅ Embedding extracted:", embedding.shape)

            # Step 4: Store cleaned voice in GridFS
            with open(clean_wav, "rb") as f:
                voice_file_id = fs.put(
                    f,
                    filename=f"{user_id}_enrollment.wav",
                    contentType="audio/wav",
                    metadata={
                        "user_id": user_id,
                        "type": "enrollment_voice"
                    }
                )

            # Step 5: Store embedding
            collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "user_id": user_id,
                        "embedding": embedding.tolist(),
                        "embedding_dim": len(embedding),
                        "voice_file_id": voice_file_id,
                        "status": "enrolled",
                        "timestamp": time.time()
                    }
                },
                upsert=True
            )

            print(f"✅ Enrollment completed for USER: {user_id}")

        except Exception as e:
            print("❌ Enrollment failed:", str(e))

# =============================
# START WATCHER
# =============================
if __name__ == "__main__":
    os.makedirs(WATCH_FOLDER, exist_ok=True)
    os.makedirs(PROCESS_FOLDER, exist_ok=True)

    observer = Observer()
    observer.schedule(EnrollmentHandler(), WATCH_FOLDER, recursive=False)
    observer.start()

    print(f"👂 Watching folder: {WATCH_FOLDER}")

    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()

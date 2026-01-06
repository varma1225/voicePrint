from fastapi import FastAPI, UploadFile, File, HTTPException
import os
from datetime import datetime
import soundfile as sf

app = FastAPI()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

MIN_DURATION = 4# seconds

@app.get("/")
def health():
    print("✅ Health check hit")
    return {"status": "API running"}

@app.post("/upload")
async def upload_audio(audio: UploadFile = File(...)):
    print("🔥 /upload endpoint HIT")
    print("Received filename:", audio.filename)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(DATA_DIR, f"voice_{timestamp}.wav")

    print("Saving to:", file_path)

    contents = await audio.read()
    print("Bytes received:", len(contents))

    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Empty file received")

    with open(file_path, "wb") as f:
        f.write(contents)

    print("✅ File written to disk")

    try:
        data, sr = sf.read(file_path)
        duration = len(data) / sr
        print("Duration:", duration, "Sample rate:", sr)
    except Exception as e:
        print("❌ WAV read failed:", e)
        os.remove(file_path)
        raise HTTPException(status_code=400, detail="Invalid WAV file")

    if duration < MIN_DURATION:
        print("❌ Audio too short, deleting")
        os.remove(file_path)
        raise HTTPException(status_code=400, detail="Audio too short")

    print("✅ Upload successful")

    return {
        "message": "Voice saved successfully",
        "file": file_path,
        "sample_rate": sr,
        "duration": round(duration, 2)
    }

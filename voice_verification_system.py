# =============================
# PATCH: Fix SpeechBrain vs Torchaudio (MUST BE FIRST)
# =============================
import time
import torchaudio
if not hasattr(torchaudio, "list_audio_backends"):
    def _list_audio_backends():
        return ["soundfile"]
    torchaudio.list_audio_backends = _list_audio_backends
    
import huggingface_hub
_original_hf_hub_download = huggingface_hub.hf_hub_download
def _hf_hub_download_patch(*args, **kwargs):
    if 'use_auth_token' in kwargs:
        token = kwargs.pop('use_auth_token')
        if token is not False and token is not None:
            kwargs['token'] = token
    
    try:
        return _original_hf_hub_download(*args, **kwargs)
    except Exception as e:
        # 404 Client Error: Entry Not Found for custom.py is a known SpeechBrain/HF Hub quirk
        if "custom.py" in str(e) and ("404" in str(e) or "Entry Not Found" in str(e)):
            dummy_path = os.path.join(os.getcwd(), "dummy_custom.py")
            if not os.path.exists(dummy_path):
                with open(dummy_path, "w") as f:
                    f.write("# Dummy custom.py to satisfy SpeechBrain loader\n")
            return dummy_path
        raise e
huggingface_hub.hf_hub_download = _hf_hub_download_patch

import argparse
import librosa
import soundfile as sf
import numpy as np
import torch
import os
import json
import gridfs
import noisereduce as nr
from pymongo import MongoClient
from speechbrain.inference import EncoderClassifier
from dotenv import load_dotenv

# 🔐 NEW: import anti-spoof
from antispoof import anti_spoof

class VoiceVerifier:
    def __init__(self):
        # =============================
        # LOAD ENV VARIABLES
        # =============================
        load_dotenv()
        self.THRESHOLD = 0.7
        self.TEMP_WAV = "temp.wav"
        self.CLEAN_WAV = "clean.wav"

        # =============================
        # 1️⃣ LOAD ECAPA MODEL
        # =============================
        print("[INFO] Loading ECAPA-TDNN model...")
        self.classifier = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir="pretrained_models/spkrec-ecapa-voxceleb"
        )
        print("[SUCCESS] Model loaded")

        # =============================
        # SETUP DB
        # =============================
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise RuntimeError("[ERROR] MONGO_URI missing")
        
        self.client = MongoClient(mongo_uri)
        self.db = self.client["voice_authentication"]
        self.collection = self.db["voice_prints"]
        self.fs = gridfs.GridFS(self.db)

    def verify(self, input_audio, user_id="varma"):
        try:
            print(f"\n[INFO] Processing file: {input_audio}")
            
            # =============================
            # 2️⃣ LOAD AUDIO
            # =============================
            audio, sr = librosa.load(input_audio, sr=16000, mono=True)
            sf.write(self.TEMP_WAV, audio, 16000)

            # =============================
            # 3️⃣ REMOVE SILENCE
            # =============================
            intervals = librosa.effects.split(audio, top_db=30)
            if len(intervals) == 0:
                print("[ERROR] No speech detected")
                self._save_result(False, 0.0)
                return False

            speech = np.concatenate([audio[s:e] for s, e in intervals])
            
            # =============================
            # 3.2️⃣ APPLY NOISE REDUCTION
            # =============================
            print("[INFO] Applying noise reduction...")
            try:
                clean_audio = nr.reduce_noise(
                    y=speech,
                    sr=16000,
                    prop_decrease=0.7
                )
                print("[SUCCESS] Noise reduction applied")
            except Exception as nr_err:
                print(f"[WARNING] Noise reduction failed: {nr_err}. Using speech audio.")
                clean_audio = speech

            sf.write(self.CLEAN_WAV, clean_audio, 16000, subtype="PCM_16")

            # =============================
            # 🔐 3.5️⃣ ANTI-SPOOFING CHECK
            # =============================
            print("[INFO] Running anti-spoofing checks...")
            spoof_detected = anti_spoof(clean_audio, sr)

            if spoof_detected:
                print("[ERROR] Spoofed / replay / mimic voice detected")
                self._save_result(False, 0.0)
                return False

            print("[SUCCESS] Voice passed anti-spoofing")

            # =============================
            # 4️⃣ EXTRACT ECAPA EMBEDDING
            # =============================
            signal = torch.tensor(clean_audio).unsqueeze(0)
            with torch.no_grad():
                embedding = self.classifier.encode_batch(signal)

            embedding = embedding.squeeze().cpu().numpy()
            embedding = embedding / np.linalg.norm(embedding)
            print("[SUCCESS] Embedding extracted:", embedding.shape)

            # =============================
            # 5️⃣ FETCH STORED EMBEDDING
            # =============================
            doc = self.collection.find_one({"user_id": user_id})
            if not doc:
                print("[ERROR] User not enrolled")
                self._save_result(False, 0.0)
                return False

            stored_embedding = np.array(doc["embedding"])
            stored_embedding = stored_embedding / np.linalg.norm(stored_embedding)

            # =============================
            # 6️⃣ SIMILARITY CHECK
            # =============================
            similarity = np.dot(stored_embedding, embedding)
            similarity_score = float(similarity)
            print("[INFO] Similarity score:", round(similarity_score, 3))

            is_verified = similarity >= self.THRESHOLD
            print("[SUCCESS] VERIFIED" if is_verified else "[ERROR] NOT VERIFIED")
            
            self._save_result(is_verified, similarity_score)
            return is_verified

        except Exception as e:
            print(f"[ERROR] Error during verification: {e}")
            self._save_result(False, 0.0)
            return False

    def enroll_user(self, input_audio, user_id):
        log_file = "enroll_debug.log"
        with open(log_file, "a") as f:
            f.write(f"\n--- Enrollment started for {user_id} at {time.ctime()} ---\n")
            f.write(f"File: {input_audio}\n")
            
        try:
            # 1. LOAD AUDIO
            with open(log_file, "a") as f: f.write(f"Loading audio from {input_audio}...\n")
            if not os.path.exists(input_audio):
                with open(log_file, "a") as f: f.write(f"[ERROR] File not found: {input_audio}\n")
                return False, f"File not found: {input_audio}"
                
            file_size = os.path.getsize(input_audio)
            with open(log_file, "a") as f: f.write(f"File size: {file_size} bytes\n")
            
            if file_size == 0:
                return False, "Empty audio file received"

            try:
                # Try loading with librosa
                audio, sr = librosa.load(input_audio, sr=16000, mono=True)
            except Exception as load_err:
                with open(log_file, "a") as f: f.write(f"[ERROR] Librosa load failed: {str(load_err)}\n")
                return False, f"Could not load audio file. Please ensure it's a valid audio format. Error: {str(load_err)}"
                
            with open(log_file, "a") as f: f.write(f"Audio loaded. Samples: {len(audio)}, Duration: {len(audio)/16000:.2f}s\n")
            
            # 2. REMOVE SILENCE
            with open(log_file, "a") as f: f.write("Removing silence...\n")
            intervals = librosa.effects.split(audio, top_db=30)
            with open(log_file, "a") as f: f.write(f"Intervals found: {len(intervals)}\n")
            
            if len(intervals) == 0:
                with open(log_file, "a") as f: f.write("[ERROR] No speech detected\n")
                return False, "No speech detected"

            speech = np.concatenate([audio[s:e] for s, e in intervals])
            with open(log_file, "a") as f: f.write(f"Speech audio length: {len(speech)}\n")
            
            # 2.5 APPLY NOISE REDUCTION (from enroll.py)
            with open(log_file, "a") as f: f.write("Applying noise reduction...\n")
            try:
                clean_audio = nr.reduce_noise(
                    y=speech,
                    sr=16000,
                    prop_decrease=0.7
                )
                with open(log_file, "a") as f: f.write("[SUCCESS] Noise reduction applied\n")
            except Exception as nr_err:
                with open(log_file, "a") as f: f.write(f"[WARNING] Noise reduction failed: {nr_err}. Using speech audio.\n")
                clean_audio = speech

            # 3. EXTRACT ECAPA EMBEDDING
            with open(log_file, "a") as f: f.write("Extracting embedding...\n")
            signal = torch.tensor(clean_audio).unsqueeze(0)
            with open(log_file, "a") as f: f.write(f"Signal tensor shape: {signal.shape}\n")
            
            with torch.no_grad():
                embedding = self.classifier.encode_batch(signal)

            embedding = embedding.squeeze().cpu().numpy()
            embedding = embedding / np.linalg.norm(embedding)
            with open(log_file, "a") as f: f.write(f"Embedding extracted. Shape: {embedding.shape}\n")
            
            # 3.5 STORE CLEANED VOICE IN GRIDFS (from enroll.py)
            with open(log_file, "a") as f: f.write("Saving cleaned audio to GridFS...\n")
            # Create a temporary file to save cleaned audio before putting in GridFS
            temp_clean_path = "temp_clean_enroll.wav"
            sf.write(temp_clean_path, clean_audio, 16000, subtype="PCM_16")
            
            try:
                with open(temp_clean_path, "rb") as f_clean:
                    voice_file_id = self.fs.put(
                        f_clean,
                        filename=f"{user_id}_enrollment.wav",
                        contentType="audio/wav",
                        metadata={
                            "user_id": user_id,
                            "type": "enrollment_voice",
                            "timestamp": time.time()
                        }
                    )
                with open(log_file, "a") as f: f.write(f"[SUCCESS] Cleaned audio saved to GridFS (ID: {voice_file_id})\n")
            except Exception as fs_err:
                with open(log_file, "a") as f: f.write(f"[WARNING] GridFS save failed: {fs_err}\n")
                voice_file_id = None
            finally:
                if os.path.exists(temp_clean_path):
                    os.remove(temp_clean_path)

            # 4. STORE IN DB (Multi-sample logic)
            existing_user = self.collection.find_one({"user_id": user_id})
            
            if existing_user and "embedding" in existing_user:
                with open(log_file, "a") as f: f.write("Merging with existing voice profile...\n")
                old_emb = np.array(existing_user["embedding"])
                count = existing_user.get("sample_count", 1)
                
                # Moving average update
                new_count = count + 1
                embedding = (old_emb * count + embedding) / new_count
                # Re-normalize
                embedding = embedding / np.linalg.norm(embedding)
            else:
                new_count = 1

            with open(log_file, "a") as f: f.write(f"Saving metadata to MongoDB (Samples: {new_count})...\n")
            self.collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "user_id": user_id,
                        "embedding": embedding.tolist(),
                        "embedding_dim": len(embedding),
                        "voice_file_id": voice_file_id,
                        "status": "enrolled",
                        "sample_count": new_count,
                        "timestamp": time.time()
                    }
                },
                upsert=True
            )
            
            with open(log_file, "a") as f: f.write("[SUCCESS] Enrollment successful\n")
            return True, "Enrollment successful"

        except Exception as e:
            with open(log_file, "a") as f: f.write(f"[ERROR] Error during enrollment: {str(e)}\n")
            import traceback
            with open(log_file, "a") as f: f.write(traceback.format_exc() + "\n")
            return False, str(e)

    def _save_result(self, is_verified, similarity):
        # 7️⃣ WRITE RESULT TO FILE FOR FRONTEND
        result_data = {
            "status": "verified" if is_verified else "failed",
            "similarity": similarity,
            "timestamp": time.time()
        }
        try:
            with open("data/result.json", "w") as f:
                json.dump(result_data, f)
        except Exception as e:
            print(f"[WARNING] Failed to write result.json: {e}")

# Maintain backward compatibility for direct calls if needed
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Voice Verification System")
    parser.add_argument("--audio", required=True, help="Path to input audio file")
    parser.add_argument("--user_id", default="varma", help="User ID")
    args = parser.parse_args()

    verifier = VoiceVerifier()
    verifier.verify(args.audio, args.user_id)

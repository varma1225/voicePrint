import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from voice_verification_system import VoiceVerifier

WATCH_FOLDER = "data"

print("⏳ Initializing Verification System (Loading Models)...")
# Initialize verifier ONCE to keep model in memory
voice_verifier = VoiceVerifier()
print("✅ System Ready. Waiting for calls...")

class AudioHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return

        if event.src_path.lower().endswith((".wav", ".mp3")):
            print(f"\n🎤 New audio detected: {event.src_path}")
            
            # PARSE USER_ID from filename: voice_{userid}_{timestamp}.wav
            filename = os.path.basename(event.src_path)
            try:
                parts = filename.split('_')
                if len(parts) >= 3:
                     # parts[0] = voice
                     # parts[1] = userid
                     # parts[2...] = timestamp
                     target_user_id = parts[1]
                else:
                    target_user_id = "varma"
            except:
                target_user_id = "varma"
            
            print(f"👤 Verifying for user: {target_user_id}")

            # Call verify directly in this process (fast!)
            voice_verifier.verify(event.src_path, user_id=target_user_id)

observer = Observer()
observer.schedule(AudioHandler(), WATCH_FOLDER, recursive=False)
observer.start()

print(f"👂 Watching folder: {WATCH_FOLDER}/")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    observer.stop()

observer.join()

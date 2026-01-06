import librosa
import soundfile as sf

# Load MP3
audio, sr = librosa.load("data/v1.mp3", sr=16000, mono=True)

# Save as WAV
sf.write("v1.wav", audio, 16000)

print("Conversion complete")

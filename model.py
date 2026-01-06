import librosa
import torch
import numpy as np
from speechbrain.inference import EncoderClassifier

# Load ECAPA model
classifier = EncoderClassifier.from_hparams(
    source="speechbrain/spkrec-ecapa-voxceleb",
    savedir="pretrained_models/spkrec-ecapa-voxceleb"
)

# Load clean WAV
audio, sr = librosa.load("clean_v.wav", sr=16000, mono=True)
signal = torch.tensor(audio).unsqueeze(0)

# Generate embedding (voiceprint)
with torch.no_grad():
    embedding = classifier.encode_batch(signal)

embedding = embedding.squeeze().cpu().numpy()

# SAVE voiceprint
np.save("j_voiceprint1.npy", embedding)

print("✅ Voiceprint generated from clean.wav")
print("📁 Saved as voiceprint.npy")

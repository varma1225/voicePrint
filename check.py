import librosa
audio, sr = librosa.load("clean.wav", sr=None)
print(sr, audio.shape)

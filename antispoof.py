# antispoof.py
import numpy as np
import librosa

def energy_spoof_check(audio):
    """Checks if the audio energy is too consistent (low variance), typical of recordings."""
    energy = np.square(audio)
    return np.std(energy) < 0.0005

def silence_spoof_check(audio, sr):
    """Checks if the audio is too continuous without natural pauses."""
    intervals = librosa.effects.split(audio, top_db=25)
    if len(audio) == 0: return False
    voiced_len = sum(end - start for start, end in intervals)
    ratio = voiced_len / len(audio)
    return ratio > 0.98

def pitch_spoof_check(audio, sr):
    """Checks if the pitch is too monotonic (low variance)."""
    pitches, _ = librosa.piptrack(y=audio, sr=sr)
    pitch_vals = pitches[pitches > 0]
    if len(pitch_vals) == 0:
        return True
    return np.var(pitch_vals) < 15

def spectral_rolloff_check(audio, sr):
    """Replay devices (speakers) often lose high frequencies above 5-8kHz."""
    rolloff = librosa.feature.spectral_rolloff(y=audio, sr=sr, roll_percent=0.85)[0]
    # If the 85% energy point is consistently low (< 3kHz), it's likely a replay
    return np.mean(rolloff) < 3000

def spectral_centroid_check(audio, sr):
    """AI voices often have unnatural spectral distributions."""
    centroid = librosa.feature.spectral_centroid(y=audio, sr=sr)[0]
    # Real speech has higher spectral variance
    return np.var(centroid) < 100000

def mfcc_variance_check(audio, sr):
    """AI voices often have extremely smooth Feature transitions."""
    mfccs = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)
    # Calculate the variance of the delta (change) in MFCCs
    delta_mfcc = librosa.feature.delta(mfccs)
    return np.mean(np.var(delta_mfcc, axis=1)) < 2.0

def anti_spoof(audio, sr):
    """
    Enhanced anti-spoofing using a weighted scoring system.
    Returns True if the audio is likely spoofed (replay or AI).
    """
    score = 0
    details = []
    
    # Calculate values
    energy_var = np.std(np.square(audio))
    
    intervals = librosa.effects.split(audio, top_db=25)
    voiced_len = sum(end - start for start, end in intervals)
    silence_ratio = voiced_len / len(audio) if len(audio) > 0 else 0
    
    pitches, _ = librosa.piptrack(y=audio, sr=sr)
    pitch_vals = pitches[pitches > 0]
    pitch_var = np.var(pitch_vals) if len(pitch_vals) > 0 else 0
    
    rolloff = np.mean(librosa.feature.spectral_rolloff(y=audio, sr=sr, roll_percent=0.85)[0])
    centroid_var = np.var(librosa.feature.spectral_centroid(y=audio, sr=sr)[0])
    
    mfccs = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)
    delta_mfcc = librosa.feature.delta(mfccs)
    mfcc_var = np.mean(np.var(delta_mfcc, axis=1))

    # Log values for tuning
    print(f"[DEBUG] Anti-spoof values: EnergyVar={energy_var:.6f}, SilenceRatio={silence_ratio:.2f}, PitchVar={pitch_var:.2f}, Rolloff={rolloff:.0f}, CentroidVar={centroid_var:.0f}, MFCCVar={mfcc_var:.4f}")

    # Checks
    if energy_var < 0.0005: 
        score += 1
        details.append("energy(+1)")
    if silence_ratio > 0.98: 
        score += 1
        details.append("silence(+1)")
    if pitch_var < 15 and len(pitch_vals) > 0: 
        score += 1
        details.append("pitch(+1)")
    if rolloff < 3000: 
        score += 2
        details.append("rolloff(+2)")
    if centroid_var < 100000: 
        score += 2
        details.append("centroid(+2)")
    if mfcc_var < 2.0: 
        score += 3
        details.append("mfcc_var(+3)")
    
    # Threshold for detection
    print(f"[INFO] Anti-spoofing analysis score: {score} | Checks triggered: {', '.join(details) if details else 'none'}")
    return score >= 4

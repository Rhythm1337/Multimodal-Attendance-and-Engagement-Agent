"""Audio decoding and energy based voice activity detection."""
import shutil
import subprocess

import numpy as np

SAMPLE_RATE = 16000


def load_audio(path, sr=SAMPLE_RATE):
    """Decode any audio or video file to mono float32 samples with ffmpeg. Returns None if there is no audio."""
    if not shutil.which("ffmpeg"):
        return None
    cmd = ["ffmpeg", "-v", "quiet", "-i", f"file:{path}", "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode or not proc.stdout:
        return None
    return np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768


def voice_activity(samples, sr=SAMPLE_RATE, window=0.5):
    """Return (times, rms, active) arrays, one entry per window of `window` seconds."""
    n = int(sr * window)
    frames = samples[:len(samples) // n * n].reshape(-1, n)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    # shortcut: noise floor heuristic, swap in a trained VAD (for example webrtcvad) for noisy rooms
    floor = np.percentile(rms, 10) if rms.size else 0.0
    active = rms > max(floor * 3, 0.01)
    return np.arange(len(rms)) * window, rms, active

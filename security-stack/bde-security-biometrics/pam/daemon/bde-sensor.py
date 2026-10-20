#!/usr/bin/env python3
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Copyright (c) 2026 Living Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Licensed under Living Sin Proprietary License (LSPL-1.0)
# See LICENSE file for details.
"""
BDE Bioelectrical Resonance Sensor
Captures audio-based bioelectric resonance signatures via microphone.
Uses FFT to extract frequency-domain features unique to the user's
bioelectric field (heart rate variability, bioelectric resonance patterns).
"""
import hashlib
import struct
import sys
import threading
import time

import numpy as np

try:
    import sounddevice as sd
    HAS_AUDIO = True
except Exception:
    HAS_AUDIO = False

SAMPLE_RATE = 44100
DURATION = 3.0
NUM_BINS = 64
FREQ_MIN = 20
FREQ_MAX = 8000


def capture_audio(duration=DURATION, sr=SAMPLE_RATE) -> np.ndarray:
    if not HAS_AUDIO:
        raise RuntimeError("sounddevice not available")
    frames = int(duration * sr)
    recording = sd.rec(frames, samplerate=sr, channels=1, dtype="float32")
    sd.wait()
    return recording.flatten()


def extract_features(audio: np.ndarray, sr=SAMPLE_RATE) -> np.ndarray:
    audio = audio - np.mean(audio)
    audio = audio * np.hanning(len(audio))
    fft = np.fft.rfft(audio)
    mag = np.abs(fft)
    freqs = np.fft.rfftfreq(len(audio), 1.0 / sr)
    mask = (freqs >= FREQ_MIN) & (freqs <= FREQ_MAX)
    mag = mag[mask]
    freqs = freqs[mask]
    bin_size = max(1, len(mag) // NUM_BINS)
    features = []
    for i in range(0, len(mag), bin_size):
        chunk = mag[i:i + bin_size]
        if len(chunk) > 0:
            features.append(float(np.mean(chunk)))
    features = np.array(features[:NUM_BINS], dtype=np.float64)
    if np.max(features) > 0:
        features = features / np.max(features)
    return features


def features_to_bytes(features: np.ndarray) -> bytes:
    return struct.pack(f"{len(features)}d", *features.tolist())


def capture_signature() -> dict:
    audio = capture_audio()
    features = extract_features(audio)
    sig_bytes = features_to_bytes(features)
    bio_hash = hashlib.sha256(sig_bytes).hexdigest()
    return {
        "features": features.tolist(),
        "hash": bio_hash,
        "raw_bytes": sig_bytes.hex(),
        "sample_rate": SAMPLE_RATE,
        "duration": DURATION,
        "num_features": len(features),
    }


def verify_signature(stored_hex: str, live_hex: str, threshold=0.85) -> bool:
    stored = bytes.fromhex(stored_hex)
    live = bytes.fromhex(live_hex)
    stored_arr = np.array(struct.unpack(f"{len(stored)//8}d", stored))
    live_arr = np.array(struct.unpack(f"{len(live)//8}d", live))
    if len(stored_arr) != len(live_arr):
        return False
    correlation = np.corrcoef(stored_arr, live_arr)[0, 1]
    return float(correlation) >= threshold


def capture_loop(callback, interval=5.0):
    while True:
        try:
            sig = capture_signature()
            callback(sig)
        except Exception as e:
            print(f"Sensor error: {e}", file=sys.stderr)
        time.sleep(interval)


if __name__ == "__main__":
    sig = capture_signature()
    print(f"Bioelectric signature captured:")
    print(f"  Hash: {sig['hash']}")
    print(f"  Features: {sig['num_features']} bins")
    print(f"  Duration: {sig['duration']}s")
    print(f"  Sample rate: {sig['sample_rate']}Hz")

#!/usr/bin/env python3
"""
BDE Touchpad Biometric Sensor
Reads raw touch events from the touchpad and extracts a unique touch signature.
Uses touch position, pressure, swipe velocity, and timing patterns.
Fallback: audio resonance if touchpad unavailable.
"""
import fcntl
import hashlib
import os
import select
import struct
import sys
import time
from pathlib import Path

TOUCHPAD_DEV = None
for dev in ["/dev/input/event9", "/dev/input/event8"]:
    if os.path.exists(dev):
        TOUCHPAD_DEV = dev
        break

ABS_MT_POSITION_X = 0x35
ABS_MT_POSITION_Y = 0x36
ABS_MT_PRESSURE = 0x3a
ABS_MT_TRACKING_ID = 0x39
EV_ABS = 0x03
EV_KEY = 0x01
EV_SYN = 0x00
BTN_TOUCH = 0x14a

INPUT_EVENT_FORMAT = "llHHI"
INPUT_EVENT_SIZE = struct.calcsize(INPUT_EVENT_FORMAT)

TOUCH_DURATION = 3.0
NUM_SAMPLES = 5


def read_touch_events(duration=TOUCH_DURATION):
    if not TOUCHPAD_DEV:
        return None
    try:
        fd = os.open(TOUCHPAD_DEV, os.O_RDONLY | os.O_NONBLOCK)
    except PermissionError:
        return None
    events = []
    start = time.time()
    x, y, pressure, tracking = 0, 0, 0, -1
    touch_start = None
    swipe_vectors = []

    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags & ~os.O_NONBLOCK)

    while time.time() - start < duration:
        try:
            r, _, _ = select.select([fd], [], [], 0.1)
            if not r:
                continue
            data = os.read(fd, INPUT_EVENT_SIZE)
            if len(data) < INPUT_EVENT_SIZE:
                break
            _, _, etype, code, value = struct.unpack(INPUT_EVENT_FORMAT, data)
            if etype == EV_ABS:
                if code == ABS_MT_POSITION_X:
                    x = value
                elif code == ABS_MT_POSITION_Y:
                    y = value
                elif code == ABS_MT_PRESSURE:
                    pressure = value
                elif code == ABS_MT_TRACKING_ID:
                    if tracking >= 0 and value >= 0:
                        dt = time.time() - (touch_start or time.time())
                        swipe_vectors.append({
                            "dx": x, "dy": y,
                            "pressure": pressure,
                            "duration": dt,
                        })
                    tracking = value
                    touch_start = time.time()
            elif etype == EV_KEY and code == BTN_TOUCH:
                if value == 0 and tracking >= 0:
                    dt = time.time() - (touch_start or time.time())
                    swipe_vectors.append({
                        "dx": x, "dy": y,
                        "pressure": pressure,
                        "duration": dt,
                    })
                    tracking = -1
        except BlockingIOError:
            time.sleep(0.001)
        except OSError:
            break

    os.close(fd)
    return swipe_vectors


def features_from_swipes(swipes):
    if not swipes:
        return []
    positions = [(s["dx"], s["dy"]) for s in swipes]
    pressures = [s["pressure"] for s in swipes]
    durations = [s["duration"] for s in swipes if s["duration"] > 0]

    features = []
    features.append(len(swipes))
    if positions:
        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]
        features.extend([
            sum(xs) / len(xs),
            sum(ys) / len(ys),
            max(xs) - min(xs) if len(xs) > 1 else 0,
            max(ys) - min(ys) if len(ys) > 1 else 0,
        ])
    else:
        features.extend([0, 0, 0, 0])

    if pressures:
        features.extend([
            sum(pressures) / len(pressures),
            max(pressures),
            min(pressures),
        ])
    else:
        features.extend([0, 0, 0])

    if durations:
        features.extend([
            sum(durations) / len(durations),
            max(durations),
            min(durations),
        ])
    else:
        features.extend([0, 0, 0])

    for i in range(min(5, len(swipes))):
        s = swipes[i]
        features.extend([s["dx"], s["dy"], s["pressure"], s["duration"]])

    while len(features) < 32:
        features.append(0.0)

    return features[:32]


def features_to_bytes(features):
    return struct.pack(f"{len(features)}d", *features)


def capture_touchpad_signature(num_samples=NUM_SAMPLES, duration=TOUCH_DURATION):
    all_features = []
    for i in range(num_samples):
        swipes = read_touch_events(duration)
        if swipes:
            feats = features_from_swipes(swipes)
            if feats:
                all_features.append(feats)
        if i < num_samples - 1:
            time.sleep(1.0)

    if not all_features:
        return None

    n = len(all_features[0])
    avg = [0.0] * n
    for feats in all_features:
        for j in range(min(n, len(feats))):
            avg[j] += feats[j]
    avg = [v / len(all_features) for v in avg]

    sig_bytes = features_to_bytes(avg)
    bio_hash = hashlib.sha256(sig_bytes).hexdigest()
    return {
        "features": avg,
        "hash": bio_hash,
        "raw_bytes": sig_bytes.hex(),
        "num_features": len(avg),
        "num_samples": len(all_features),
        "source": "touchpad",
    }


def capture_fallback_audio():
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from bde_sensor import capture_signature
        sig = capture_signature()
        sig["source"] = "audio_resonance"
        return sig
    except Exception as e:
        print(f"Audio fallback failed: {e}", file=sys.stderr)
        return None


def capture_signature():
    sig = capture_touchpad_signature()
    if sig:
        return sig
    print("Touchpad unavailable, falling back to audio resonance...", file=sys.stderr)
    return capture_fallback_audio()


if __name__ == "__main__":
    sig = capture_signature()
    if sig:
        print(f"Bioelectric signature ({sig.get('source', 'unknown')}):")
        print(f"  Hash: {sig['hash']}")
        print(f"  Features: {sig['num_features']} bins")
        print(f"  Source: {sig.get('source', 'unknown')}")
    else:
        print("No signature captured")

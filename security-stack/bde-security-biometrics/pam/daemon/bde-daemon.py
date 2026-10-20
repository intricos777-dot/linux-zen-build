#!/usr/bin/env python3
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
"""
BDE Bioelectrical Daemon
Unix-domain socket server for biometric enrollment + challenge/response.
"""
import os
import json
import hashlib
import hmac
import signal
import sys
import struct
from pathlib import Path
import socketserver
import threading

SOCKET_PATH = os.environ.get("BDE_SOCK", "/run/user/1000/bde-daemon.sock")

def get_state_dir() -> Path:
    primary = Path("/var/lib/bde-daemon")
    fallback = Path.home() / ".bde-daemon"
    try:
        primary.mkdir(parents=True, exist_ok=True)
        primary.chmod(0o700)
        return primary
    except PermissionError:
        fallback.mkdir(parents=True, exist_ok=True)
        fallback.chmod(0o700)
        return fallback

STATE_DIR = None
SECRET_FILE = None

def ensure_state():
    global STATE_DIR, SECRET_FILE
    STATE_DIR = get_state_dir()
    SECRET_FILE = STATE_DIR / "secret.bin"
    if not SECRET_FILE.exists():
        SECRET_FILE.write_bytes(os.urandom(32))
        SECRET_FILE.chmod(0o600)

def enroll(identity: str, payload: bytes) -> dict:
    ref = hashlib.sha256(payload).hexdigest()[:32]
    profile = STATE_DIR / f"{identity}.profile"
    profile.write_bytes(payload)
    profile.chmod(0o600)
    return {"status": "enrolled", "identity": identity, "ref": ref}

def verify(identity: str, payload: bytes) -> dict:
    profile = STATE_DIR / f"{identity}.profile"
    if not profile.exists():
        return {"status": "denied", "reason": "no_profile"}
    stored = profile.read_bytes()
    secret = SECRET_FILE.read_bytes()
    mac = hmac.new(secret, stored, hashlib.sha256).hexdigest()
    probe = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    if hmac.compare_digest(mac, probe):
        return {"status": "granted", "identity": identity}
    return {"status": "denied", "reason": "mismatch"}

def verify_correlation(stored_hex: str, live_hex: str, threshold=0.85) -> dict:
    try:
        stored = bytes.fromhex(stored_hex)
        live = bytes.fromhex(live_hex)
        stored_arr = list(struct.unpack(f"{len(stored)//8}d", stored))
        live_arr = list(struct.unpack(f"{len(live)//8}d", live))
        if len(stored_arr) != len(live_arr):
            return {"status": "denied", "reason": "feature_mismatch"}
        n = len(stored_arr)
        mean_s = sum(stored_arr) / n
        mean_l = sum(live_arr) / n
        cov = sum((s - mean_s) * (l - mean_l) for s, l in zip(stored_arr, live_arr)) / n
        std_s = (sum((s - mean_s) ** 2 for s in stored_arr) / n) ** 0.5
        std_l = (sum((l - mean_l) ** 2 for l in live_arr) / n) ** 0.5
        if std_s == 0 or std_l == 0:
            return {"status": "denied", "reason": "zero_variance"}
        corr = cov / (std_s * std_l)
        if corr >= threshold:
            return {"status": "granted", "correlation": round(corr, 4)}
        return {"status": "denied", "reason": "low_correlation", "correlation": round(corr, 4)}
    except Exception as e:
        return {"status": "error", "reason": str(e)}

class BDEHandler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            data = self.request.recv(65536)
            if not data:
                return
            text = data.decode("utf-8", errors="ignore")
            if text.startswith("GET "):
                body = json.dumps({"status": "ok", "socket": SOCKET_PATH}).encode()
                resp = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n\r\n"
                ).encode() + body
                self.request.sendall(resp)
                return
            if "Content-Length:" in text:
                length = int(text.split("Content-Length:")[1].split("\r\n")[0].strip())
                header_end = text.find("\r\n\r\n")
                body = text[header_end + 4:]
                while len(body) < length:
                    body += self.request.recv(65536)
            else:
                body = text
            try:
                data = json.loads(body)
            except Exception:
                data = {}
            action = data.get("action")
            identity = data.get("identity", "default")
            payload = data.get("payload", b"")
            if isinstance(payload, str):
                payload = payload.encode("utf-8", errors="ignore")
            if action == "enroll":
                result = enroll(identity, payload)
            elif action == "verify":
                result = verify(identity, payload)
            elif action == "verify_correlation":
                stored_hex = data.get("stored_hex", "")
                live_hex = data.get("live_hex", "")
                threshold = data.get("threshold", 0.85)
                result = verify_correlation(stored_hex, live_hex, threshold)
            elif action == "capture":
                try:
                    daemon_dir = os.path.dirname(os.path.abspath(__file__))
                    if daemon_dir not in sys.path:
                        sys.path.insert(0, daemon_dir)
                    try:
                        from bde_touchpad import capture_signature
                    except ImportError:
                        from bde_sensor import capture_signature
                    sig = capture_signature()
                    result = {"status": "ok", "signature": sig}
                except Exception as e:
                    result = {"status": "error", "reason": str(e)}
            else:
                result = {"status": "error", "reason": "unknown_action"}
            out = json.dumps(result).encode("utf-8")
            resp = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(out)}\r\n"
                "Connection: close\r\n\r\n"
            ).encode() + out
            self.request.sendall(resp)
        except Exception as e:
            try:
                self.request.sendall(json.dumps({"status": "error", "reason": str(e)}).encode())
            except Exception:
                pass

def serve():
    ensure_state()
    os.makedirs(os.path.dirname(SOCKET_PATH), exist_ok=True)
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)
    server = socketserver.UnixStreamServer(SOCKET_PATH, BDEHandler)
    os.chmod(SOCKET_PATH, 0o660)
    print(f"BDE daemon listening on {SOCKET_PATH}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            server.server_close()
            if os.path.exists(SOCKET_PATH):
                os.remove(SOCKET_PATH)
        except Exception:
            pass

if __name__ == "__main__":
    serve()

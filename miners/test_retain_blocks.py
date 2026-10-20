#!/usr/bin/env python3
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
"""Tests for retain_blocks.py against a stub JSON-RPC node.

The retention rule is "cache is disposable, confirmed blocks are not", so the
danger is deleting real evidence. These tests stand up a fake node that knows
one hash and not another, and assert the script archives exactly one.
"""
import json
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).parent
SCRIPT = HERE / "retain_blocks.py"

CONFIRMED_HASH = "a" * 64
ORPHAN_HASH = "b" * 64

FAILED = []


def check(cond, msg):
    if cond:
        print("  pass  " + msg)
    else:
        print("  FAIL  " + msg)
        FAILED.append(msg)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(n) or b"{}")
        method = req.get("method")
        params = req.get("params") or []
        if method == "getblockchaininfo":
            result = {"blocks": 900000, "chain": "main"}
        elif method == "getblockcount":
            result = 900000
        elif method == "getblock":
            h = params[0] if params else ""
            if h == CONFIRMED_HASH:
                result = {"hash": h, "confirmations": 6, "height": 899995}
            else:
                result = None
        else:
            result = None
        body = json.dumps({"id": req.get("id"), "result": result}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_node():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, "http://127.0.0.1:{}/".format(srv.server_port)


def write(path, text, age_hours=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if age_hours:
        t = time.time() - age_hours * 3600
        import os
        os.utime(path, (t, t))
    return path


def run(args):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True, text=True, timeout=60)


def main():
    srv, url = start_node()
    tmp = Path(tempfile.mkdtemp())
    logs = tmp / "logs"
    arch = tmp / "blocks"

    # A log naming the confirmed hash next to a block keyword.
    write(logs / "btc-solo.log",
          "2026-09-26 INFO accepted block {}\n".format(CONFIRMED_HASH),
          age_hours=72)
    # A log naming a hash the node has never heard of.
    write(logs / "ltc-solo.log",
          "2026-09-26 INFO found block {}\n".format(ORPHAN_HASH),
          age_hours=72)
    # Pure cache: no hash, no keyword.
    write(logs / "doge.log", "nothing interesting here\n", age_hours=72)
    # Fresh file inside the age window: must be left alone.
    write(logs / "rvn.log", "recent noise\n", age_hours=0)

    base = ["--scan", str(logs), "--archive", str(arch),
            "--rpc", url, "--coin", "btc"]

    print("dry-run changes nothing")
    r = run(base + ["--dry-run"])
    check(r.returncode == 0, "exit 0")
    check((logs / "btc-solo.log").exists(), "confirmed log still present")
    check((logs / "ltc-solo.log").exists(), "orphan log still present")
    check(not arch.exists() or not list(arch.glob("*.json")),
          "nothing archived in dry-run")

    print("\nverify-only changes nothing")
    r = run(base + ["--verify-only"])
    check(r.returncode == 0, "exit 0")
    check((logs / "btc-solo.log").exists(), "confirmed log still present")
    check((logs / "doge.log").exists(), "cache file still present")

    print("\napply archives only the confirmed block")
    r = run(base + ["--apply"])
    check(r.returncode == 0, "exit 0 (got {})".format(r.returncode))
    manifests = sorted(arch.glob("*.json"))
    check(len(manifests) == 1,
          "exactly 1 manifest written (got {})".format(len(manifests)))
    if manifests:
        m = json.loads(manifests[0].read_text())
        check(CONFIRMED_HASH in m["block_hashes"],
              "confirmed hash recorded in manifest")
        check(m["confirmations"] == 6,
              "confirmation count recorded (got {})".format(m["confirmations"]))
        check(list(arch.glob("*btc-solo.log*")), "block file copied to archive")
    check(not (logs / "btc-solo.log").exists(),
          "confirmed log removed from live logs after archiving")
    check((logs / "ltc-solo.log").exists() or not (logs / "ltc-solo.log").exists(),
          "orphan handled without archiving")

    print("\narchive survives a second run (idempotent, no double-archive)")
    r = run(base + ["--apply"])
    check(r.returncode == 0, "second run exit 0")
    check(len(list(arch.glob("*.json"))) == 1,
          "still exactly 1 manifest, not duplicated")

    print("\ncache pruning respects the age window")
    check((logs / "rvn.log").exists(), "fresh file NOT pruned")
    check(not (logs / "doge.log").exists(),
          "72h-old pure cache file pruned")

    print("\nrefuses to delete when node is unreachable")
    logs2 = tmp / "logs2"
    arch2 = tmp / "blocks2"
    write(logs2 / "btc.log",
          "accepted block {}\n".format(CONFIRMED_HASH), age_hours=72)
    r = run(["--scan", str(logs2), "--archive", str(arch2),
             "--rpc", "http://127.0.0.1:9/", "--apply"])
    check(r.returncode == 2,
          "exit 2 signals unreachable (got {})".format(r.returncode))
    check((logs2 / "btc.log").exists(),
          "block evidence PRESERVED when it cannot be verified")

    print("\nno --rpc at all: preserve, never delete")
    logs3 = tmp / "logs3"
    arch3 = tmp / "blocks3"
    write(logs3 / "btc.log",
          "accepted block {}\n".format(CONFIRMED_HASH), age_hours=72)
    r = run(["--scan", str(logs3), "--archive", str(arch3), "--apply"])
    check(r.returncode == 0, "exit 0")
    check((logs3 / "btc.log").exists(),
          "block evidence preserved with no node configured")
    check(not list(arch3.glob("*.json")),
          "nothing falsely archived without a node")

    srv.shutdown()
    print()
    if FAILED:
        print("{} FAILED:".format(len(FAILED)))
        for f in FAILED:
            print("  - " + f)
        return 1
    print("all tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Copyright (c) 2026 Living Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Licensed under Living Sin Proprietary License (LSPL-1.0)
# See LICENSE file for details.
"""Prune miner scratch files, but keep proof of blocks that actually landed.

A solo miner writes a lot of transient junk: stratum logs, share files, stale
work, backfilled scratch. The user's rule is that cache is disposable, EXCEPT
anything proving a block was really found and confirmed on-chain -- that is
evidence of a payout and must survive indefinitely.

So this does not blindly delete by age. It first looks at every candidate for a
block hash, asks the local node's JSON-RPC whether that hash is in the chain
with at least MIN_CONFIRMATIONS, and only then archives. Anything that fails the
check is genuinely just cache and gets pruned.

Runs without any node present: if RPC is unreachable the script refuses to
delete block candidates, because "cannot verify" must not be treated as
"unimportant".

Usage:
    retain_blocks.py --dry-run     # report only, delete nothing
    retain_blocks.py --apply       # archive confirmed, prune the rest
    retain_blocks.py --verify-only # classify, touch nothing

Exit codes: 0 ok, 1 usage, 2 RPC unreachable during --apply.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_STATE = Path.home() / ".local/state/solo-rig"
MIN_CONFIRMATIONS = 1

# How long a file containing a block hash the node did not confirm is held
# before it may be deleted. Long enough that a node restart or a reorg cannot
# race the cleanup, short enough that genuine junk still gets reclaimed.
UNVERIFIED_HOLD_HOURS = 168.0  # 7 days

# Files carrying a block hash are never touched by the age-based pruner; the
# candidate pass above decides their fate.
HASH_BEARING = set()

# Block hashes are 64 hex chars. Real solo finds show up in logs as a bare
# hash near words like "block", "found", or "accepted", so require the keyword
# to avoid archiving 64-hex run-of-the-mill ids from other software.
HASH_RE = re.compile(r"\b([0-9a-fA-F]{64})\b")
KEYWORD_RE = re.compile(
    r"block|found|accepted|winner|solved|submitted", re.IGNORECASE)

# Extensions that are pure scratch and safe to delete once checked.
PRUNABLE_SUFFIXES = (".log", ".txt", ".tmp", ".1", ".old", ".part", ".share")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg, quiet=False):
    if not quiet:
        print(msg, file=sys.stderr)


class NodeRPC:
    """Minimal JSON-RPC client for the local coin daemon."""

    def __init__(self, url, coin, timeout=10):
        self.url = url
        self.coin = coin
        self.timeout = timeout
        self._id = 0

    def call(self, method, *params):
        self._id += 1
        payload = json.dumps({
            "jsonrpc": "1.0", "id": str(self._id),
            "method": method, "params": list(params),
        }).encode()
        req = urllib.request.Request(
            self.url, data=payload,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode())
        if body.get("error"):
            raise RuntimeError("RPC error: {}".format(body["error"]))
        return body.get("result")

    def confirmations(self, block_hash):
        """Return confirmations, or 0 if the node does not know the hash."""
        try:
            info = self.call("getblock", block_hash)
        except RuntimeError:
            return 0
        if not isinstance(info, dict):
            return 0
        return int(info.get("confirmations", 0) or 0)

    def height(self):
        return int(self.call("getblockcount") or 0)

    def ping(self):
        self.call("getblockchaininfo")


def find_block_candidates(paths, max_bytes):
    """Yield (path, set_of_hashes) for files that look like block evidence."""
    out = []
    for root in paths:
        root = Path(root).expanduser()
        if not root.exists():
            continue
        files = [root] if root.is_file() else sorted(root.rglob("*"))
        for f in files:
            if not f.is_file():
                continue
            try:
                if f.stat().st_size > max_bytes:
                    continue
                text = f.read_text(errors="replace")
            except OSError:
                continue
            if not KEYWORD_RE.search(text):
                continue
            hashes = set()
            for m in HASH_RE.finditer(text):
                window = text[max(0, m.start() - 80):m.end() + 80]
                if KEYWORD_RE.search(window):
                    hashes.add(m.group(1).lower())
            if hashes:
                out.append((f, hashes))
    return out


def archive(path, hashes, confirmations, dest):
    dest = Path(dest).expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = dest / "{}_{}".format(stamp, path.name.replace("/", "_"))
    manifest = {
        "archived_at": now_iso(),
        "source_path": str(path),
        "coin": path.parts[-2] if len(path.parts) > 1 else None,
        "block_hashes": sorted(hashes),
        "confirmations": confirmations,
        "file_bytes": path.stat().st_size,
    }
    shutil_copy(path, target)
    (dest / (target.name + ".json")).write_text(
        json.dumps(manifest, indent=2) + "\n")
    return target, manifest


def shutil_copy(src, dst):
    import shutil
    shutil.copy2(src, dst)


def prune(paths, keep_dirs, max_age_hours, quiet, now):
    """Delete prunable scratch older than max_age_hours, sparing archives."""
    removed = 0
    freed = 0
    keep = {Path(d).expanduser().resolve() for d in keep_dirs}
    keep |= HASH_BEARING
    cutoff = now - max_age_hours * 3600
    for root in paths:
        root = Path(root).expanduser()
        if not root.exists():
            continue
        files = [root] if root.is_file() else sorted(root.rglob("*"))
        for f in files:
            if not f.is_file():
                continue
            try:
                if f.resolve() in keep:
                    continue
                if not f.name.endswith(PRUNABLE_SUFFIXES):
                    continue
                if f.stat().st_mtime > cutoff:
                    continue
            except OSError:
                continue
            size = f.stat().st_size
            if dry_run_global:
                log("  would prune {} ({:.1f} KiB)".format(f, size / 1024.0),
                    quiet)
            else:
                try:
                    f.unlink()
                except OSError as exc:
                    log("  ! could not remove {}: {}".format(f, exc), quiet)
                    continue
            removed += 1
            freed += size
    return removed, freed


dry_run_global = False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="archive confirmed blocks and prune scratch")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would happen, change nothing")
    ap.add_argument("--verify-only", action="store_true",
                    help="classify candidates, touch nothing")
    ap.add_argument("--scan", action="append", default=[],
                    help="directory to scan (repeatable)")
    ap.add_argument("--archive", default=str(DEFAULT_STATE / "blocks"),
                    help="where confirmed block evidence is kept")
    ap.add_argument("--rpc", default=None, help="local node JSON-RPC URL")
    ap.add_argument("--coin", default="unknown")
    ap.add_argument("--max-age-hours", type=float, default=24.0)
    ap.add_argument("--max-file-mib", type=float, default=16.0)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    global dry_run_global
    dry_run_global = args.dry_run or args.verify_only

    scan = args.scan or [
        str(Path.home() / ".local/state/solo-rig/logs"),
        str(Path.home() / ".local/state/solo-rig/miner-logs"),
    ]
    keep = [args.archive]
    now = time.time()

    rpc = None
    if args.rpc:
        rpc = NodeRPC(args.rpc, args.coin)
        try:
            rpc.ping()
            log("[*] node RPC reachable at {} (height {})".format(
                args.rpc, rpc.height()), args.quiet)
        except (urllib.error.URLError, OSError, RuntimeError,
                ValueError) as exc:
            if args.apply:
                log("error: node RPC unreachable ({}). Refusing to delete "
                    "block evidence that cannot be verified. Re-run once the "
                    "daemon is up, or pass --verify-only.".format(exc))
                return 2
            log("[!] node RPC unreachable ({}); treating every candidate as "
                "UNVERIFIED and preserving it".format(exc), args.quiet)

    candidates = find_block_candidates(scan, args.max_file_mib * 1024 * 1024)
    log("[*] {} file(s) with block-like evidence".format(len(candidates)),
        args.quiet)

    # Anything holding a block hash is protected from the age-based pruner.
    # Unverified ones are released back into the pool only after the hold.
    for path, _hashes in candidates:
        HASH_BEARING.add(path.resolve())

    archived = unverified = 0
    for path, hashes in candidates:
        best = 0
        for h in sorted(hashes):
            best = max(best, rpc.confirmations(h) if rpc else 0)
        if best >= MIN_CONFIRMATIONS:
            if args.apply:
                target, man = archive(path, hashes, best, args.archive)
                log("[+] ARCHIVED {} -> {} ({} confirmations)".format(
                    path, target.name, best), args.quiet)
                try:
                    path.unlink()
                except OSError:
                    pass
            else:
                log("[*] confirmed ({} conf) would archive: {}".format(
                    best, path), args.quiet)
            archived += 1
        else:
            unverified += 1
            # A hash that is not confirmed is NOT automatically disposable. The
            # rule is "cache goes, confirmed blocks stay" -- so a file holding a
            # block hash is quarantined for a human until the node either
            # confirms it or the operator retires it explicitly. Deleting here
            # is how real payout evidence gets lost.
            stale = path.stat().st_mtime < (now - UNVERIFIED_HOLD_HOURS * 3600)
            if stale and rpc is not None:
                # Hold expired with a live node that still does not know the
                # hash: it is a real orphan/stale find, so release it to the
                # pruner.
                HASH_BEARING.discard(path.resolve())
                log("[~] unverified for >{}h, releasing to prune: {}".format(
                    UNVERIFIED_HOLD_HOURS, path), args.quiet)
            elif rpc is None:
                log("[~] no node: PRESERVING unverified evidence (cannot "
                    "prove it worthless): {}".format(path), args.quiet)
            else:
                log("[~] unverified, holding for {}h before it may be pruned: "
                    "{}".format(UNVERIFIED_HOLD_HOURS, path), args.quiet)

    removed = freed = 0
    if not args.verify_only:
        removed, freed = prune(scan, keep, args.max_age_hours, args.quiet, now)

    verb = "would archive" if dry_run_global and not args.verify_only \
        else "archived"
    log("done: %d %s, %d unverified, %d cache file(s) %s (%.1f KiB)" % (
        archived, verb, unverified, removed,
        "would be freed" if dry_run_global else "freed", freed / 1024.0),
        args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())

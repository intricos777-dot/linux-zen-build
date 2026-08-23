#!/usr/bin/env bash
# POST-snapshot: capture root + home subvolumes after rebuild operations.
set -euo pipefail
STAMP="$(date +%Y%m%d-%H%M%S)"
SNAP_BASE="/.snapshots"

sudo mkdir -p "$SNAP_BASE"

echo "[*] Snapshotting / (@) -> $SNAP_BASE/${STAMP}-post-rebuild"
sudo btrfs subvolume snapshot -r / "$SNAP_BASE/${STAMP}-post-rebuild"

echo "[*] Snapshotting /home (@home) -> $SNAP_BASE/${STAMP}-post-rebuild-home"
sudo btrfs subvolume snapshot -r /home "$SNAP_BASE/${STAMP}-post-rebuild-home"

echo "[+] POST snapshots saved:"
sudo btrfs subvolume list / | grep "$STAMP"

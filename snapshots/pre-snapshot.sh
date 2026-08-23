#!/usr/bin/env bash
# PRE-snapshot: capture root + home subvolumes before rebuild operations.
set -euo pipefail
STAMP="$(date +%Y%m%d-%H%M%S)"
SNAP_BASE="/.snapshots"

sudo mkdir -p "$SNAP_BASE"

echo "[*] Snapshotting / (@) -> $SNAP_BASE/${STAMP}-pre-rebuild"
sudo btrfs subvolume snapshot -r / "$SNAP_BASE/${STAMP}-pre-rebuild"

echo "[*] Snapshotting /home (@home) -> $SNAP_BASE/${STAMP}-pre-rebuild-home"
sudo btrfs subvolume snapshot -r /home "$SNAP_BASE/${STAMP}-pre-rebuild-home"

echo "[+] PRE snapshots saved:"
sudo btrfs subvolume list / | grep "$STAMP"
echo "$STAMP" > /tmp/opencode/last-snapshot-stamp

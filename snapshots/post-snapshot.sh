#!/usr/bin/env bash
# POST-snapshot: capture root + home subvolumes after rebuild operations.
set -euo pipefail
STAMP="$(date +%Y%m%d-%H%M%S)"
SNAP_ROOT="/.snapshots/$STAMP-post-rebuild"
SNAP_HOME="/.snapshots/$STAMP-post-rebuild-home"

sudo mkdir -p "$(dirname "$SNAP_ROOT")"
ROOT_SUBVOL="$(findmnt -n -o SOURCE /)"
HOME_SUBVOL="$(findmnt -n -o SOURCE /home)"

echo "[*] Snapshotting $ROOT_SUBVOL -> $SNAP_ROOT"
sudo btrfs subvolume snapshot -r "$ROOT_SUBVOL" "$SNAP_ROOT"

if [ "$HOME_SUBVOL" != "$ROOT_SUBVOL" ]; then
  echo "[*] Snapshotting $HOME_SUBVOL -> $SNAP_HOME"
  sudo btrfs subvolume snapshot -r "$HOME_SUBVOL" "$SNAP_HOME"
fi

echo "[+] POST snapshots saved:"
sudo btrfs subvolume list / | grep "$STAMP-post-rebuild"

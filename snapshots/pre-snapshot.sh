#!/usr/bin/env bash
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# PRE-snapshot: capture root + home before rebuild operations.
#
# Thin wrapper around snapgood. All snapshot state, retention, and pinning
# now lives in one place, so this script no longer creates raw btrfs
# subvolumes directly (which used to be invisible to snapper and exempt from
# every cleanup rule).
#
# Pin the result if you are about to break the running system; a pinned
# snapshot is never auto-deleted, so it is your guaranteed way back.
set -euo pipefail

STAMP="$(date +%Y%m%d-%H%M%S)"
DESC="${STAMP}-pre-rebuild"
PIN=()

if [[ "${1:-}" == "--pin" ]]; then
  PIN=(--pin --note "pre-rebuild safety point, $(date -Is)")
  echo "[*] --pin given: this snapshot will be exempt from retention."
fi

if ! command -v snapgood >/dev/null 2>&1 && [[ ! -x /usr/local/sbin/snapgood ]]; then
  echo "[x] snapgood is not installed. Run: sudo ~/Projects/snapgood/install.sh" >&2
  exit 1
fi
SNAPGOOD="$(command -v snapgood || echo /usr/local/sbin/snapgood)"

echo "[*] PRE snapshot: / (@)"
sudo "$SNAPGOOD" create -c root -t single \
  -d "$DESC" "${PIN[@]}"

if snapper list-configs 2>/dev/null | grep -qw home; then
  echo "[*] PRE snapshot: /home (@home)"
  sudo "$SNAPGOOD" create -c home -t single \
    -d "$DESC" "${PIN[@]}"
else
  echo "[!] No snapper 'home' config; /home was not snapshotted."
  echo "[!] To fix: sudo ~/Projects/snapgood/install.sh"
fi

echo "[+] PRE snapshot complete. State:"
sudo "$SNAPGOOD" status
echo "$STAMP" > "${XDG_RUNTIME_DIR:-/tmp}/last-snapshot-stamp"

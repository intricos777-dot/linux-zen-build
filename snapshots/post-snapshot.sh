#!/usr/bin/env bash
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# POST-snapshot: capture root + home after rebuild operations.
#
# Thin wrapper around snapgood, mirroring pre-snapshot.sh. Pair them with
# `snapper` pre/post types if you want the two bracketing a change to be
# treated as a single unit.
set -euo pipefail

STAMP="$(date +%Y%m%d-%H%M%S)"
DESC="${STAMP}-post-rebuild"
PIN=()

if [[ "${1:-}" == "--pin" ]]; then
  PIN=(--pin --note "post-rebuild known-good, $(date -Is)")
fi

if ! command -v snapgood >/dev/null 2>&1 && [[ ! -x /usr/local/sbin/snapgood ]]; then
  echo "[x] snapgood is not installed. Run: sudo ~/Projects/snapgood/install.sh" >&2
  exit 1
fi
SNAPGOOD="$(command -v snapgood || echo /usr/local/sbin/snapgood)"

echo "[*] POST snapshot: / (@)"
sudo "$SNAPGOOD" create -c root -t single \
  -d "$DESC" "${PIN[@]}"

if snapper list-configs 2>/dev/null | grep -qw home; then
  echo "[*] POST snapshot: /home (@home)"
  sudo "$SNAPGOOD" create -c home -t single \
    -d "$DESC" "${PIN[@]}"
else
  echo "[!] No snapper 'home' config; /home was not snapshotted."
fi

echo "[+] POST snapshot complete. State:"
sudo "$SNAPGOOD" status

cat <<EOF

  If the rebuild boots and behaves, mark this snapshot known-good so it is
  never pruned automatically:

      sudo snapgood pin "$DESC" --note "rebuild $(date +%Y-%m-%d) verified"

  Snapshots are only kept because you say they boot. An unpinned snapshot is
  disposable; a pinned one is your way back.
EOF

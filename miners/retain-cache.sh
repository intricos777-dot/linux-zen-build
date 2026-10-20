#!/usr/bin/env bash
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Periodic cache retention for the solo miner set.
#
# Cache is disposable; confirmed blocks are not. This runs retain_blocks.py,
# which checks each block-shaped log against the local node before deleting
# anything, archives confirmed finds permanently, and holds unverified
# evidence for a week rather than discarding it.
set -euo pipefail

STATE_DIR="${SOLO_RIG_STATE:-$HOME/.local/state/solo-rig}"
COIN="${SOLO_RIG_COIN:-btc}"
RPC="${SOLO_RIG_RPC:-http://127.0.0.1:8332/}"
LOG_DIR="$STATE_DIR/logs"
ARCHIVE_DIR="$STATE_DIR/blocks"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$LOG_DIR" "$ARCHIVE_DIR"

run_retention() {
  python3 "$HERE/retain_blocks.py" \
    --scan "$LOG_DIR" \
    --archive "$ARCHIVE_DIR" \
    --rpc "$RPC" \
    --coin "$COIN" \
    --max-age-hours "${SOLO_RIG_MAX_AGE_H:-24}" \
    --apply
}

case "${1:-run}" in
  run)
    # A node that is down makes retention exit 2 on purpose: it will not
    # delete block evidence it cannot verify. That is a safe no-op, not a
    # failure worth alarming anyone about at 4am.
    if ! run_retention; then
      echo "[!] retention skipped: node unreachable, evidence preserved" >&2
    fi
    ;;
  dry-run)
    python3 "$HERE/retain_blocks.py" --scan "$LOG_DIR" \
      --archive "$ARCHIVE_DIR" --rpc "$RPC" --coin "$COIN" --dry-run
    ;;
  *)
    echo "usage: $0 [run|dry-run]" >&2
    exit 1
    ;;
esac

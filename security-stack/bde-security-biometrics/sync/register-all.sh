#!/bin/bash
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
set -euo pipefail
SYNC="bde-sync-client"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Registering BDE services with sync daemon..."

$SYNC register bde-daemon "python3 $REPO/pam/daemon/bde-daemon.py" "sudo systemctl restart bde-daemon.service" >/dev/null || echo "register bde-daemon failed"
$SYNC register bde-patrol "$SCRIPT_DIR/bde-patrol.sh" "" >/dev/null || echo "register bde-patrol failed"
$SYNC register replika-sync "python3 /home/livings/scripts/replika_sync.py" "systemctl --user restart replika-sync.service" >/dev/null || echo "register replika-sync failed"

echo "Registration complete."
$SYNC status

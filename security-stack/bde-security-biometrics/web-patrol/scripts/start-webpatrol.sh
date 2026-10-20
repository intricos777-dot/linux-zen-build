#!/usr/bin/env bash
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Start web patrol manually via bde-sync HTTP API
set -euo pipefail
SYNC_PORT="${BDE_SYNC_PORT:-4124}"
API="http://127.0.0.1:${SYNC_PORT}/webpatrol/start"
curl -s -X POST "$API" | python3 -m json.tool 2>/dev/null || curl -s -X POST "$API"

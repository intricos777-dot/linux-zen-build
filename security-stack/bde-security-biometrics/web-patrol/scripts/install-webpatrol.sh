#!/usr/bin/env bash
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Install BDE Web Patrol systemd service
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
WEBPATROL_JS="$PROJECT_ROOT/web-patrol/scripts/bde-webpatrol.js"
SERVICE_FILE="/etc/systemd/system/bde-webpatrol.service"

if [ ! -f "$WEBPATROL_JS" ]; then
    echo "Error: $WEBPATROL_JS not found" >&2
    exit 1
fi

# Create systemd service
sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=BDE Web Patrol Daemon
After=network.target bde-sync.service
Wants=bde-sync.service

[Service]
Type=simple
ExecStart=/usr/bin/node $WEBPATROL_JS
Restart=always
RestartSec=10
Environment=NODE_ENV=production
StandardOutput=journal
StandardError=journal

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$HOME/.bde $HOME/.hermes
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

echo "[*] Installed systemd service: $SERVICE_FILE"
echo "[*] Reloading systemd..."
sudo systemctl daemon-reload
echo "[*] Enabling and starting bde-webpatrol..."
sudo systemctl enable --now bde-webpatrol.service
echo "[*] Checking status..."
sudo systemctl status bde-webpatrol.service --no-pager
echo ""
echo "[*] Web patrol is now running hourly."
echo "    Archive: $HOME/.bde/webpatrol/archive"
echo "    Logs: journalctl -u bde-webpatrol -f"

#!/bin/bash
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# BDE Security Biometrics Installer for Garuda/Arch Linux
set -euo pipefail

# Resolve from this script's own location. The hardcoded /home/livings/workspace
# path does not exist on this host, so the installer could never find its own
# sources — every install step silently operated on missing files.
BDE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$BDE_DIR/.venv/bin/python"

echo "=== BDE Security Biometrics Installer ==="

# 1) Ensure venv and deps
if [ ! -f "$VENV_PYTHON" ]; then
    echo "[*] Creating Python venv..."
    python3 -m venv "$BDE_DIR/.venv"
    "$BDE_DIR/.venv/bin/pip" install numpy sounddevice
fi

# 2) Install daemon
echo "[*] Installing BDE daemon..."
sudo install -Dm755 "$BDE_DIR/pam/daemon/bde-daemon.py" /opt/bde/daemon/bde-daemon.py
sudo install -Dm755 "$BDE_DIR/pam/daemon/bde-sensor.py" /opt/bde/daemon/bde-sensor.py
sudo install -Dm755 "$BDE_DIR/pam/daemon/bde-touchpad.py" /opt/bde/daemon/bde-touchpad.py

# 3) Install PAM helpers
echo "[*] Installing PAM helpers..."
sudo install -Dm755 "$BDE_DIR/pam/modules/bde-auth" /usr/local/bin/bde-auth
sudo install -Dm755 "$BDE_DIR/pam/modules/bde-enroll" /usr/local/bin/bde-enroll
sudo install -Dm755 "$BDE_DIR/pam/modules/bde-verify" /usr/local/bin/bde-verify

# 4) Install systemd service
echo "[*] Installing systemd service..."
sudo tee /etc/systemd/system/bde-daemon.service > /dev/null << SVCEOF
[Unit]
Description=BDE Bioelectrical Biometrics Daemon
After=network.target

[Service]
Type=simple
ExecStart=$VENV_PYTHON /opt/bde/daemon/bde-daemon.py
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SVCEOF

# 5) Install PAM config
echo "[*] Installing PAM config..."
sudo install -Dm644 "$BDE_DIR/pam/modules/bde-auth.pam" /etc/pam.d/bde-auth

# 6) Create state directory
echo "[*] Creating state directory..."
sudo mkdir -p /var/lib/bde-daemon
sudo chmod 700 /var/lib/bde-daemon

# 7) Enable and start daemon
echo "[*] Starting BDE daemon..."
sudo systemctl daemon-reload
sudo systemctl enable --now bde-daemon.service

# 8) Wait for socket
echo "[*] Waiting for daemon socket..."
for i in $(seq 1 10); do
    if [ -S /var/run/bde-daemon.sock ]; then
        echo "  Socket ready."
        break
    fi
    sleep 1
done

if [ ! -S /var/run/bde-daemon.sock ]; then
    echo "  WARNING: Socket not found after 10s. Check: systemctl status bde-daemon"
fi

echo ""
echo "=== BDE Security Biometrics Installed ==="
echo ""
echo "Commands:"
echo "  bde-enroll [user]     - Enroll bioelectric profile (5 samples)"
echo "  bde-verify  [user]    - Test bioelectric verification"
echo "  bde-auth              - PAM helper (called by system)"
echo ""
echo "Next steps:"
echo "  1. Enroll:  bde-enroll sin"
echo "  2. Test:    bde-verify sin"
echo "  3. Add to PAM (see docs/pam-bde-integration.md)"

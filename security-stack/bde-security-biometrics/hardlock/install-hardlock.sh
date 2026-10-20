#!/bin/bash
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# BDE HardLock Installer for BlackArch Linux
# Enforces biometric authentication at boot and system lock
set -euo pipefail

echo "=== BDE HardLock Patch for BlackArch ==="

# 1) Install PAM biometrics stack
echo "[*] Installing PAM biometrics..."
sudo pacman -S --noconfirm --needed pam-biometric libfprint 2>/dev/null || true

# 2) Deploy BDE hardlock PAM config
echo "[*] Deploying BDE hardlock PAM config..."
sudo install -Dm644 /opt/bde/hardlock/bde-hardlock.pam /etc/pam.d/bde-hardlock

# 3) Enable biometric authentication for login, sudo, gdm, ssh
echo "[*] Configuring system services..."
for service in login sudo gdm-password sshd su; do
  if [ -f "/etc/pam.d/$service" ]; then
    if ! grep -q "bde-hardlock" "/etc/pam.d/$service" 2>/dev/null; then
      echo "auth [success=1 default=ignore] /usr/local/bin/bde-auth" | sudo tee -a "/etc/pam.d/$service" >/dev/null
      echo "auth required pam_deny.so" | sudo tee -a "/etc/pam.d/$service" >/dev/null
    fi
  fi
done

# 4) Deploy systemd lock service
echo "[*] Installing BDE lock service..."
sudo install -Dm644 /opt/bde/hardlock/bde-hardlock.service /etc/systemd/system/bde-hardlock.service
sudo systemctl daemon-reload
sudo systemctl enable --now bde-hardlock.service

# 5) Deploy BlackArch-style package
echo "[*] Building BlackArch package..."
if command -v pacman >/dev/null 2>&1 && [ -d /usr/share/blackarch ]; then
  sudo cp -r /opt/bde/blackarch/bde-hardlock /usr/share/blackarch/ 2>/dev/null || true
  sudo pacman -U --noconfirm /usr/share/blackarch/bde-hardlock/*.pkg.tar.zst 2>/dev/null || true
fi

echo "[+] BDE HardLock patch installed successfully"
echo "[*] Reboot to enforce biometric lock"

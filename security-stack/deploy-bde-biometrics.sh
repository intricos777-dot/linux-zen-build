#!/usr/bin/env bash
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Copyright (c) 2026 Living Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Licensed under Living Sin Proprietary License (LSPL-1.0)
# See LICENSE file for details.
# Deploy BDE security biometrics (PAM daemon) to ~/workspace.
# Uses bundled verified copy — no GitHub clone needed (upstream .venv bloat breaks transfers).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BDE_SRC="$HERE/bde-security-biometrics"
BDE_DIR="$HOME/workspace/bde-security-biometrics"

mkdir -p "$HOME/workspace"
rm -rf "$BDE_DIR"
cp -r "$BDE_SRC" "$BDE_DIR"

# Verify integrity against bundled manifest before installing.
cd "$BDE_SRC" && find . -type f | sed 's:^\./::' | sort > /tmp/bde-expected.$$
cd "$BDE_DIR" && find . -type f -not -path "./.venv/*" | sed 's:^\./::' | sort > /tmp/bde-actual.$$
diff /tmp/bde-expected.$$ /tmp/bde-actual.$$ >/dev/null && echo "[+] file manifest verified ($(wc -l < /tmp/bde-expected.$$) files)" || { echo "MANIFEST MISMATCH" >&2; exit 1; }
rm -f /tmp/bde-expected.$$ /tmp/bde-actual.$$

# Fresh venv (never trust a shipped one)
python3 -m venv "$BDE_DIR/.venv"
"$BDE_DIR/.venv/bin/pip" install -q --upgrade pip
"$BDE_DIR/.venv/bin/pip" install -q numpy sounddevice

echo "[*] Running BDE installer (sudo for /opt/bde + PAM + systemd)..."
cd "$BDE_DIR"
bash scripts/install-bde.sh

systemctl is-enabled bde-daemon.service >/dev/null && echo "[+] bde-daemon enabled"
systemctl is-active  bde-daemon.service >/dev/null && echo "[+] bde-daemon active"
echo "[*] BDE biometrics deploy complete."

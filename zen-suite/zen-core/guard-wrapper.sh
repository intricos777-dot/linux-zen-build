#!/usr/bin/env bash
# guard-wrapper.sh
# Secure wrapper for local-function-guard.ts
# Installs allowlists, sets permissions, creates systemd user unit.

set -euo pipefail

ZEN_CORE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ALLOWLIST_DIR="/etc/zen"
LOG_DIR="/var/log/zen"
STATE_DIR="/var/lib/zen"
UNIT_USER_DIR="${HOME}/.config/systemd/user"

install() {
    echo "[zen-guard] Installing local-function-guard..."

    # 1) Create directories
    mkdir -p "${ALLOWLIST_DIR}"
    mkdir -p "${LOG_DIR}"
    mkdir -p "${STATE_DIR}"
    chmod 700 "${LOG_DIR}"
    chmod 700 "${STATE_DIR}"

    # 2) Install default allowlist
    cat > "${ALLOWLIST_DIR}/function-allowlist.json" <<'ALLOWLIST'
{
  "version": "1.0.0",
  "description": "Default function allowlist for zen services",
  "allowlist": [
    {
      "binary": "/usr/bin/systemd",
      "allowedSyscalls": ["read", "write", "open", "close", "mmap", "munmap", "rt_sigaction", "ioctl"],
      "notes": "Systemd core"
    },
    {
      "binary": "/usr/bin/docker",
      "allowedSyscalls": ["read", "write", "open", "close", "clone", "execve", "socket", "connect", "bind"],
      "notes": "Docker runtime"
    },
    {
      "binary": "/usr/bin/ollama",
      "allowedSyscalls": ["read", "write", "open", "close", "mmap", "munmap", "socket", "bind", "listen", "accept"],
      "notes": "Ollama local LLM runtime"
    },
    {
      "binary": "/usr/local/bin/lia-cli",
      "allowedSyscalls": ["read", "write", "open", "close", "connect", "sendto", "recvfrom"],
      "notes": "LIA Coinbase CLI"
    },
    {
      "binary": "/usr/local/bin/crypto-bot",
      "allowedSyscalls": ["read", "write", "open", "close", "connect", "sendto", "recvfrom"],
      "notes": "Crypto mining/sweep bot"
    }
  ]
}
ALLOWLIST
    chmod 644 "${ALLOWLIST_DIR}/function-allowlist.json"

    # 3) Install guard script
    cp "${ZEN_CORE_DIR}/local-function-guard.ts" "${ALLOWLIST_DIR}/local-function-guard.ts"
    chmod 644 "${ALLOWLIST_DIR}/local-function-guard.ts"

    # 4) Create systemd user unit
    mkdir -p "${UNIT_USER_DIR}"
    cat > "${UNIT_USER_DIR}/local-function-guard.service" <<'UNIT'
[Unit]
Description=Local Function Guard (zen)
After=default.target

[Service]
Type=simple
ExecStart=/usr/bin/env node /etc/zen/local-function-guard.ts --mode enforce --allowlist /etc/zen/function-allowlist.json
Restart=on-failure
RestartSec=5
Environment=NODE_ENV=production

[Install]
WantedBy=default.target
UNIT

    # 5) Enable
    systemctl --user daemon-reload || true
    systemctl --user enable --now local-function-guard.service || true

    echo "[zen-guard] Installation complete."
    echo "[zen-guard] Logs: ${LOG_DIR}/function-guard.log"
    echo "[zen-guard] Allowlist: ${ALLOWLIST_DIR}/function-allowlist.json"
}

uninstall() {
    echo "[zen-guard] Uninstalling..."
    systemctl --user disable --now local-function-guard.service || true
    rm -f "${UNIT_USER_DIR}/local-function-guard.service"
    rm -f "${ALLOWLIST_DIR}/local-function-guard.ts"
    systemctl --user daemon-reload || true
    echo "[zen-guard] Uninstalled."
}

status() {
    echo "[zen-guard] Checking status..."
    systemctl --user status local-function-guard.service || true
    if [ -f "${LOG_DIR}/function-guard.log" ]; then
        echo "[zen-guard] Last 5 log entries:"
        tail -n 5 "${LOG_DIR}/function-guard.log" || true
    fi
}

case "${1:-install}" in
    install) install ;;
    uninstall) uninstall ;;
    status) status ;;
    *) echo "Usage: $0 {install|uninstall|status}"; exit 1 ;;
esac

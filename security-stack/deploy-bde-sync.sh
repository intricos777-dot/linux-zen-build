#!/usr/bin/env bash
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Copyright (c) 2026 Living Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Licensed under Living Sin Proprietary License (LSPL-1.0)
# See LICENSE file for details.
# Deploy the BDE cross-device sync daemon.
#
# Sync is a user-level background service, so this is a plain --user unit with
# no root and no PAM involvement. It is deployed disabled-by-default in terms
# of not being started until the user asks, because it phones home to a paired
# device and that should be a conscious choice.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/bde-security-biometrics/sync"
DEST="$HOME/workspace/bde-security-biometrics"
SYNC_DIR="$DEST/sync"
UNIT="bde-sync.service"
USER_UNIT_DIR="$HOME/.config/systemd/user"

echo "[*] Deploying BDE sync daemon"
mkdir -p "$SYNC_DIR" "$USER_UNIT_DIR"
# Test for the payload, not the directory: mkdir -p above guarantees the dir
# exists, so `[ -d ] || cp` never copies anything.
if [ ! -f "$SYNC_DIR/bde-sync.js" ]; then
  cp -r "$SRC/." "$SYNC_DIR/"
fi

UNIT_SRC="$SYNC_DIR/bde-sync.service"
[ -f "$UNIT_SRC" ] || { echo "ABORT: $UNIT_SRC missing" >&2; exit 1; }

# The bundled unit is a SYSTEM unit: it runs from /opt/bde and installs into
# multi-user.target. A user unit cannot execute from /opt (it would resolve
# against the user's own tree) and cannot be WantedBy=multi-user.target.
#
# Two options, and the choice is the user's because it decides whether the
# daemon runs before login or after:
#   system : sudo cp to /etc/systemd/system, start at boot  (needs root)
#   user   : rewritten %h + default.target, starts at login (no root)
MODE="${BDE_SYNC_MODE:-user}"

case "$MODE" in
  user)
    # The daemon also opens a unix socket at a hardcoded /var/run path, which a
    # user service cannot create (EACCES -> exit 1 -> restart loop). Verified:
    # starting it as a user unit crash-loops on exactly that. So user mode
    # overrides the socket location to a user-writable path via BDE_SOCKET.
    #
    # BDE_SOCKET is only honoured if the daemon supports it; check with:
    #   grep -n 'BDE_SOCKET' <dest>/bde-sync.js
    # If it does not, use --mode system instead of running a broken unit.
    if ! grep -q 'BDE_SOCKET' "$SYNC_DIR/bde-sync.js" 2>/dev/null; then
      cat <<EOF
[!] $SYNC_DIR/bde-sync.js hardcodes its unix socket to /var/run and does
    not honour BDE_SOCKET, so a --user unit cannot run it: it exits 1 with
    EACCES on listen and restart-loops.

    Refusing to install a unit that cannot start. Use system mode instead:

        BDE_SYNC_MODE=system bash $0

    or leave it uninstalled. Not enabling a known-broken unit.
EOF
      exit 1
    fi
    SOCKET="${XDG_RUNTIME_DIR:-$HOME/.local/state}/bde-sync.sock"
    cat > "$USER_UNIT_DIR/$UNIT" <<EOF
[Unit]
Description=BDE Sync Daemon (user)
After=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/node %h/workspace/bde-security-biometrics/sync/bde-sync.js
WorkingDirectory=%h/workspace/bde-security-biometrics/sync
Environment=BDE_SOCKET=$SOCKET
Restart=on-failure
RestartSec=3
Environment=NODE_ENV=production

[Install]
WantedBy=default.target
EOF
    echo "[+] wrote $USER_UNIT_DIR/$UNIT (user mode: starts at login)"
    echo "    unix socket -> $SOCKET"
    sed 's/^/    /' "$USER_UNIT_DIR/$UNIT"
    systemctl --user daemon-reload
    systemctl --user enable "$UNIT"
    echo "[+] $UNIT enabled (not started)"
    echo "    start:  systemctl --user start $UNIT"
    ;;

  system)
    echo "[*] system mode: needs sudo, starts at boot"
    sudo install -m 0644 "$UNIT_SRC" /etc/systemd/system/bde-sync.service
    sudo install -d /opt/bde/sync
    sudo install -m 0755 "$SYNC_DIR/bde-sync.js" /opt/bde/sync/bde-sync.js
    sudo install -m 0755 "$SYNC_DIR/sync-client.js" /opt/bde/sync/ 2>/dev/null || true
    sudo systemctl daemon-reload
    sudo systemctl enable bde-sync.service
    echo "[+] bde-sync.service installed and enabled at boot"
    ;;

  *)
    echo "ABORT: BDE_SYNC_MODE must be 'user' or 'system' (got '$MODE')" >&2
    exit 1
    ;;
esac

if [ -x "$SYNC_DIR/register-all.sh" ]; then
  echo "[*] register-all.sh is available to register paired devices:"
  echo "    bash $SYNC_DIR/register-all.sh"
fi

echo "[*] sync deploy complete."

#!/usr/bin/env bash
# Deploy the BDE web patrol (browser integrity monitoring).
#
# The bundled installer writes a system unit, so this script needs root for
# that step only. Everything before it is inspection.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/bde-security-biometrics/web-patrol"
DEST="$HOME/workspace/bde-security-biometrics"
PATROL_DIR="$DEST/web-patrol"

echo "[*] Deploying BDE web patrol"
mkdir -p "$DEST"
# mkdir -p above makes `[ -d ]` always true, which would skip the copy.
if [ ! -f "$PATROL_DIR/scripts/install-webpatrol.sh" ]; then
  mkdir -p "$PATROL_DIR"
  cp -r "$SRC/." "$PATROL_DIR/"
fi

INSTALLER="$PATROL_DIR/scripts/install-webpatrol.sh"
if [ ! -f "$INSTALLER" ]; then
  echo "ABORT: bundled installer missing at $INSTALLER" >&2
  exit 1
fi

# Show the config that will be enforced before installing anything that
# monitors browsing.
if [ -f "$PATROL_DIR/config/webpatrol.json" ]; then
  echo "[*] webpatrol config:"
  sed 's/^/    /' "$PATROL_DIR/config/webpatrol.json"
fi

echo "[*] Running installer (system unit, needs sudo)"
cd "$PATROL_DIR"
bash "$INSTALLER"

systemctl is-enabled bde-webpatrol.service >/dev/null 2>&1 \
  && echo "[+] bde-webpatrol enabled" \
  || echo "[i] installed; enable with: sudo systemctl enable --now bde-webpatrol.service"
echo "[*] web patrol deploy complete."

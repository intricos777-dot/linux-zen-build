#!/usr/bin/env bash
# Deploy the BDE shell guard and the Tampermonkey bridge.
#
# Both are user-level: a PATH shim and a userscript. No root, no system unit.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/bde-security-biometrics"
DEST="$HOME/workspace/bde-security-biometrics"
BIN="$HOME/.local/bin"

echo "[*] Deploying BDE tools"
mkdir -p "$DEST" "$BIN"

# ---- shell guard -----------------------------------------------------------
GUARD_SRC="$SRC/tools/bde-shell-guard"
if [ -f "$GUARD_SRC" ]; then
  install -m 0755 "$GUARD_SRC" "$BIN/bde-shell-guard"
  echo "[+] installed $BIN/bde-shell-guard"
else
  echo "[!] tools/bde-shell-guard not found; skipping"
fi

# ---- tampermonkey bridge ---------------------------------------------------
# Copied to a stable path rather than installed, because a userscript has to be
# imported by hand into the browser extension.
BRIDGE_SRC="$SRC/tampermonkey/bde-bridge.user.js"
BRIDGE_DIR="$HOME/workspace/bde-bridge"
if [ -f "$BRIDGE_SRC" ]; then
  mkdir -p "$BRIDGE_DIR"
  cp "$BRIDGE_SRC" "$BRIDGE_DIR/bde-bridge.user.js"
  echo "[+] userscript at $BRIDGE_DIR/bde-bridge.user.js"
  echo "    import it manually: Tampermonkey -> Create a new script -> paste"
else
  echo "[!] tampermonkey/bde-bridge.user.js not found; skipping"
fi

# ---- PATH ------------------------------------------------------------------
case ":$PATH:" in
  *":$BIN:"*) echo "[ok] $BIN already on PATH" ;;
  *)
    echo "[!] $BIN is not on PATH for this shell."
    echo "    add to your rc:  export PATH=\"$HOME/.local/bin:\$PATH\""
    ;;
esac

echo "[*] tools deploy complete."

#!/usr/bin/env bash
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Deploy the void-browser extension (BDE-integrated browser).
#
# A VS Code-style extension package. Building it needs npm; installing the
# built artefact into a browser profile is left to the user because browser
# profiles are not ours to rewrite unattended.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/bde-security-biometrics/void-browser"
DEST="$HOME/workspace/bde-security-biometrics"
EXT_DIR="$DEST/void-browser"

echo "[*] Deploying void-browser extension"
mkdir -p "$DEST"
# mkdir -p above makes `[ -d ]` always true, which would skip the copy.
if [ ! -f "$EXT_DIR/extension.js" ]; then
  mkdir -p "$EXT_DIR"
  cp -r "$SRC/." "$EXT_DIR/"
fi

if [ -f "$EXT_DIR/package.json" ]; then
  echo "[*] building extension (npm)"
  cd "$EXT_DIR"
  if [ ! -d node_modules ]; then
    npm ci --no-audit --no-fund 2>/dev/null || npm install --no-audit --no-fund
  fi
  npm run build 2>&1 | tail -20 || {
    echo "[!] build failed; extension left unbuilt at $EXT_DIR" >&2
    exit 1
  }
  echo "[+] build finished"
else
  echo "[!] no package.json; treating as a plain source tree"
fi

cat <<EOF
[*] Extension source at: $EXT_DIR

    Loading it is a manual step, because writing into a browser profile
    unattended is how you end up with a profile that no longer opens:

      chromium/chrome -> chrome://extensions -> Developer mode -> Load unpacked
        -> select: $EXT_DIR

    A packaged .vsix, if you prefer double-clicking it:
      cd $EXT_DIR && npx vsce package
EOF
echo "[*] void-browser deploy complete."

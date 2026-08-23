#!/usr/bin/env bash
# linux-zen-build: full rebuild entry point.
# Run AFTER pre-snapshot.sh. Order matters.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== [1/6] CPU miners (BTC solo, LTC solo, DOGE) ==="
if ! command -v cpuminer >/dev/null 2>&1 && ! command -v minerd >/dev/null 2>&1; then
  echo "[*] Installing cpuminer via paru..."
  paru -S --needed cpuminer
fi
bash "$HERE/miners/install-miners.sh"

echo "=== [2/6] Runtime deps for security stack ==="
if ! command -v node >/dev/null 2>&1; then
  sudo pacman -S --needed --noconfirm nodejs npm
fi

echo "=== [3/6] lin-antimalware (linAV) + tools ==="
bash "$HERE/security-stack/deploy-lin-antimalware.sh"

echo "=== [4/6] local-emergency-patrol ==="
bash "$HERE/security-stack/deploy-local-emergency-patrol.sh"

echo "=== [5/6] BDE biometrics + PAM daemon ==="
bash "$HERE/security-stack/deploy-bde-biometrics.sh"

echo "=== [6/6] quantum-enochian 21-layer verification ==="
QE="$HERE/quantum-enochian"
node --check "$QE/src/layered-enochian.js" && echo "OK engine syntax"
(cd "$QE" && node --test 2>/dev/null | grep -E '^# (pass|fail)' || true)
mkdir -p "$HOME/Projects"
rm -rf "$HOME/Projects/quantum-enochian.bak"
if [ -d "$HOME/Projects/quantum-enochian" ]; then
  mv "$HOME/Projects/quantum-enochian" "$HOME/Projects/quantum-enochian.bak"
fi
cp -r "$QE" "$HOME/Projects/quantum-enochian"
chmod 700 "$HOME/.quantum-enochian-layered" 2>/dev/null || true
bash "$HOME/Projects/quantum-enochian/scripts/bde-layered-patrol.sh"

echo "[+] Rebuild complete. Run post-snapshot.sh next."

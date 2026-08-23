#!/usr/bin/env bash
# Deploy CPU miners (BTC solo / LTC solo / DOGE) for user sin.
# Resolves cpuminer binary name (cpuminer or minerd depending on package).
set -euo pipefail

BIN_DIR="$HOME/.local/bin"
MINER_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$BIN_DIR"

CPUMINER=""
for cand in cpuminer minerd; do
  if command -v "$cand" >/dev/null 2>&1; then CPUMINER="$(command -v "$cand")"; break; fi
done
if [ -z "$CPUMINER" ]; then
  echo "ERROR: no cpuminer/minerd found. Install with: paru -S cpuminer" >&2
  exit 1
fi
echo "[*] Using miner binary: $CPUMINER"

install_miner_script() {
  local src="$1" dst="$2"
  sed "s|^exec .*cpuminer |exec $CPUMINER |; s|^exec /usr/bin/cpuminer |exec $CPUMINER |" \
    "$MINER_SRC/$(basename "$src")" > "$dst"
  chmod +x "$dst"
  echo "[+] installed $dst"
}

install_miner_script mine-btc-solo.sh "$BIN_DIR/mine-btc-solo.sh"
install_miner_script mine-ltc.sh      "$BIN_DIR/mine-ltc.sh"
install_miner_script mine-doge.sh     "$BIN_DIR/mine-doge.sh"

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "[!] NOTE: $BIN_DIR is not in PATH" ;;
esac

echo "[*] Miner deploy complete. Wallets are embedded in each script."

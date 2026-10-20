#!/usr/bin/env bash
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Mine DOGE solo, against your own dogecoind.
#
# TRUE solo, and a node entirely separate from LTC. Dogecoin removed auxpow
# (merged mining) in 2014, so "LTC+DOGE dual mining" does not exist; anyone
# selling you a merged LTC/DOGE config is selling you something that cannot
# work. These are two independent solo nodes that happen to run on one machine.
#
# CPU only: scrypt is memory-hard by design and resists GPU acceleration.
set -euo pipefail

PORT="${SOLO_DOGE_STRATUM_PORT:-3335}"
THREADS="${SOLO_DOGE_THREADS:-4}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! (exec 3<>"/dev/tcp/127.0.0.1/${PORT}") 2>/dev/null; then
  echo "ERROR: nothing is listening on 127.0.0.1:${PORT}." >&2
  echo "Start the bridge first:" >&2
  echo "  python3 ${HERE}/solo_bridge.py -c ${HERE}/configs/doge.json" >&2
  exit 1
fi

# The recorded DOGE address in this repo is not a valid Dogecoin address
# (bad base58 checksum, wrong version byte). Refuse to start rather than hash
# toward a payout that can never be spent.
if ! command -v dogecoin-cli >/dev/null 2>&1; then
  echo "NOTE: dogecoin-cli not on PATH, skipping daemon check." >&2
elif ! dogecoin-cli -datadir="${HOME}/.dogecoin" getblockchaininfo >/dev/null 2>&1; then
  echo "ERROR: dogecoind is not answering on its RPC port." >&2
  echo "Start it:  sudo systemctl start dogecoind" >&2
  exit 1
fi

CPUMINER=""
for cand in cpuminer-opt cpuminer cpuminer-multi minerd; do
  if command -v "$cand" >/dev/null 2>&1; then CPUMINER="$(command -v "$cand")"; break; fi
done
if [ -z "$CPUMINER" ]; then
  echo "ERROR: no CPU miner found (tried cpuminer-opt, cpuminer, cpuminer-multi)." >&2
  echo "Install one:  sudo pacman -S cpuminer-opt" >&2
  exit 1
fi

case "$("$CPUMINER" --help 2>&1)" in
  *--algo=*|*"-a "*) ALGO_FLAG="--algo=scrypt" ;;
  *) ALGO_FLAG="" ;;
esac

echo "[*] DOGE solo: $CPUMINER -> 127.0.0.1:${PORT}, scrypt, ${THREADS} threads"

exec "$CPUMINER" $ALGO_FLAG \
  --url="stratum+tcp://127.0.0.1:${PORT}" \
  --user="solo" \
  --pass="x" \
  --threads="${THREADS}" \
  --retry-pause=10

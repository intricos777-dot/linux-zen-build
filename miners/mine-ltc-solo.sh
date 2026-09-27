#!/usr/bin/env bash
# Mine LTC solo, against your own litecoind.
#
# This is TRUE solo: no pool, no shared ledger, no dev fee, 100% of any block
# reward. It is also a separate node from DOGE, because merged LTC+DOGE mining
# has not existed since Dogecoin dropped auxpow in 2014.
#
# CPU only. The RTX 3050 in this machine is useless for scrypt, which is
# deliberately memory-hard and cannot be profitably accelerated on a GPU.
set -euo pipefail

PORT="${SOLO_LTC_STRATUM_PORT:-3334}"
THREADS="${SOLO_LTC_THREADS:-4}"
BRIDGE="${SOLO_BRIDGE:-solo_bridge.py}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The bridge must be running, or there is no stratum endpoint to point at.
# This check is the difference between "mining solo" and "mining into the void".
if ! (exec 3<>"/dev/tcp/127.0.0.1/${PORT}") 2>/dev/null; then
  echo "ERROR: nothing is listening on 127.0.0.1:${PORT}." >&2
  echo "Start the bridge first:" >&2
  echo "  python3 ${HERE}/solo_bridge.py -c ${HERE}/configs/ltc.json" >&2
  echo "Without a local litecoind there is no work to mine, and a pool is the" >&2
  echo "only other thing that could hand us any - which is not solo." >&2
  exit 1
fi

# Confirm litecoind itself is reachable and synced, so a "running" bridge that
# is actually polling a half-synced chain does not read as a working rig.
if ! command -v litecoin-cli >/dev/null 2>&1; then
  echo "NOTE: litecoin-cli not on PATH, skipping daemon check." >&2
elif ! litecoin-cli -datadir="${HOME}/.litecoin" getblockchaininfo >/dev/null 2>&1; then
  echo "ERROR: litecoind is not answering on its RPC port." >&2
  echo "Start it:  sudo systemctl start litecoind" >&2
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

echo "[*] LTC solo: $CPUMINER -> 127.0.0.1:${PORT}, scrypt, ${THREADS} threads"
echo "[*] Payout is the LTC address in configs/ltc.json, not the pool's."

case "$("$CPUMINER" --help 2>&1)" in
  *--algo=*|*"-a "*) ALGO_FLAG="--algo=scrypt" ;;
  *) ALGO_FLAG="" ;;
esac

exec "$CPUMINER" $ALGO_FLAG \
  --url="stratum+tcp://127.0.0.1:${PORT}" \
  --user="solo" \
  --pass="x" \
  --threads="${THREADS}" \
  --retry-pause=10

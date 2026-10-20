#!/usr/bin/env bash
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Mine BTC solo on the CPU, against your own bitcoind.
#
# TRUE solo: no pool, no dev fee, 100% of the block reward.
#
# There is deliberately no GPU BTC miner here. SHA-256 has been ASIC-only since
# roughly 2013; the RTX 3050 in this machine cannot compete with an ASIC and
# no amount of configuration will change that. The only GPU-mineable coin in
# this repo is Ravencoin, on KawPoW (see mine-rvn-gpu.sh).
set -euo pipefail

PORT="${SOLO_BTC_STRATUM_PORT:-3333}"
THREADS="${SOLO_BTC_THREADS:-4}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! (exec 3<>"/dev/tcp/127.0.0.1/${PORT}") 2>/dev/null; then
  echo "ERROR: nothing is listening on 127.0.0.1:${PORT}." >&2
  echo "Start the bridge first:" >&2
  echo "  python3 ${HERE}/solo/solo_bridge.py -c ${HERE}/solo/configs/btc.json" >&2
  echo "A pool is the only other source of work, and a pool is not solo." >&2
  exit 1
fi

if command -v bitcoin-cli >/dev/null 2>&1; then
  if ! bitcoin-cli -datadir="${HOME}/.bitcoin" getblockchaininfo >/dev/null 2>&1; then
    echo "ERROR: bitcoind is not answering on its RPC port." >&2
    echo "Start it:  sudo systemctl start bitcoind" >&2
    exit 1
  fi
  IBD="$(bitcoin-cli -datadir="${HOME}/.bitcoin" getblockchaininfo 2>/dev/null \
         | sed -n 's/.*"initialblockdownload"[: ]*\([a-z]*\).*/\1/p')"
  if [ "${IBD}" = "true" ]; then
    echo "ERROR: bitcoind is still doing its initial block download." >&2
    echo "Solo mining finds nothing until the node has the full chain." >&2
    exit 1
  fi
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
  *--algo=*|*"-a "*) ALGO_FLAG="--algo=sha256d" ;;
  *) ALGO_FLAG="" ;;
esac

echo "[*] BTC solo: $CPUMINER -> 127.0.0.1:${PORT}, sha256d, ${THREADS} threads"
echo "[*] CPU only. Do not look for a GPU sha256d miner; it cannot exist usefully."

exec "$CPUMINER" $ALGO_FLAG \
  --url="stratum+tcp://127.0.0.1:${PORT}" \
  --user="solo" \
  --pass="x" \
  --threads="${THREADS}" \
  --retry-pause=10

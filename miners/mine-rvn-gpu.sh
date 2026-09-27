#!/usr/bin/env bash
# Mine Ravencoin solo on the GPU (KawPoW), against your own ravend.
#
# This is the one coin in this repo a GPU is genuinely the right tool for.
# KawPoW is ProgPoW based and was designed to be GPU-minable, which is the
# whole reason Bitcoin's SHA-256 was left to ASICs.
#
# Two things must be true before this runs, and this script refuses to start
# otherwise:
#   1. ravend must be installed, synced and answering on 127.0.0.1:8766.
#      Ravencoin Core is not in the Arch repos or the AUR, so the installer's
#      ravencoin stage reports UNAVAILABLE. See docs/RVN-NODE-GAP.md.
#   2. configs/rvn.json must hold a real Ravencoin address. None is on record.
set -euo pipefail

PORT="${SOLO_RVN_STRATUM_PORT:-3336}"
DATADIR="${HOME}/.ravencoin"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${HERE}/solo/configs/rvn.json"

RAVEN_CLI=""
for cand in raven-cli ravend; do
  if command -v "$cand" >/dev/null 2>&1; then RAVEN_CLI="$(command -v "$cand")"; break; fi
done
if [ -z "$RAVEN_CLI" ]; then
  cat >&2 <<EOF
ERROR: no ravend found on PATH.

Ravencoin Core is not in the Arch binary repos, and the AUR only carries
electrum-ravencoin and raven-qt (wallets, not a full node), so there is no
package to install here. See docs/RVN-NODE-GAP.md for the two options:
  A. build Ravencoin Core from source (github.com/RavenProject/Ravencoin)
  B. point the GPU at a remote ravend you control over a tunnel
EOF
  exit 1
fi

if ! "$RAVEN_CLI" -datadir="${DATADIR}" getblockchaininfo >/dev/null 2>&1; then
  echo "ERROR: ravend is not answering on 127.0.0.1:8766." >&2
  echo "Start it:  sudo systemctl start ravend" >&2
  exit 1
fi

# A placeholder address would mean hashing toward an unspendable payout, and
# solo mining pays the entire block reward to whichever address is set here.
PLACEHOLDER="$(sed -n 's/.*"address"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${CONFIG}" | head -1)"
case "${PLACEHOLDER}" in
  REPLACE_*|"")
    cat >&2 <<EOF
ERROR: no Ravencoin payout address configured.

  ${CONFIG}
  has address = "${PLACEHOLDER}"

Generate a real one:
  raven-cli -datadir=${DATADIR} getnewaddress
and put it in that file. Refusing to start rather than mining to a guess.
EOF
    exit 1
    ;;
esac

if ! (exec 3<>"/dev/tcp/127.0.0.1/${PORT}") 2>/dev/null; then
  echo "ERROR: nothing is listening on 127.0.0.1:${PORT}." >&2
  echo "Start the bridge first:" >&2
  echo "  python3 ${HERE}/solo/solo_bridge.py -c ${CONFIG}" >&2
  exit 1
fi

GMINER=""
for cand in gminer lolminer trex; do
  if command -v "$cand" >/dev/null 2>&1; then GMINER="$(command -v "$cand")"; break; fi
done
if [ -z "$GMINER" ]; then
  echo "ERROR: no GPU miner found (tried gminer, lolminer, trex)." >&2
  echo "Install one:  paru -S gminer-bin" >&2
  exit 1
fi

# GMiner and lolminer take --algo kawpow; trex takes --algo kawpow too but
# different pool flags, so branch on the binary name.
case "$(basename "$GMINER")" in
  trex)
    exec "$GMINER" \
      --algo kawpow \
      --url "stratum+tcp://127.0.0.1:${PORT}" \
      --user "solo" \
      --pass "x" \
      --nvml \
      --no-watchdog
    ;;
  *)
    exec "$GMINER" \
      --algo kawpow \
      --server "127.0.0.1:${PORT}" \
      --user "solo" \
      --pass "x" \
      --no-watchdog
    ;;
esac

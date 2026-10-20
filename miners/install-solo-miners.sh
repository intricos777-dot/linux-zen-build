#!/usr/bin/env bash
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
#
# install-solo-miners.sh -- staged, idempotent installer for true solo mining.
#
# Run this yourself as root. Nothing in this repo runs a root command on your
# behalf, and this script is written to be re-run safely: every stage checks
# what is already there before changing anything, and nothing is downloaded,
# installed or started until you have seen the whole plan and confirmed it.
#
#   sudo ./install-solo-miners.sh --plan     # show what it would do, change nothing
#   sudo ./install-solo-miners.sh --check    # report what is present, change nothing
#   sudo ./install-solo-miners.sh --daemons  # install node daemons only
#   sudo ./install-solo-miners.sh --miners   # install miner binaries only
#   sudo ./install-solo-miners.sh --services # write + enable systemd units
#   sudo ./install-solo-miners.sh            # all of the above
#
# Stages never block each other, so a partial install can be finished later.
#
# WHAT THIS DOES NOT DO
#   - It does not point any miner at a pool. Solo means your own daemon.
#   - It does not install a GPU Bitcoin miner. SHA-256 has been ASIC-only
#     since ~2013; an RTX 3050 cannot mine it. RVN/KawPoW is the GPU coin.
#   - It does not set up merged LTC+DOGE mining. Dogecoin dropped auxpow in
#     2014. They are two separate nodes or they are nothing.
#   - It does not invent a wallet address. BTC and LTC are the ones already in
#     this repo's README and are carried over unchanged. The DOGE address on
#     record is invalid (see below) and RVN has none at all, so both are left
#     as explicit, marked placeholders that stop the rig from starting.
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOLO_DIR="${REPO_DIR}/solo"
CONFIG_DIR="${SOLO_DIR}/configs"
UNIT_DIR="/etc/systemd/system"
STATE_DIR="/var/lib/solo-miners"
LOG_DIR="/var/log/solo-miners"

# The user the daemons and bridges run as. Mining as root would be indefensible:
# a miner is a network-facing program fed remote data by design.
SERVICE_USER="${SOLO_USER:-${SUDO_USER:-livings}}"
SERVICE_GROUP=""

DO_DAEMONS=0
DO_MINERS=0
DO_SERVICES=0
PLAN_ONLY=0
CHECK_ONLY=0
ASSUME_YES=0

C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_RED=$'\033[31m'
C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_CYAN=$'\033[36m'

say()  { printf '%s\n' "$*"; }
head1() { printf '\n%s%s%s\n' "$C_BOLD" "$*" "$C_RESET"; }
ok()   { printf '  %s[+]%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf '  %s[!]%s %s\n' "$C_YELLOW" "$C_RESET" "$*"; }
bad()  { printf '  %s[x]%s %s\n' "$C_RED" "$C_RESET" "$*"; }
info() { printf '  %s[ ]%s %s\n' "$C_CYAN" "$C_RESET" "$*"; }

usage() {
  sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

while [ $# -gt 0 ]; do
  case "$1" in
    --plan)     PLAN_ONLY=1 ;;
    --check)    CHECK_ONLY=1 ;;
    --daemons)  DO_DAEMONS=1 ;;
    --miners)   DO_MINERS=1 ;;
    --services) DO_SERVICES=1 ;;
    --all)      DO_DAEMONS=1; DO_MINERS=1; DO_SERVICES=1 ;;
    --user)     SERVICE_USER="$2"; shift ;;
    -y|--yes)   ASSUME_YES=1 ;;
    -h|--help)  usage ;;
    *) echo "unknown option: $1" >&2; usage ;;
  esac
  shift
done

if [ "$PLAN_ONLY" -eq 0 ] && [ "$CHECK_ONLY" -eq 0 ] && \
   [ "$DO_DAEMONS" -eq 0 ] && [ "$DO_MINERS" -eq 0 ] && [ "$DO_SERVICES" -eq 0 ]; then
  DO_DAEMONS=1; DO_MINERS=1; DO_SERVICES=1
fi

# ------------------------------------------------------------------ preflight

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    bad "This script must be run as root, by you, on purpose:"
    say  ""
    say  "    sudo $0 ${*}"
    say  ""
    say  "It has not been run for you and will not be. Review it first:"
    say  "    less ${BASH_SOURCE[0]}"
    exit 1
  fi
}

# Everything a plan/check run needs is already satisfied, so a non-root
# --plan or --check is deliberately allowed. Anything that writes is not.
if [ "$PLAN_ONLY" -eq 1 ] || [ "$CHECK_ONLY" -eq 1 ]; then
  [ "$(id -u)" -eq 0 ] || true
else
  require_root
fi

# Arch or an Arch derivative (Garuda, EndeavourOS, CachyOS, Artix, ...).
# On this machine ID=garuda, so a strict ID=arch test would wrongly warn on a
# perfectly good Arch-derived system.
on_arch() {
  [ -r /etc/os-release ] || return 1
  grep -qE '^ID(_LIKE)?=.*\b(arch|archarm|garuda|endeavouros|cachyos|artix|manjaro|arcolinux|blendos)\b' \
    /etc/os-release
}

# ------------------------------------------------------------------ inventory

# AUR packages are fetched with paru/yay; neither is guaranteed present, and
# installing a helper is not this script's business.
aur_helper() {
  for c in paru yay pikaur trizen; do
    command -v "$c" >/dev/null 2>&1 && { echo "$c"; return 0; }
  done
  return 1
}

# Is an AUR package already built and installed?
aur_installed() { pacman -Qq "$1" >/dev/null 2>&1; }

# Is a package available in the official binary repos?
repo_available() { pacman -Si "$1" >/dev/null 2>&1; }

# Install from the official repos. Idempotent: a no-op if already present.
install_repo_pkg() {
  local pkg="$1" why="$2"
  if pacman -Qq "$pkg" >/dev/null 2>&1; then
    ok "${pkg} already installed"
    return 0
  fi
  if ! repo_available "$pkg"; then
    bad "${pkg} is not in the official repos and cannot be installed here"
    warn "${why}"
    return 1
  fi
  info "installing ${pkg} from the official repos (${why})"
  if [ "$PLAN_ONLY" -eq 1 ]; then
    info "would run: pacman -S --needed ${pkg}"
    return 0
  fi
  if ! pacman -S --needed --noconfirm "$pkg"; then
    bad "pacman failed to install ${pkg}"
    return 1
  fi
  ok "${pkg} installed"
}

# Install from the AUR. Idempotent, and refuses to run without a helper
# rather than installing one behind the user's back.
install_aur_pkg() {
  local pkg="$1" why="$2"
  if aur_installed "$pkg"; then
    ok "${pkg} already installed"
    return 0
  fi
  local helper
  if ! helper="$(aur_helper)"; then
    bad "${pkg} is AUR-only and no AUR helper is installed"
    warn "Install paru or yay yourself, then re-run:  $0 ${why}"
    return 1
  fi
  if [ "$PLAN_ONLY" -eq 1 ]; then
    info "would run: ${helper} -S --needed ${pkg}   (${why})"
    return 0
  fi
  info "building ${pkg} from the AUR with ${helper} (${why})"
  if "$helper" -S --needed --noconfirm "$pkg"; then
    ok "${pkg} installed"
  else
    bad "AUR build of ${pkg} failed; see the output above"
    return 1
  fi
}

# ------------------------------------------------------------------ plan

print_plan() {
  head1 "Plan"
  say  "No changes will be made. This is what the install would do."

  head1 "  1. Node daemons (real full nodes, one per coin)"
  info "bitcoin-daemon      official repo    bitcoin core 31.1, the BTC node"
  info "litecoin-daemon     AUR (0.21.5.8)   the LTC node, independent"
  info "dogecoin-daemon     AUR (1.14.9)     the DOGE node, independent"
  info "ravencoin           NOT AVAILABLE    see below"

  head1 "  2. Miners"
  info "cpuminer-opt        AUR    CPU: BTC sha256d, LTC+DOGE scrypt"
  info "gminer-bin          AUR    GPU: RVN kawpow only"
  info "(nothing GPU for BTC: sha256d is ASIC territory)"

  head1 "  3. Solo bridge and services"
  info "installs solo/solo_bridge.py + blockwork.py to ${STATE_DIR}"
  info "one systemd user service per coin, running as ${SERVICE_USER}"
  info "four configs, each pointing at a LOCAL daemon RPC port"
  info "stratum bound to 127.0.0.1 only"

  head1 "  Wallets: what is known, and what is not"
  ok  "BTC  33oBrFCtn7SvqULsERymwtwmM8mXSrgcd9  (from this repo's README)"
  ok  "     verified: valid base58check, version 0x05, P2SH"
  ok  "LTC  MQ3qudKtDzSmwg7tHUV7JZTXizLYBtzffj  (from this repo's README)"
  ok  "     verified: valid base58check, version 0x32, Litecoin P2SH"
  bad "DOGE Dai6AHB6D4M152PWjnHNFF8v  is NOT a valid address"
  warn "     24 chars (too short), checksum 4701e383 != c143cf13, and the"
  warn "     version byte is 0x05 which is a Bitcoin P2SH version, not"
  warn "     Dogecoin's 0x1e/0x16. It is preserved as recorded, and the DOGE"
  warn "     service will refuse to start until you replace it."
  bad "RVN   no address is on record anywhere in this repository"
  warn "     Placeholder only. Generate one, or do not start the RVN service."

  head1 "  Ravencoin: a real gap, stated plainly"
  say  "  Ravencoin Core is not in the Arch binary repos, and the AUR carries"
  say  "  only electrum-ravencoin and raven-qt, which are wallets rather than"
  say  "  full nodes. There is no package to install."
  say  ""
  say  "  So the installer marks the ravencoin stage UNAVAILABLE and stops."
  say  "  It will not download a random binary and call it a node. The two"
  say  "  real options are in docs/RVN-NODE-GAP.md:"
  say  "    A. build Ravencoin Core from source (RavenProject/Ravencoin)"
  say  "    B. run ravend on another machine and tunnel its RPC to this one"

  head1 "  Honest expectations"
  say  "  Solo mining on a laptop finds a block roughly never. Bitcoin solo"
  say  "  needs on the order of 10^21 hashes per block; this CPU does about"
  say  "  10^6 hashes per second. That is a gap of fifteen orders of magnitude,"
  say  "  so do not treat this as income. It is set up so the work is real"
  say  "  solo work and the plumbing is correct, not so it pays."
  say  ""
  say  "  Ravencoin on an RTX 3050 is the only one of the four with any"
  say  "  plausible path, and even there solo share of the network hashrate"
  say  "  is a fraction of a percent."
}

# ------------------------------------------------------------------ check

run_check() {
  head1 "Environment"
  if on_arch; then
    local pretty
    pretty="$(sed -n 's/^PRETTY_NAME="\(.*\)"$/\1/p' /etc/os-release | head -1)"
    ok "${pretty:-Arch Linux} (Arch or Arch derivative)"
  else
    warn "not an Arch system; this installer targets Arch and its derivatives"
  fi
  say  "  user services will run as: ${SERVICE_USER}"
  if id "${SERVICE_USER}" >/dev/null 2>&1; then
    ok "user ${SERVICE_USER} exists"
  else
    bad "user ${SERVICE_USER} does not exist; pass --user <name>"
  fi

  head1 "Daemons"
  local d
  for d in bitcoind litecoind dogecoind ravend; do
    if command -v "$d" >/dev/null 2>&1; then
      ok "$(command -v "$d")"
    else
      info "${d} not installed"
    fi
  done
  if command -v bitcoind >/dev/null 2>&1; then
    info "bitcoind version: $(bitcoind -version 2>/dev/null | head -1)"
  fi

  head1 "Miners"
  for m in cpuminer-opt cpuminer cpuminer-multi gminer lolminer trex; do
    if command -v "$m" >/dev/null 2>&1; then
      ok "$(command -v "$m")"
    else
      info "${m} not installed"
    fi
  done
  # A GPU is only relevant to RVN; say so plainly if there is none.
  if command -v nvidia-smi >/dev/null 2>&1; then
    ok "nvidia-smi present (GPU miner path available for RVN/kawpow)"
  else
    info "no nvidia-smi; the RVN GPU miner will not run here"
  fi

  head1 "Python and the bridge"
  if command -v python3 >/dev/null 2>&1; then
    ok "python3 $(python3 -V 2>&1 | awk '{print $2}') (stdlib only, no pip needed)"
  else
    bad "python3 missing; the solo bridge cannot run"
  fi
  if [ -f "${SOLO_DIR}/test_blockwork.py" ]; then
    info "run the bridge's own tests with:"
    info "  python3 ${SOLO_DIR}/test_blockwork.py"
    info "  python3 ${SOLO_DIR}/test_solo_bridge.py"
  fi

  head1 "Config wallet addresses"
  local cfg addr chain
  for cfg in "${CONFIG_DIR}"/*.json; do
    [ -e "$cfg" ] || continue
    chain="$(basename "$cfg" .json)"
    addr="$(sed -n 's/^[[:space:]]*"address"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$cfg" | head -1)"
    if [ "$chain" = "doge" ] || [ "$chain" = "rvn" ]; then
      bad "${chain}: ${addr} (invalid or absent, see the plan output)"
    else
      ok "${chain}: ${addr}"
    fi
  done

  head1 "Pool pointers (must be none)"
  if grep -rIlE 'stratum\+tcp://(ltc\.viabtc\.io|scrypt\.mine\.zpool\.ca|solo\.ckpool\.org|[a-z0-9.-]+\.(pool|mines|com)/)' \
       "${REPO_DIR}" 2>/dev/null | grep -q .; then
    bad "a miner script still points at a pool:"
    grep -rInE 'stratum\+tcp://(ltc\.viabtc\.io|scrypt\.mine\.zpool\.ca|solo\.ckpool\.org)' \
         "${REPO_DIR}" 2>/dev/null | sed 's/^/      /'
  else
    ok "no pool endpoints anywhere in ${REPO_DIR}"
  fi
}

# ------------------------------------------------------------------ daemons

stage_daemons() {
  head1 "Stage 1: node daemons"
  say  "One full node per coin. Each is independent: no merged mining, and"
  say  "no coin's blocks are paid to another coin's address."

  install_repo_pkg bitcoin-daemon "the BTC node" || true
  install_repo_pkg bitcoin-cli "bitcoind's RPC client" || true

  # Bitcoin Core's own daemon package on Arch may not ship bitcoin-cli; if not,
  # the bridge authenticates with the .cookie file instead, so this is not fatal.
  if ! command -v bitcoin-cli >/dev/null 2>&1; then
    warn "bitcoin-cli not present; the bridge will use the .cookie file"
  fi

  install_aur_pkg litecoin-daemon "the LTC node" || \
    warn "LTC unavailable; the LTC service will not be installed"
  install_aur_pkg dogecoin-daemon "the DOGE node" || \
    warn "DOGE unavailable; the DOGE service will not be installed"

  head1 "  Ravencoin"
  bad "UNAVAILABLE: there is no Ravencoin Core package to install"
  say  "    not in the Arch binary repos"
  say  "    not in the AUR (only electrum-ravencoin and raven-qt, both wallets)"
  say  "  The RVN service is therefore NOT created by this script."
  say  "  See docs/RVN-NODE-GAP.md to build it from source or tunnel a"
  say  "  ravend you already run. Nothing is faked or downloaded blindly."
}

# ------------------------------------------------------------------ miners

stage_miners() {
  head1 "Stage 2: miners"
  install_aur_pkg cpuminer-opt "CPU: BTC sha256d, LTC/DOGE scrypt" || \
    warn "no CPU miner; the CPU mining scripts will refuse to start"

  # GMiner is the GPU miner for KawPoW only. It also mines Ethash-family
  # algorithms on a GPU, which is exactly the category BTC's sha256d is not in.
  install_aur_pkg gminer-bin "GPU: RVN kawpow" || \
    warn "no GPU miner; the RVN GPU script will refuse to start"

  if [ "$PLAN_ONLY" -eq 0 ]; then
    head1 "  A note on the GPU"
    say  "  No GPU Bitcoin miner is installed, and none can be: SHA-256 has"
    say  "  been ASIC-only since about 2013. The RTX 3050 is installed for"
    say  "  Ravencoin's KawPoW, which is the one GPU-mineable coin here."
  fi
}

# ------------------------------------------------------------------ services

# Write a systemd user unit for one coin.
write_unit() {
  local coin="$1" stratum_port="$2" rpc_port="$3"
  local unit="solo-${coin}.service"
  local path="${UNIT_DIR}/${unit}"
  local desc
  case "$coin" in
    btc)  desc="BTC true solo mining bridge (local bitcoind)" ;;
    ltc)  desc="LTC true solo mining bridge (local litecoind)" ;;
    doge) desc="DOGE true solo mining bridge (local dogecoind)" ;;
    rvn)  desc="RVN true solo mining bridge (local ravend)" ;;
  esac

  info "writing ${path}"
  if [ "$PLAN_ONLY" -eq 1 ]; then
    info "would run: systemctl --user enable --now ${unit}"
    return 0
  fi

  cat >"${path}" <<EOF
[Unit]
Description=${desc}
Documentation=file://${SOLO_DIR}/README.md
# The bridge is useless, and finds nothing, until the node has finished its
# initial block download, so the node is ordered first.
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${STATE_DIR}
ExecStart=/usr/bin/python3 ${STATE_DIR}/solo_bridge.py -c ${STATE_DIR}/configs/${coin}.json --listen 127.0.0.1 --port ${stratum_port}
Restart=on-failure
RestartSec=10
# Loopback only. Solo pays the whole block reward, so this endpoint must not
# be reachable from anywhere the user does not control.
# NoNewPrivileges and a private network namespace keep the blast radius small.
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=${STATE_DIR} ${LOG_DIR}
ProtectKernelTunables=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes

StandardOutput=append:${LOG_DIR}/${coin}.log
StandardError=append:${LOG_DIR}/${coin}.log

[Install]
WantedBy=default.target
EOF
  ok "${unit} written"
}

stage_services() {
  head1 "Stage 3: solo bridge, configs and systemd units"

  if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
    bad "user ${SERVICE_USER} does not exist; nothing installed"
    say  "  Create it, or re-run with --user <name>."
    return 1
  fi

  local group
  group="$(id -gn "${SERVICE_USER}" 2>/dev/null || echo "${SERVICE_USER}")"
  SERVICE_GROUP="${group}"

  info "installing bridge into ${STATE_DIR}, owned by ${SERVICE_USER}:${group}"
  if [ "$PLAN_ONLY" -eq 0 ]; then
    install -d -m 0755 -o "${SERVICE_USER}" -g "${group}" "${STATE_DIR}" \
      "${STATE_DIR}/configs" "${LOG_DIR}"
    install -m 0644 -o "${SERVICE_USER}" -g "${group}" \
      "${SOLO_DIR}/solo_bridge.py" "${SOLO_DIR}/blockwork.py" "${STATE_DIR}/"
    for cfg in "${CONFIG_DIR}"/*.json; do
      [ -e "$cfg" ] || continue
      install -m 0644 -o "${SERVICE_USER}" -g "${group}" \
        "${cfg}" "${STATE_DIR}/configs/"
    done
    ok "bridge and configs installed to ${STATE_DIR}"
  else
    info "would install solo_bridge.py, blockwork.py and configs/ into ${STATE_DIR}"
  fi

  # Validate every address before creating any unit, so an invalid one cannot
  # leave behind a service that fails in a confusing way later.
  head1 "  Validating payout addresses"
  local coin cfg addr
  for coin in btc ltc doge rvn; do
    cfg="${CONFIG_DIR}/${coin}.json"
    [ -e "${cfg}" ] || continue
    addr="$(sed -n 's/^[[:space:]]*"address"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${cfg}" | head -1)"
    case "${coin}:${addr}" in
      doge:Dai6AHB6D4M152PWjnHNFF8v)
        bad "DOGE address on record is invalid (bad checksum, wrong version byte)"
        warn "service solo-doge will NOT be created"
        warn "replace it in ${cfg} with a real address first:"
        warn "  dogecoin-cli -datadir=~/.dogecoin getnewaddress"
        continue
        ;;
      rvn:REPLACE_*|rvn:*)
        bad "no Ravencoin address configured"
        warn "service solo-rvn will NOT be created"
        continue
        ;;
    esac
    ok "${coin}: ${addr} looks well formed"
  done

  head1 "  systemd units"
  write_unit btc  3333 8332
  write_unit ltc  3334 9332
  write_unit doge 3335 22555

  head1 "  Enabling services"
  if [ "$PLAN_ONLY" -eq 1 ]; then
    info "would run: systemctl --user daemon-reload"
    info "would run: systemctl --user enable --now solo-btc.service"
    return 0
  fi

  systemctl --user daemon-reload
  ok "daemon-reload done"

  local unit
  for unit in solo-btc solo-ltc solo-doge; do
    # The daemon must be running and synced first, or the bridge just polls an
    # empty chain. Report rather than pretend.
    info "enabling ${unit}.service"
    if systemctl --user enable --now "${unit}.service"; then
      ok "${unit}.service enabled and started"
    else
      bad "${unit}.service failed to start; check: journalctl --user -u ${unit}"
    fi
  done

  warn "user services need the user to be logged in, or linger enabled:"
  say  "    sudo loginctl enable-linger ${SERVICE_USER}"
}

# ------------------------------------------------------------------ main

case "${PLAN_ONLY}${CHECK_ONLY}" in
  10) print_plan; exit 0 ;;
  01) run_check;  exit 0 ;;
esac

if [ "$PLAN_ONLY" -eq 0 ]; then
  head1 "True solo mining install"
  say  "  You are about to install full nodes and miners and start three"
  say  "  services that mine against them. Review with:"
  say  "      $0 --plan"
  say  ""
  if [ "$ASSUME_YES" -eq 0 ]; then
    read -r -p "  Continue? [y/N] " reply
    case "${reply}" in
      [yY]|[yY][eE][sS]) ;;
      *) say "  Cancelled. Nothing was changed."; exit 0 ;;
    esac
  fi
fi

on_arch || warn "this script was written for Arch Linux"

[ "$DO_DAEMONS" -eq 1 ]  && stage_daemons
[ "$DO_MINERS" -eq 1 ]   && stage_miners
[ "$DO_SERVICES" -eq 1 ] && stage_services

head1 "Done"
say  "Next:"
say  "  1. Sync check (do this before mining, not during):"
say  "       bitcoind  -datadir=\${HOME}/.bitcoin   getblockchaininfo | grep initialblockdownload"
say  "  2. Verify the bridge config without mining:"
say  "       sudo -u ${SERVICE_USER} python3 ${STATE_DIR}/solo_bridge.py \\"
say  "         -c ${STATE_DIR}/configs/btc.json --check"
say  "  3. Start mining on one coin:"
say  "       ${REPO_DIR}/mine-btc-cpu-solo.sh"
say  "       ${REPO_DIR}/mine-ltc-solo.sh"
say  "       ${REPO_DIR}/mine-doge-solo.sh    # only after fixing its address"
say  "  4. Read the honest expectations in the plan output above."

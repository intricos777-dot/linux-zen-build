#!/usr/bin/env bash
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Copyright (c) 2026 Living Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Licensed under Living Sin Proprietary License (LSPL-1.0)
# See LICENSE file for details.
# Deploy any component of the BDE security stack.
#
#   ./deploy-all.sh                 # list what is available
#   ./deploy-all.sh hardlock        # one component
#   ./deploy-all.sh --all           # every component, safe ones first
#
# "Safe" here means user-level and reversible. hardlock, pam and web-patrol
# change boot or system state, so --all runs them last and prints what each
# one will touch before running it.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# component -> script. Order is the order --all uses: least consequence first.
COMPONENTS=(
  "tools:deploy-bde-tools.sh:user"
  "sync:deploy-bde-sync.sh:user"
  "void-browser:deploy-void-browser.sh:user"
  "hardlock:deploy-bde-hardlock.sh:boot"
  "web-patrol:deploy-bde-webpatrol.sh:system"
)

usage() {
  echo "usage: $(basename "$0") <component>|--all|--list"
  echo
  printf '  %-14s %-26s %s\n' COMPONENT SCRIPT IMPACT
  for row in "${COMPONENTS[@]}"; do
    IFS=: read -r name script impact <<<"$row"
    printf '  %-14s %-26s %s\n' "$name" "$script" "$impact"
  done
  echo
  echo "impact: user   = no root, fully reversible"
  echo "        boot   = can affect whether the machine boots"
  echo "        system = writes a system unit (needs sudo)"
}

run_one() {
  local name="$1" script="$2" impact="$3"
  local path="$HERE/$script"
  if [ ! -f "$path" ]; then
    echo "[!] $name: $script not found, skipping"
    return 0
  fi
  echo
  echo "=============================================================="
  echo "  $name  ($impact)"
  echo "=============================================================="
  case "$impact" in
    boot)
      cat <<EOF
This component can DENY BOOT if no biometric profile is enrolled.
It refuses to install in that state. Continuing.
EOF
      ;;
    system)
      echo "This component writes a system unit and needs sudo."
      ;;
  esac
  bash "$path"
}

if [ $# -eq 0 ] || [ "${1:-}" = "--list" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi

if [ "${1:-}" = "--all" ]; then
  failures=0
  for row in "${COMPONENTS[@]}"; do
    IFS=: read -r name script impact <<<"$row"
    # A failure in one component must not abandon the rest; hardlock aborting
    # on "no enrollment" is expected, not fatal.
    run_one "$name" "$script" "$impact" || {
      echo "[!] $name failed or declined; continuing" >&2
      failures=$((failures + 1))
    }
  done
  echo
  echo "done. $failures component(s) reported a problem (often intentional)."
  exit 0
fi

target="$1"
for row in "${COMPONENTS[@]}"; do
  IFS=: read -r name script impact <<<"$row"
  if [ "$name" = "$target" ]; then
    run_one "$name" "$script" "$impact"
    exit 0
  fi
done

echo "unknown component: $target" >&2
usage
exit 1

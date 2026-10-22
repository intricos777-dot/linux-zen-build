#!/usr/bin/env bash
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Copyright (c) 2026 Living Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Licensed under Living Sin Proprietary License (LSPL-1.0)
# See LICENSE file for details.
# Lock /dev/rfkill to the rfkill group and keep the uaccess ACL from
# overriding that group ownership across udev upgrades.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/rfkill-lock"
TARGET_USER="${SUDO_USER:-${RFKILL_USER:-livings}}"

if [ "$(id -u)" -ne 0 ]; then
  echo "run as root: sudo bash $0" >&2
  exit 1
fi

for f in 71-rfkill-lock.rules 70-uaccess-rfkill.hook update-uaccess-override; do
  [ -f "$SRC/$f" ] || { echo "missing $SRC/$f" >&2; exit 1; }
done

if ! getent group rfkill >/dev/null; then
  groupadd --system rfkill
  echo "[+] created system group rfkill"
fi

if id "$TARGET_USER" >/dev/null 2>&1; then
  if id -nG "$TARGET_USER" | grep -qw rfkill; then
    echo "[+] $TARGET_USER already belongs to rfkill"
  else
    usermod -aG rfkill "$TARGET_USER"
    echo "[+] added $TARGET_USER to rfkill (log out and back in to apply)"
  fi
else
  echo "[!] user $TARGET_USER does not exist; group membership not changed" >&2
fi

install -Dm0644 "$SRC/71-rfkill-lock.rules" /etc/udev/rules.d/71-rfkill-lock.rules
install -Dm0644 "$SRC/70-uaccess-rfkill.hook" /etc/pacman.d/hooks/70-uaccess-rfkill.hook
install -Dm0755 "$SRC/update-uaccess-override" /usr/local/lib/rfkill-lock/update-uaccess-override

/usr/local/lib/rfkill-lock/update-uaccess-override
udevadm control --reload-rules
udevadm trigger --name-match=/dev/rfkill 2>/dev/null || true
udevadm settle

echo "[+] rfkill lock installed"
ls -l /dev/rfkill 2>/dev/null || true
getent group rfkill

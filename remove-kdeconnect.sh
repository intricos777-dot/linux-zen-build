#!/usr/bin/env bash
# Remove kdeconnect safely, with a rollback path.
#
# WHY THIS SCRIPT EXISTS
# ----------------------
# kdeconnect is NOT required by any package ("Required By: None"), so removing
# it cannot break plasma-workspace or plasma-desktop. Verified before writing.
#
# The one real hazard: the org.kde.kdeconnect applet was LOADED in the panel.
# If the package is removed while the panel config still references it, Plasma
# starts up trying to instantiate a widget whose QML files no longer exist.
# That does not brick the desktop, but it leaves a broken-panel error on every
# login until the config is fixed by hand.
#
# That applet entry has ALREADY been removed from
# ~/.config/plasma-org.kde.plasma.desktop-appletsrc, and a backup exists. This
# script re-checks it anyway, because a stale entry is the one failure mode
# that survives package removal.
#
# Run:  bash remove-kdeconnect.sh
# Revert: see ROLLBACK below.
set -euo pipefail

BACKUP_DIR="$HOME/.config"
STAMP="$(date +%Y%m%d%H%M%S)"
APPLETS="$BACKUP_DIR/plasma-org.kde.plasma.desktop-appletsrc"

say() { printf '\n== %s\n' "$1"; }

# ---------------------------------------------------------------- preflight
say "PREFLIGHT"

if ! pacman -Q kdeconnect >/dev/null 2>&1; then
  echo "kdeconnect is not installed. Nothing to do."
  exit 0
fi

REVERSE="$(pacman -Qi kdeconnect | awk '/^Required By/{print $0}')"
echo "reverse dependencies: ${REVERSE#Required By : }"
if [ "${REVERSE#Required By : }" != "None" ]; then
  echo "ABORT: something depends on kdeconnect. Not continuing." >&2
  exit 1
fi

# Belt and braces: if the applet is somehow still in the panel, strip it now
# rather than after the package is gone.
if grep -q '^plugin=org\.kde\.kdeconnect$' "$APPLETS" 2>/dev/null; then
  say "kdeconnect applet still present in panel config - removing it now"
  cp -a "$APPLETS" "$APPLETS.bak-preuninstall-$STAMP"
  python3 - "$APPLETS" <<'PY'
import re, sys
p = sys.argv[1]
with open(p, encoding="utf-8") as fh:
    text = fh.read()
# Drop the whole "[Containments]...[Applets][NN]" stanza that loads the applet.
out = re.sub(
    r"\n\[Containments\][^\n]*\[Applets\]\[\d+\]\n(?:[^\[\n][^\n]*\n)*?"
    r"plugin=org\.kde\.kdeconnect\n",
    "\n", text)
with open(p, "w", encoding="utf-8") as fh:
    fh.write(out)
PY
  if grep -q '^plugin=org\.kde\.kdeconnect$' "$APPLETS"; then
    echo "ABORT: could not remove the applet entry automatically."
    echo "Panel config left untouched. Remove it by hand, then re-run."
    exit 1
  fi
  echo "[ok] applet entry removed; backup at $APPLETS.bak-preuninstall-$STAMP"
else
  echo "[ok] no kdeconnect applet in panel config"
fi

# Confirm the systemtray (its immediate neighbour) survived, so a malformed
# edit is caught here rather than at next login.
if ! grep -q 'plugin=org\.kde\.plasma\.systemtray' "$APPLETS"; then
  echo "ABORT: systemtray applet missing from config - config looks damaged."
  echo "Restore from: $APPLETS.bak-preuninstall-$STAMP"
  exit 1
fi
echo "[ok] systemtray applet intact"

# ---------------------------------------------------------------- pre-removal backup
say "BACKING UP KDEConnect DATA"
for d in "$HOME/.local/share/kdeconnect" "$HOME/.config/kdeconnect"; do
  if [ -e "$d" ]; then
    cp -a "$d" "$d.bak-$STAMP"
    echo "  backed up $d -> $d.bak-$STAMP"
  fi
done
echo "  (no output above means there was no data to back up)"

# ---------------------------------------------------------------- removal
say "REMOVING PACKAGE"
# -R remove, -n skip initramfs (kdeconnect is not in one), -s unneeded deps.
# If pacman proposes removing anything unexpected it will list it and prompt:
# answer 'n' and nothing is changed.
sudo pacman -Rns kdeconnect

say "VERIFYING"
if pacman -Q kdeconnect >/dev/null 2>&1; then
  echo "kdeconnect still present - the removal did not complete."
  exit 1
fi
echo "[ok] kdeconnect package gone"

if pgrep -x kdeconnectd >/dev/null 2>&1; then
  echo "[!] kdeconnectd is still running; stop it with:"
  echo "    pkill -x kdeconnectd"
else
  echo "[ok] kdeconnectd not running"
fi

say "DONE"
cat <<EOF
Phone integration is gone. Nothing else was touched: kdeconnect had no
reverse dependencies, and no Plasma package listed it.

Your panel will lose the kdeconnect entry on next login (or immediately if you
run:  kquitapp6 plasma-plasmashell && qdbus org.kde.plasmashell /PlasmaShell \
reload).

ROLLBACK
  pacman -S kdeconnect
  # then restore the panel applet from:
  #   $APPLETS.bak-kdeconnect-*   (or .bak-preuninstall-$STAMP)
  # and your paired-device data from:
  #   ~/.local/share/kdeconnect.bak-$STAMP
EOF

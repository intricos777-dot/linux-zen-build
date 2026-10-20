#!/usr/bin/env bash
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Deploy the BDE hardlock component (boot-time biometric enforcement).
#
# Hardlock is the piece that makes a boot FAIL CLOSED when no enrolled
# biometric profile matches. It is the highest-consequence component in the
# stack, so this script refuses to install it in a state where it could lock
# the machine out: it checks for an existing enrollment first and never
# enables the unit blind.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/bde-security-biometrics/hardlock"
DEST="$HOME/workspace/bde-security-biometrics"
HARDLOCK_DIR="$DEST/hardlock"

echo "[*] Deploying BDE hardlock to $HARDLOCK_DIR"
mkdir -p "$DEST"
# mkdir -p above makes `[ -d ]` always true, which would skip the copy.
if [ ! -f "$HARDLOCK_DIR/install-hardlock.sh" ]; then
  mkdir -p "$HARDLOCK_DIR"
  cp -r "$SRC/." "$HARDLOCK_DIR/"
fi
chmod +x "$HARDLOCK_DIR"/*.sh 2>/dev/null || true

# The PAM drop-in is the part that can lock you out, so inspect it rather
# than blindly installing whatever is bundled.
PAM_FILE="$HARDLOCK_DIR/bde-hardlock.pam"
if [ -f "$PAM_FILE" ]; then
  echo "[*] bundled PAM stack:"
  sed 's/^/    /' "$PAM_FILE"
  if ! grep -qi "bde" "$PAM_FILE"; then
    echo "ABORT: $PAM_FILE does not reference bde — refusing to install." >&2
    exit 1
  fi
fi

# Enrollments are stored outside the repo. If none exist, enabling hardlock
# would deny every boot, including rescue.
ENROLL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/bde"
if [ ! -d "$ENROLL_DIR" ] || [ -z "$(ls -A "$ENROLL_DIR" 2>/dev/null)" ]; then
  cat <<EOF
[!] No biometric enrollment found in $ENROLL_DIR

    Hardlock denies boot when no profile matches. With zero enrollments that
    means no boot at all, including your rescue path.

    NOT installing. Enroll first:
        bash $DEST/scripts/install-bde.sh
        bde-enroll <user> --samples 5

    Then re-run this script.
EOF
  exit 1
fi
echo "[+] enrollment(s) present: $(ls -1 "$ENROLL_DIR" | wc -l)"

echo "[*] Running bundled hardlock installer (writes PAM + unit, needs sudo)"
cd "$HARDLOCK_DIR"
bash install-hardlock.sh

if systemctl is-enabled bde-hardlock.service >/dev/null 2>&1; then
  echo "[+] bde-hardlock enabled"
  echo
  echo "VERIFY YOU CAN STILL BOOT. If in doubt, disable it now:"
  echo "    sudo systemctl disable bde-hardlock.service"
  echo "Hardlock is fail-closed by design; test before walking away."
else
  echo "[i] bde-hardlock installed but NOT enabled (safe default)."
  echo "    enable with: sudo systemctl enable --now bde-hardlock.service"
fi
echo "[*] hardlock deploy complete."

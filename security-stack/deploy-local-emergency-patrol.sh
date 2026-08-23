#!/usr/bin/env bash
# Deploy local-emergency-patrol to ~/Projects.
set -euo pipefail
PROJECTS="$HOME/Projects"
mkdir -p "$PROJECTS"
[ -d "$PROJECTS/local-emergency-patrol" ] || git clone --depth 1 \
  "https://github.com/intricos777-dot/local-emergency-patrol.git" "$PROJECTS/local-emergency-patrol"

cd "$PROJECTS/local-emergency-patrol"
# Backend uses pyproject.toml (no requirements.txt upstream)
if [ -f backend/pyproject.toml ]; then
  [ -d venv ] || python3 -m venv venv
  ./venv/bin/pip install -q --upgrade pip
  ./venv/bin/pip install -q -e backend
  ./venv/bin/python -c "from app import main" && echo "[+] patrol backend imports OK"
fi
echo "[*] local-emergency-patrol deploy complete."

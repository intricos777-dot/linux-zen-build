# Repo Push Checklist

Before pushing the BDE Security & Biometrics Overhaul repo:

## Contents
- [ ] `README.md` is accurate and all referenced directories/files exist
- [ ] `docs/garuda-repo-setup.md` contains the exact `pacman.conf` repo block
- [ ] `docs/kali-repo-setup.md` contains the exact `sources.list.d` line
- [ ] `docs/pam-bde-integration.md` documents PAM stack edits for all target services
- [ ] `aur/PKGBUILD` install paths match the actual file locations in the repo
- [ ] `scripts/install-bde.sh` has been tested on a clean system
- [ ] No secrets, keys, or tokens are committed
- [ ] Git tags match `pkgver` in `aur/PKGBUILD` (`v1.0.0`, etc.)

## Commands
```bash
git status --short
git diff --stat
git log --oneline -5
```

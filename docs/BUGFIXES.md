<!-- Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work -->
# Bugfixes Applied in linux-zen-build

## quantum-enochian (layered encryption)

1. **CRITICAL — binary-safe multi-layer unwrap** (`src/layered-enochian.js`)
   `unwrapLayer()` returned decrypted ciphertext as a UTF-8 *string*. Ciphertext is
   high-entropy binary; forcing UTF-8 replaced invalid sequences with U+FFFD, so
   every unwrap after the first layer operated on corrupted bytes. Result: sealed
   blobs could not be unsealed through more than one layer (verified: the original
   repo fails its own roundtrip test). Fix: return a `Buffer` from `unwrapLayer()`
   and keep Buffers between layers in `unseal()`; convert to UTF-8 only at the end.

2. **21-layer extension** (3 triads of 7)
   - Triad I — Quantum Enochian: Root, Veil, Sigil, Aethyr, Choir, Watchtower, Seal
   - Triad II — Cypher Magick: Glyph, Charm, Hex, Ward, Talisman, Arcanum, Oracle
   - Triad III — The World Runes (.hack//G.U. phases): Skeith, Innis, Magus,
     Fidchell, Gorre, Macha, Tarvos
   Legacy layers 0–6 keep identical names/elements, so previously sealed blobs
   (single-layer recoverable) remain compatible. `status()` now reports triads.

3. **keygen secret handling** (`src/layered-cli.js`)
   Personal layer keys were derived from the layer *label* instead of a personal
   secret. Now accepts `--secret`; falls back to label for old behavior.

4. **debug-layered.sh**
   - Hardcoded `seq 0 6` → dynamic layer count with triad annotations.
   - Smoke-test unseal read from the real `$HOME` while seal wrote to a temp
     HOME → always failed. Now reads/writes within the same temp HOME.
   - Added missing `$REPO` definition.

## zen-suite

5. **PKGBUILD rebuilt** — original referenced release tarball, pem/der sources,
   placeholder checksums (`'SKIP'`, `ABCD1234` GPG key) and ~7 directories that
   were never committed (`scripts/`, `config/`, `systemd/`, `security/`,
   `sysusers/`, `tmpfiles/`, `udev/`). New PKGBUILD builds from git and packages
   the artifacts that actually exist (zen-core guard tooling, patrol cron,
   hardening conf, browser profiles).

## bde-security-biometrics

6. **Committed .venv removed from build flow** — the repo shipped ~28MB of
   committed virtualenv (numpy/sounddevice wheels), which broke tarball/git
   transfers repeatedly. Deploy script prunes `.venv` and lets
   `scripts/install-bde.sh` recreate it fresh.

## miners

7. **cpuminer binary name normalization** — scripts hardcode `/usr/bin/cpuminer`
   or bare `cpuminer`, but Arch's cpuminer package may install `minerd`.
   `install-miners.sh` resolves whichever binary exists and rewrites the deploy
   copies accordingly. (Confirmed on this system: AUR cpuminer 2.5.1 installs
   as `/usr/bin/minerd`.)

## deploy scripts (stability pass)

8. **lin-antimalware import path** — `cli/main.py` imports `scanner.engine`
   but requires repo root on `PYTHONPATH`; bare invocation fails with
   ModuleNotFoundError. Deploy script now sets PYTHONPATH and installs a
   `~/.local/bin/lin-antimalware` wrapper that works from anywhere.

9. **local-emergency-patrol packaging** — backend has no `requirements.txt`;
   it ships `pyproject.toml`. Deploy does editable install (`pip install -e
   backend`) and verifies `from app import main`.

10. **bde-security-biometrics transfer failures** — upstream commits its full
    `.venv/` (~28MB, thousands of files), which repeatedly broke git clones
    and tarballs (truncated fetch-pack). The release bundles a verified
    36-file copy; deploy re-verifies against a file manifest, builds a fresh
    venv, then runs the upstream installer. Service verified enabled+active.

11. **PATH hygiene** — `~/.local/bin` was not on PATH; added to `~/.bashrc`
    so miner scripts and the linAV wrapper resolve.


# BDE Security & Biometrics Overhaul
Root-level bioelectrical resonance biometrics for Linux PAM.

## What This Is
Audio-based bioelectric resonance detection for system authentication.
Captures frequency-domain signatures via microphone, stores as enrollment
profiles, and verifies via Pearson correlation in the PAM stack.

- `pam/daemon/` — systemd daemon + bioelectric sensor (FFT-based)
- `pam/modules/` — PAM helper, enrollment tool, verification tool
- `hardlock/` — boot-time biometric enforcement
- `sync/` — cross-device sync daemon
- `web-patrol/` — browser integrity monitoring
- `aur/` — Arch/Garuda PKGBUILD
- `scripts/` — installer
- `docs/` — integration guides

## Quick Install
```bash
sudo bash ~/workspace/bde-security-biometrics/scripts/install-bde.sh
```

## Usage

### Enroll bioelectric profile
```bash
bde-enroll sin --samples 5
```
Hold finger near microphone during each 3-second capture. Takes 5 readings
and averages them for a stable resonance profile.

### Test verification
```bash
bde-verify sin
```

### Add to PAM
Edit `/etc/pam.d/sudo` (and login, sddm, etc):
```
auth sufficient /usr/local/bin/bde-auth
auth required   pam_deny.so
```

## How It Works
1. **Sensor** captures audio resonance via microphone using numpy FFT
2. **Daemon** runs as systemd service on `/var/run/bde-daemon.sock`
3. **Enrollment** averages 5 samples, stores in `/var/lib/bde-daemon/`
4. **PAM helper** captures live signature, correlates with stored profile
5. **Verification** uses Pearson correlation — ≥0.85 = granted

## Files
- `/opt/bde/daemon/bde-daemon.py` — daemon
- `/opt/bde/daemon/bde-sensor.py` — bioelectric sensor
- `/usr/local/bin/bde-auth` — PAM helper
- `/usr/local/bin/bde-enroll` — enrollment tool
- `/usr/local/bin/bde-verify` — verification test
- `/etc/pam.d/bde-auth` — PAM config
- `/var/lib/bde-daemon/` — profiles + secrets

## Security
All biometric data stays local. No cloud required.
Profiles stored with 0600 perms. Daemon socket 0660.
Secret key generated at first run in `/var/lib/bde-daemon/secret.bin`.

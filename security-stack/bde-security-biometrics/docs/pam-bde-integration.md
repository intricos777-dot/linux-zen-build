# BDE PAM Integration

## Install
```bash
sudo bash ~/workspace/bde-security-biometrics/scripts/install-bde.sh
```

## Enroll bioelectric profile
```bash
bde-enroll sin --samples 5
```
Hold finger on sensor (or near microphone) during each capture. The tool takes 5 readings and averages them for a stable bioelectric resonance profile.

## Test verification
```bash
bde-verify sin
```

## Add to PAM stack

### sudo
Edit `/etc/pam.d/sudo` — add before `auth include system-auth`:
```
auth sufficient /usr/local/bin/bde-auth
```

### login
Edit `/etc/pam.d/login` — add at the top:
```
auth sufficient /usr/local/bin/bde-auth
```

### KDE/GDM
Edit `/etc/pam.d/sddm` or `/etc/pam.d/gdm-password`:
```
auth sufficient /usr/local/bin/bde-auth
```

## How it works

1. **Sensor** (`bde-sensor.py`) captures audio resonance via microphone using FFT
2. **Daemon** (`bde-daemon.py`) runs as systemd service, listens on `/var/run/bde-daemon.sock`
3. **Enrollment** (`bde-enroll`) takes 5 samples, averages them, stores profile in `/var/lib/bde-daemon/`
4. **PAM helper** (`bde-auth`) captures live signature, correlates with stored profile
5. **Verification** uses Pearson correlation — ≥0.85 = granted, <0.85 = denied

## Files
- `/opt/bde/daemon/bde-daemon.py` — daemon
- `/opt/bde/daemon/bde-sensor.py` — bioelectric sensor
- `/usr/local/bin/bde-auth` — PAM helper
- `/usr/local/bin/bde-enroll` — enrollment tool
- `/usr/local/bin/bde-verify` — verification test
- `/etc/pam.d/bde-auth` — PAM config
- `/var/lib/bde-daemon/` — profiles and secrets
- `/var/run/bde-daemon.sock` — daemon socket

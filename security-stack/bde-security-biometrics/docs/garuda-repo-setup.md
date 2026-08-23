# Garuda Linux / BlackArch pacman repo setup

## Add BDE repo to pacman.conf

```ini
[bde-security-biometrics]
Server = https://repo.intricos777-dot.com/bde-security-biometrics/arch/
SigLevel = Optional TrustAll
```

Install:
```bash
sudo -S -p '' pacman -Syy
sudo -S -p '' pacman -S bde-security-biometrics
```

Notes:
- Place repo above `[extra]` in `/etc/pacman.conf`.
- BlackArch tooling is compatible; this repo adds BDE biometrics on top.
